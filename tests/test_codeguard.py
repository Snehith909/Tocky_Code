"""
Comprehensive test suite for CodeGuard AI.
Covers scanners, language detection, findings, context minimization,
patch generation, scope validation, verification states, and storage metrics.
"""

import unittest
import tempfile
import os
import sys
import json
import io
import urllib.error
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from codeguard.models import Finding, Severity, FindingStatus, PatchProposal
from codeguard.language_detection import detect_languages
from codeguard.scanners.builtin_rules import BuiltinRulesScanner
from codeguard.findings import normalize_and_deduplicate
from codeguard.triage import prioritize_findings
from codeguard.context_builder import redact_secrets, build_minimal_context
from codeguard.patching import validate_patch_scope, apply_patch_string, generate_diff
from codeguard.llm_provider import GeminiLLMProvider, MockLLMProvider
from codeguard.verification import VerificationEvaluator
from codeguard.storage import StorageManager
from codeguard.orchestrator import ScanOrchestrator


class TestCodeGuardEngine(unittest.TestCase):
    def setUp(self):
        self.fixtures_dir = Path(__file__).parent / "fixtures"

    def test_language_detection(self):
        profile = detect_languages(str(self.fixtures_dir))
        self.assertIn("python", profile.detected_languages)
        self.assertIn("javascript", profile.detected_languages)
        self.assertIn("typescript", profile.detected_languages)

    def test_builtin_scanner_detects_vulnerabilities(self):
        scanner = BuiltinRulesScanner()
        findings = scanner.scan(str(self.fixtures_dir))
        self.assertGreater(len(findings), 0)

        rules = {f.rule_id for f in findings}
        # Verify core vulnerability rules were triggered
        self.assertIn("builtin.py.unsafe_eval", rules)
        self.assertIn("builtin.js.command_injection", rules)
        self.assertIn("builtin.secret.hardcoded_credential", rules)

    def test_builtin_scanner_detects_vulnshop_python_patterns(self):
        source = '''app.secret_key = "supersecret123"
q = f"SELECT * FROM users WHERE username='{username}'"
        rows = db.execute(
            f"SELECT name FROM products WHERE name LIKE '%{term}%'"
        ).fetchall()
        output = os.popen(f"ping -c 1 {host}").read()
        '''
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "app.py"
            target.write_text(source, encoding="utf-8")
            findings = BuiltinRulesScanner().scan(str(target))

        rules = [finding.rule_id for finding in findings]
        self.assertEqual(rules.count("builtin.secret.hardcoded_credential"), 1)
        self.assertEqual(rules.count("builtin.py.sql_injection_fstring"), 2)
        self.assertEqual(rules.count("builtin.py.command_injection_popen"), 1)

    def test_scanner_does_not_flag_literal_eval_as_unsafe_eval(self):
        source = "import ast\nresult = ast.literal_eval(user_input)\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "safe.py"
            target.write_text(source, encoding="utf-8")
            findings = BuiltinRulesScanner().scan(str(target))

        self.assertNotIn("builtin.py.unsafe_eval", {finding.rule_id for finding in findings})

    def test_secret_redaction(self):
        sample = 'const API_KEY = "sk-abcdef1234567890abcdef1234567890";'
        redacted = redact_secrets(sample)
        self.assertNotIn("sk-abcdef1234567890abcdef1234567890", redacted)
        self.assertIn("[REDACTED", redacted)

    def test_context_minimization(self):
        sample_finding = Finding(
            id="FINDING-01",
            tool="builtin",
            rule_id="builtin.py.unsafe_eval",
            language="python",
            file="python_vulns/app.py",
            start_line=19,
            end_line=19,
            severity=Severity.CRITICAL.value,
            message="eval call",
            evidence="return eval(user_input)"
        )
        ctx = build_minimal_context(str(self.fixtures_dir), sample_finding, context_lines_before=5, context_lines_after=5)
        self.assertIn("eval(user_input)", ctx["snippet"])
        self.assertIn("<UNTRUSTED_CODE_SNIPPET", ctx["prompt"])
        self.assertLess(len(ctx["snippet"].splitlines()), 25)  # Context is strictly minimized

    def test_patch_scope_validation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            f1 = tmp / "src" / "app.py"
            f1.parent.mkdir(parents=True)
            f1.write_text("print('hello')", encoding="utf-8")

            # Valid scope
            valid, msg = validate_patch_scope("src/app.py", "src/app.py", str(tmp))
            self.assertTrue(valid)

            # Invalid scope (different file)
            valid, msg = validate_patch_scope("src/other.py", "src/app.py", str(tmp))
            self.assertFalse(valid)
            self.assertIn("Scope violation", msg)

            # Path traversal attempt
            valid, msg = validate_patch_scope("../outside.py", "src/app.py", str(tmp))
            self.assertFalse(valid)
            self.assertIn("traversal", msg)

    def test_llm_fix_generation_and_verification(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            test_file = tmp / "app.py"
            test_file.write_text("import ast\ndef compute(inp):\n    return eval(inp)\n", encoding="utf-8")

            finding = Finding(
                id="TEST-001",
                tool="builtin",
                rule_id="builtin.py.unsafe_eval",
                language="python",
                file="app.py",
                start_line=3,
                end_line=3,
                severity=Severity.CRITICAL.value,
                message="Arbitrary code execution",
                evidence="return eval(inp)"
            )

            # Generate fix using Mock provider
            provider = MockLLMProvider()
            ctx = build_minimal_context(str(tmp), finding)
            patch = provider.generate_fix(finding, ctx, test_file.read_text(encoding="utf-8"))

            self.assertIn("ast.literal_eval", patch.replacement_snippet)
            self.assertIn("PATCH-", patch.id)

            # Evaluate verification
            evaluator = VerificationEvaluator(str(tmp))
            result = evaluator.verify_patch(finding, patch, run_tests=False)

            # When tests are not configured, per rule, status is NEEDS_REVIEW (requires human verification),
            # but rescan must pass!
            self.assertTrue(result.rescan_passed)
            self.assertEqual(result.status, FindingStatus.NEEDS_REVIEW.value)

    def test_storage_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test.db"
            storage = StorageManager(str(db_path))

            finding = Finding(
                id="F-1",
                tool="builtin",
                rule_id="test.rule",
                language="python",
                file="app.py",
                start_line=1,
                end_line=1,
                severity=Severity.HIGH.value,
                message="test",
                evidence="x = 1"
            )
            storage.record_scan("SCAN-1", "test_path", [finding], 15.0)

            patch = PatchProposal(
                id="P-1",
                finding_id="F-1",
                target_file="app.py",
                diff="--- a\n+++ b",
                explanation="fix",
                provider="mock",
                model="test",
                tokens_used={"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
                latency_ms=12.5
            )
            storage.record_patch(patch)

            metrics = storage.get_metrics()
            self.assertEqual(metrics["total_scans"], 1)
            self.assertEqual(metrics["total_findings"], 1)
            self.assertEqual(metrics["total_patches"], 1)
            self.assertEqual(metrics["tokens"]["total_tokens"], 70)
            self.assertGreater(metrics["tokens"]["token_reduction_pct"], 0)

    def test_gemini_uses_header_auth_current_model_and_provider_token_usage(self):
        finding = Finding(
            id="GEMINI-001",
            tool="builtin",
            rule_id="builtin.py.sql_injection",
            language="python",
            file="app.py",
            start_line=1,
            end_line=1,
            severity=Severity.HIGH.value,
            message="SQL injection",
            evidence='query = f"SELECT * FROM users WHERE name={name}"'
        )
        response_data = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps({
                            "replacement_code": 'query = "SELECT * FROM users WHERE name=?"',
                            "explanation": "Use a parameterized query."
                        })
                    }]
                }
            }],
            "usageMetadata": {
                "promptTokenCount": 31,
                "candidatesTokenCount": 12,
                "totalTokenCount": 43
            }
        }

        with patch(
            "codeguard.llm_provider.urllib.request.urlopen",
            return_value=io.BytesIO(json.dumps(response_data).encode("utf-8"))
        ) as urlopen:
            patch_proposal = GeminiLLMProvider(api_key="test-api-key").generate_fix(
                finding,
                {"prompt": "Fix the demonstrated SQL injection."},
                finding.evidence
            )

        request = urlopen.call_args.args[0]
        self.assertEqual(patch_proposal.model, "gemini-2.5-flash")
        self.assertEqual(request.headers["X-goog-api-key"], "test-api-key")
        self.assertNotIn("key=", request.full_url)
        self.assertEqual(
            patch_proposal.tokens_used,
            {"prompt_tokens": 31, "completion_tokens": 12, "total_tokens": 43}
        )
        request_payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(
            request_payload["generationConfig"]["responseMimeType"],
            "application/json"
        )

    def test_gemini_http_failure_falls_back_to_specialized_provider(self):
        finding = Finding(
            id="GEMINI-HTTP-001",
            tool="builtin",
            rule_id="builtin.py.unsafe_eval",
            language="python",
            file="app.py",
            start_line=1,
            end_line=1,
            severity=Severity.CRITICAL.value,
            message="Arbitrary code execution",
            evidence="return eval(value)"
        )
        error = urllib.error.HTTPError(
            "https://generativelanguage.googleapis.com",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b'{"error":{"message":"API key not valid"}}')
        )

        with patch(
            "codeguard.llm_provider.urllib.request.urlopen",
            side_effect=error
        ):
            patch_proposal = GeminiLLMProvider(api_key="invalid").generate_fix(
                finding,
                {"prompt": "Fix the unsafe eval call."},
                finding.evidence
            )

        self.assertEqual(patch_proposal.provider, "codeguard-model")
        self.assertIn("Fallback to CodeGuard specialized model", patch_proposal.explanation)
        self.assertIn("HTTP 401", patch_proposal.explanation)
        self.assertIn("ast.literal_eval", patch_proposal.replacement_snippet)

    def test_secret_fix_replaces_complete_source_line(self):
        source = 'OPENAI_API_KEY = "sk-abcdef1234567890abcdef1234567890"\n'
        finding = Finding(
            id="SECRET-001",
            tool="builtin",
            rule_id="builtin.secret.openai_api_key",
            language="python",
            file="app.py",
            start_line=1,
            end_line=1,
            severity=Severity.CRITICAL.value,
            message="Hardcoded API key",
            evidence="sk-abcdef1234567890abcdef1234567890"
        )

        provider = MockLLMProvider()
        proposal = provider.generate_fix(finding, {"prompt": ""}, source)
        applied, updated = apply_patch_string(
            source,
            proposal.original_snippet,
            proposal.replacement_snippet
        )

        self.assertTrue(applied)
        self.assertNotIn("sk-abcdef1234567890abcdef1234567890", updated)
        self.assertIn("os.environ.get", updated)


if __name__ == "__main__":
    unittest.main()
