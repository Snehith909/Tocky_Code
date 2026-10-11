"""
Gitleaks scanner adapter for exposed secrets detection.
"""

import json
import subprocess
import tempfile
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from codeguard.scanners.base import BaseScannerAdapter
from codeguard.models import Finding, Severity, FindingStatus


class GitleaksAdapter(BaseScannerAdapter):
    name = "gitleaks"
    supported_languages = ["generic", "python", "javascript", "typescript", "go", "java"]

    def is_available(self) -> bool:
        cmd = self.resolve_executable("gitleaks")
        return cmd is not None

    def scan(self, target_path: str, config: Optional[Dict[str, Any]] = None) -> List[Finding]:
        if not self.is_available():
            return []

        exe = self.resolve_executable("gitleaks")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_report = tmp.name

        try:
            cmd = [
                exe or "gitleaks",
                "detect",
                "--no-git",
                "--source", target_path,
                "--report-format", "json",
                "--report-path", tmp_report
            ]
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=(config or {}).get("timeout", 60)
            )

            if Path(tmp_report).exists() and Path(tmp_report).stat().st_size > 0:
                with open(tmp_report, "r", encoding="utf-8") as f:
                    raw = f.read()
                return self.parse_output(raw, target_path)
            return []
        except Exception:
            return []
        finally:
            if Path(tmp_report).exists():
                try:
                    os.remove(tmp_report)
                except Exception:
                    pass

    def parse_output(self, raw_output: str, target_path: str) -> List[Finding]:
        findings: List[Finding] = []
        if not raw_output or not raw_output.strip():
            return findings

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return findings

        if not isinstance(data, list):
            return findings

        for idx, item in enumerate(data):
            rule_id = item.get("RuleID", "exposed-secret")
            file_path = item.get("File", "")
            start_line = int(item.get("StartLine", 1))
            end_line = int(item.get("EndLine", start_line))
            description = item.get("Description", "Exposed Secret Detected")
            secret = item.get("Secret", "")

            # Redact secret in evidence to adhere to safety guidelines
            redacted_evidence = f"[REDACTED_SECRET_{rule_id}]"
            match = item.get("Match", "")
            if match and secret:
                redacted_evidence = match.replace(secret, f"[REDACTED_{rule_id}]")

            findings.append(Finding(
                id=f"GLK-{idx+1:04d}",
                tool=self.name,
                rule_id=rule_id,
                language="generic",
                file=file_path,
                start_line=start_line,
                end_line=end_line,
                severity=Severity.HIGH.value,
                message=description,
                evidence=redacted_evidence,
                status=FindingStatus.OPEN.value,
                cwe="CWE-798",
                confidence="HIGH",
                raw_details={"rule": rule_id, "file": file_path}
            ))

        return findings
