"""
Semgrep scanner adapter.
Cross-language static analysis for JavaScript, TypeScript, Python, and more.
"""

import json
import subprocess
import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from codeguard.scanners.base import BaseScannerAdapter
from codeguard.models import Finding, Severity, FindingStatus


class SemgrepAdapter(BaseScannerAdapter):
    name = "semgrep"
    supported_languages = ["python", "javascript", "typescript", "go", "java", "c", "cpp", "csharp", "php", "ruby"]

    def is_available(self) -> bool:
        cmd = self.resolve_executable("semgrep")
        if cmd:
            return True
        # Try python module
        try:
            res = subprocess.run(
                ["python", "-m", "semgrep", "--version"],
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

        exe = self.resolve_executable("semgrep")
        args = [exe or "semgrep", "scan", "--json", "--quiet"]

        ruleset = (config or {}).get("ruleset", "auto")
        args.extend(["--config", ruleset])
        args.append(target_path)

        try:
            res = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=(config or {}).get("timeout", 60),
                cwd=target_path if Path(target_path).is_dir() else str(Path(target_path).parent)
            )
            return self.parse_output(res.stdout, target_path)
        except Exception as e:
            # Report failure gracefully
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
            check_id = item.get("check_id", "semgrep-rule")
            file_path = item.get("path", "")
            start = item.get("start", {})
            end = item.get("end", {})
            extra = item.get("extra", {})

            start_line = start.get("line", 1)
            end_line = end.get("line", start_line)
            message = extra.get("message", "Semgrep security finding")
            severity_str = extra.get("severity", "WARNING").upper()

            severity = Severity.from_str(severity_str).value
            lines = extra.get("lines", "")

            # Extract language from extension
            ext = Path(file_path).suffix.lower()
            lang_map = {
                ".py": "python",
                ".js": "javascript",
                ".jsx": "javascript",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".go": "go",
                ".java": "java",
            }
            lang = lang_map.get(ext, "generic")

            metadata = extra.get("metadata", {})
            cwe = metadata.get("cwe")
            if isinstance(cwe, list) and cwe:
                cwe = cwe[0]

            findings.append(Finding(
                id=f"SG-{idx+1:04d}",
                tool=self.name,
                rule_id=check_id,
                language=lang,
                file=file_path,
                start_line=start_line,
                end_line=end_line,
                start_col=start.get("col"),
                end_col=end.get("col"),
                severity=severity,
                message=message,
                evidence=lines.strip(),
                status=FindingStatus.OPEN.value,
                cwe=str(cwe) if cwe else None,
                help_uri=metadata.get("source"),
                confidence=metadata.get("confidence", "MEDIUM"),
                raw_details=item
            ))

        return findings
