"""
ESLint scanner adapter for JavaScript and TypeScript security analysis.
"""

import json
import subprocess
from typing import List, Dict, Any, Optional
from pathlib import Path
from codeguard.scanners.base import BaseScannerAdapter
from codeguard.models import Finding, Severity, FindingStatus


class ESLintAdapter(BaseScannerAdapter):
    name = "eslint"
    supported_languages = ["javascript", "typescript"]

    def is_available(self) -> bool:
        cmd = self.resolve_executable("eslint") or self.resolve_executable("eslint.cmd")
        return cmd is not None

    def scan(self, target_path: str, config: Optional[Dict[str, Any]] = None) -> List[Finding]:
        if not self.is_available():
            return []

        exe = self.resolve_executable("eslint")
        args = [exe or "eslint", "-f", "json"]

        p = Path(target_path)
        if p.is_dir():
            args.append(".")
            cwd = target_path
        else:
            args.append(str(p))
            cwd = str(p.parent)

        try:
            res = subprocess.run(
                args,
                capture_output=True,
                text=True,
                shell=True,
                cwd=cwd,
                timeout=(config or {}).get("timeout", 60)
            )
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

        finding_counter = 1
        for file_report in data:
            file_path = file_report.get("filePath", "")
            messages = file_report.get("messages", [])

            ext = Path(file_path).suffix.lower()
            lang = "typescript" if "ts" in ext else "javascript"

            for msg in messages:
                rule_id = msg.get("ruleId") or "eslint-general"
                # Filter for security rules or errors if security plugin is present
                is_sec = any(kw in rule_id.lower() for kw in ["security", "eval", "injection", "xss", "csrf", "secret", "unsafe"])
                # If rule isn't specifically marked security, we only report error-level issues
                severity_code = msg.get("severity", 1)  # 1: warn, 2: error
                if not is_sec and severity_code < 2:
                    continue

                line = int(msg.get("line", 1))
                end_line = int(msg.get("endLine", line))
                col = msg.get("column")
                end_col = msg.get("endColumn")
                text = msg.get("message", "ESLint finding")

                severity = Severity.HIGH.value if severity_code == 2 else Severity.MEDIUM.value

                findings.append(Finding(
                    id=f"ESL-{finding_counter:04d}",
                    tool=self.name,
                    rule_id=rule_id,
                    language=lang,
                    file=file_path,
                    start_line=line,
                    end_line=end_line,
                    start_col=col,
                    end_col=end_col,
                    severity=severity,
                    message=text,
                    evidence=f"Line {line}: {text}",
                    status=FindingStatus.OPEN.value,
                    raw_details=msg
                ))
                finding_counter += 1

        return findings
