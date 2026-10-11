"""
End-to-End integration test for CodeGuard AI.
Simulates the full lifecycle from workspace scan through LLM fix proposal,
patch scope validation, isolated verification, and token metric reporting.
"""

import unittest
import tempfile
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from codeguard.orchestrator import ScanOrchestrator
from codeguard.context_builder import build_minimal_context
from codeguard.llm_provider import MockLLMProvider
from codeguard.patching import validate_patch_scope
from codeguard.verification import VerificationEvaluator
from codeguard.storage import StorageManager
from codeguard.models import FindingStatus


class TestEndToEndLifecycle(unittest.TestCase):
    def test_complete_scan_fix_verify_cycle(self):
        # 1. Create a temporary realistic workspace with a vulnerable Python file
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            src_dir = workspace / "src"
            src_dir.mkdir(parents=True)

            vulnerable_file = src_dir / "db_handler.py"
            original_code = '''"""Database handler module."""
import sqlite3

def query_user(cursor, username: str):
    # Vulnerable SQL query
    query = "SELECT * FROM users WHERE username = %s" % username
    return cursor.execute(query)
'''
            vulnerable_file.write_text(original_code, encoding="utf-8")

            # 2. Execute Scan
            storage = StorageManager(str(workspace / ".codeguard" / "history.db"))
            orchestrator = ScanOrchestrator(storage_manager=storage)
            summary = orchestrator.scan_target(str(workspace))

            self.assertGreater(summary.total_findings, 0)
            target_finding = next(
                (f for f in summary.findings if "sql_injection" in f.rule_id),
                None
            )
            self.assertIsNotNone(target_finding, "Expected to detect SQL injection finding")

            # 3. Build Minimal Context
            context_data = build_minimal_context(str(workspace), target_finding)
            self.assertIn("SELECT * FROM users", context_data["snippet"])
            self.assertIn("<UNTRUSTED_CODE_SNIPPET", context_data["prompt"])

            # 4. Generate Fix Proposal via LLM Provider
            provider = MockLLMProvider()
            patch = provider.generate_fix(
                target_finding,
                context_data,
                vulnerable_file.read_text(encoding="utf-8")
            )
            storage.record_patch(patch)

            self.assertIn("%s", patch.replacement_snippet)
            self.assertIn("username", patch.replacement_snippet)

            # 5. Validate Scope
            valid_scope, _ = validate_patch_scope(
                patch.target_file,
                target_finding.file,
                str(workspace)
            )
            self.assertTrue(valid_scope)

            # 6. Isolated Verification
            evaluator = VerificationEvaluator(str(workspace))
            result = evaluator.verify_patch(target_finding, patch, run_tests=False)
            storage.record_verification(result)

            # Rescan on the patched file should now pass because SQL injection is parameterized!
            self.assertTrue(result.rescan_passed)
            # When tests are not configured, state is honestly reported as NEEDS_REVIEW (requires user check)
            self.assertEqual(result.status, FindingStatus.NEEDS_REVIEW.value)

            # 7. Check Aggregated Metrics
            metrics = storage.get_metrics()
            self.assertEqual(metrics["total_scans"], 1)
            self.assertEqual(metrics["total_findings"], summary.total_findings)
            self.assertEqual(metrics["total_patches"], 1)
            self.assertGreater(metrics["tokens"]["token_reduction_pct"], 80.0)


if __name__ == "__main__":
    unittest.main()
