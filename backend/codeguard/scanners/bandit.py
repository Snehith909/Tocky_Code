"""
Bandit scanner adapter for Python codebases.
Finds common security issues in Python code.
"""

import json
import subprocess
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from codeguard.scanners.base import BaseScannerAdapter
from codeguard.models import Finding, Severity, FindingStatus


class BanditAdapter(BaseScannerAdapter):
    name = "bandit"
    supported_languages = ["python"]

    def is_available(self) -> bool:
        cmd = self.resolve_executable("bandit")
        if cmd:
            return True
        try:
            res = subprocess.run(
                ["python", "-m", "bandit", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return res.returncode == 0
        except Exception:
            return False

    def scan(self, target_path: str, config: Optional[Dict[str, Any]] = None) -> List[Finding]:
        if not self.is_available():
            return []

        exe = self.resolve_executable("bandit")
        args = [exe or "bandit"]

        p = Path(target_path)
        if p.is_dir():
            args.extend(["-r", target_path])
        else:
            args.append(target_path)

        args.extend(["-f", "json", "-q"])

        try:
            res = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=(config or {}).get("timeout", 60)
            )
            # Bandit returns non-zero when issues are found, which is normal
            return self.parse_output(res.stdout, target_path)
        except Exception:
            return []

    def parse_output(self, raw_output: str, target_path: str) -> List[Finding]:
        findings: List[Finding] = []
        if not raw_output or not raw_output.strip():
            return findings

        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return findings

        results = data.get("results", [])
        for idx, item in enumerate(results):
            test_id = item.get("test_id", "B000")
            file_path = item.get("filename", "")
            line_num = int(item.get("line_number", 1))
            line_range = item.get("line_range", [line_num])
            end_line = max(line_range) if line_range else line_num

            sev_str = item.get("issue_severity", "MEDIUM")
            severity = Severity.from_str(sev_str).value

            message = item.get("issue_text", "Bandit security finding")
            code = item.get("code", "")
            confidence = item.get("issue_confidence", "MEDIUM")
            more_info = item.get("more_info", "")
            cwe = item.get("issue_cwe", {}).get("id")

            findings.append(Finding(
                id=f"BND-{idx+1:04d}",
                tool=self.name,
                rule_id=test_id,
                language="python",
                file=file_path,
                start_line=line_num,
                end_line=end_line,
                severity=severity,
                message=message,
                evidence=code.strip(),
                status=FindingStatus.OPEN.value,
                cwe=f"CWE-{cwe}" if cwe else None,
                help_uri=more_info or None,
                confidence=confidence,
                raw_details=item
            ))

        return findings
