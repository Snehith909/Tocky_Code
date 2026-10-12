"""
Verification evaluator for CodeGuard AI.
Applies patches in isolated temporary working copies, executes rescans,
runs syntax and test suites, and evaluates state transitions:
VERIFIED, REJECTED, or NEEDS_REVIEW.
"""

import tempfile
import shutil
import os
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

from codeguard.models import (
    Finding,
    PatchProposal,
    VerificationResult,
    VerificationCheck,
    FindingStatus,
    Severity,
)
from codeguard.patching import validate_patch_scope, apply_patch_string
from codeguard.scanners.builtin_rules import BuiltinRulesScanner
from codeguard.sandbox import SandboxRunner


class VerificationEvaluator:
    def __init__(self, workspace_root: str, sandbox_runner: Optional[SandboxRunner] = None):
        self.workspace_root = Path(workspace_root).resolve()
        self.sandbox = sandbox_runner or SandboxRunner()

    def verify_patch(
        self,
        finding: Finding,
        patch: PatchProposal,
        run_tests: bool = True
    ) -> VerificationResult:
        start_t = time.perf_counter()
        checks: List[VerificationCheck] = []

        # 1. Scope Validation
        valid_scope, scope_msg = validate_patch_scope(
            patch.target_file,
            finding.file,
            str(self.workspace_root)
        )
        checks.append(VerificationCheck(
            name="Scope Validation",
            check_type="scope",
            passed=valid_scope,
            details=scope_msg
        ))

        if not valid_scope:
            return VerificationResult(
                patch_id=patch.id,
                finding_id=finding.id,
                status=FindingStatus.REJECTED.value,
                rescan_passed=False,
                tests_passed=False,
                tests_run=False,
                details=f"Patch rejected: {scope_msg}",
                checks_executed=checks,
                elapsed_seconds=round(time.perf_counter() - start_t, 3)
            )

        # 2. Setup isolated temporary copy
        with tempfile.TemporaryDirectory(prefix="codeguard_verify_") as tmp_dir:
            tmp_root = Path(tmp_dir)
            orig_target_file = self.workspace_root / finding.file

            if not orig_target_file.exists():
                return VerificationResult(
                    patch_id=patch.id,
                    finding_id=finding.id,
                    status=FindingStatus.NEEDS_REVIEW.value,
                    rescan_passed=False,
                    tests_passed=False,
                    tests_run=False,
                    details=f"Target file {finding.file} does not exist on disk",
                    checks_executed=checks,
                    elapsed_seconds=round(time.perf_counter() - start_t, 3)
                )

            # Copy file or workspace into temporary sandbox directory
            dest_file = tmp_root / finding.file
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(orig_target_file, dest_file)

            original_content = orig_target_file.read_text(encoding="utf-8", errors="replace")

            # 3. Apply patch
            applied, patched_content = apply_patch_string(
                original_content,
                patch.original_snippet,
                patch.replacement_snippet
            )

            if not applied:
                checks.append(VerificationCheck(
                    name="Patch Application",
                    check_type="patch",
                    passed=False,
                    details="Could not apply patch: original snippet not found in target file"
                ))
                return VerificationResult(
                    patch_id=patch.id,
                    finding_id=finding.id,
                    status=FindingStatus.REJECTED.value,
                    rescan_passed=False,
                    tests_passed=False,
                    tests_run=False,
                    details="Patch failed to apply to current file state",
                    checks_executed=checks,
                    elapsed_seconds=round(time.perf_counter() - start_t, 3)
                )

            dest_file.write_text(patched_content, encoding="utf-8")
            checks.append(VerificationCheck(
                name="Patch Application",
                check_type="patch",
                passed=True,
                details="Patch applied cleanly to working copy"
            ))

            # 4. Syntax Verification
            syntax_passed, syntax_msg = self._check_syntax(dest_file)
            checks.append(VerificationCheck(
                name="Syntax Validation",
                check_type="syntax",
                passed=syntax_passed,
                details=syntax_msg
            ))

            if not syntax_passed:
                return VerificationResult(
                    patch_id=patch.id,
                    finding_id=finding.id,
                    status=FindingStatus.REJECTED.value,
                    rescan_passed=False,
                    tests_passed=False,
                    tests_run=False,
                    details=f"Patch introduced syntax error: {syntax_msg}",
                    checks_executed=checks,
                    elapsed_seconds=round(time.perf_counter() - start_t, 3)
                )

            # 5. Security Rescan
            rescan_scanner = BuiltinRulesScanner()
            original_findings = rescan_scanner.scan(str(orig_target_file))
            original_fingerprints = {f.fingerprint for f in original_findings}

            new_findings = rescan_scanner.scan(str(dest_file))

            # Check if original vulnerability rule is still triggered
            original_still_present = any(
                (f.rule_id == finding.rule_id or (finding.cwe and f.cwe == finding.cwe))
                and abs(f.start_line - finding.start_line) <= 3
                for f in new_findings
            )
            # Check if new critical/high findings were created that were not already present
            new_critical_introduced = any(
                f.severity in [Severity.CRITICAL.value, Severity.HIGH.value]
                and f.fingerprint not in original_fingerprints
                and f.rule_id != finding.rule_id
                for f in new_findings
            )

            rescan_ok = (not original_still_present) and (not new_critical_introduced)
            rescan_detail = "Original vulnerability resolved with no new critical findings."
            if original_still_present:
                rescan_detail = f"Vulnerability {finding.rule_id} is still detected after applying patch."
            elif new_critical_introduced:
                rescan_detail = "Patch introduced new critical/high security issues."

            checks.append(VerificationCheck(
                name="Security Rescan",
                check_type="rescan",
                passed=rescan_ok,
                details=rescan_detail
            ))

            if not rescan_ok:
                return VerificationResult(
                    patch_id=patch.id,
                    finding_id=finding.id,
                    status=FindingStatus.REJECTED.value,
                    rescan_passed=False,
                    tests_passed=False,
                    tests_run=False,
                    details=rescan_detail,
                    checks_executed=checks,
                    elapsed_seconds=round(time.perf_counter() - start_t, 3)
                )

            # 6. Test Suite Execution (if configured and requested)
            tests_run = False
            tests_passed = False
            test_detail = "No custom test command configured for file."

            # Check for pytest or npm test in workspace
            if run_tests:
                test_cmd = self._detect_test_command(dest_file)
                if test_cmd:
                    tests_run = True
                    ok, out, _ = self.sandbox.run_command(test_cmd, str(tmp_root))
                    tests_passed = ok
                    test_detail = f"Test execution {'succeeded' if ok else 'failed'}: {out[:100]}"
                    checks.append(VerificationCheck(
                        name="Test Suite",
                        check_type="test",
                        passed=tests_passed,
                        details=test_detail
                    ))
                else:
                    checks.append(VerificationCheck(
                        name="Test Suite",
                        check_type="test",
                        passed=True,
                        details="Tests not configured; evaluated via syntax and security rescan."
                    ))

            elapsed = round(time.perf_counter() - start_t, 3)

            # 7. Final status decision adhering strictly to safety rule:
            # "Do not label a patch VERIFIED if a required check failed, did not run, or was inconclusive."
            if tests_run and not tests_passed:
                status = FindingStatus.REJECTED.value
                details = "Patch rejected: Test suite failed after patch application."
            elif not tests_run:
                # Syntax & rescan passed, but test suite did not run
                status = FindingStatus.NEEDS_REVIEW.value
                details = "Security rescan passed, but test suite did not run (marked NEEDS_REVIEW for human verification)."
            else:
                status = FindingStatus.VERIFIED.value
                details = "All verification checks passed (Syntax, Security Rescan, and Tests)."

            return VerificationResult(
                patch_id=patch.id,
                finding_id=finding.id,
                status=status,
                rescan_passed=rescan_ok,
                tests_passed=tests_passed,
                tests_run=tests_run,
                details=details,
                checks_executed=checks,
                elapsed_seconds=elapsed
            )

    def _check_syntax(self, file_path: Path) -> tuple[bool, str]:
        ext = file_path.suffix.lower()
        if ext == ".py":
            import py_compile
            try:
                py_compile.compile(str(file_path), doraise=True)
                return True, "Python syntax check passed"
            except py_compile.PyCompileError as e:
                return False, f"Python compile error: {str(e)}"
        elif ext in [".js", ".jsx", ".ts", ".tsx"]:
            # Basic node check if node is installed
            if shutil.which("node") and ext in [".js", ".cjs", ".mjs"]:
                res = os.system(f'node --check "{file_path}" >nul 2>&1')
                if res == 0:
                    return True, "Node syntax check passed"
                return False, "JavaScript syntax error detected"
            return True, "Syntax accepted"
        return True, "Syntax check not required for file type"

    def _detect_test_command(self, file_path: Path) -> Optional[List[str]]:
        # Check if corresponding test file exists
        test_py = file_path.parent / f"test_{file_path.name}"
        if test_py.exists():
            return ["python", "-m", "unittest", str(test_py)]
        return None
