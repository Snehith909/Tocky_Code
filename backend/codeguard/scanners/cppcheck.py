"""
Cppcheck scanner adapter for C and C++ security analysis.
Detects buffer overflows, memory corruption, format string bugs, and unsafe functions.
"""

import subprocess
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from pathlib import Path
from codeguard.scanners.base import BaseScannerAdapter
from codeguard.models import Finding, Severity, FindingStatus


class CppcheckAdapter(BaseScannerAdapter):
    name = "cppcheck"
    supported_languages = ["c", "cpp"]

    def is_available(self) -> bool:
        cmd = self.resolve_executable("cppcheck")
        return cmd is not None

    def scan(self, target_path: str, config: Optional[Dict[str, Any]] = None) -> List[Finding]:
        if not self.is_available():
            return []

        exe = self.resolve_executable("cppcheck")
        args = [
            exe or "cppcheck",
            "--enable=warning,style,performance",
            "--xml",
            "--xml-version=2",
            target_path
        ]

        try:
            res = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=(config or {}).get("timeout", 60)
            )
            # Cppcheck writes XML report to stderr
            raw_xml = res.stderr or res.stdout
            return self.parse_output(raw_xml, target_path)
        except Exception:
            return []

    def parse_output(self, raw_output: str, target_path: str) -> List[Finding]:
        findings: List[Finding] = []
        if not raw_output or not raw_output.strip():
            return findings

        try:
            root = ET.fromstring(raw_output)
            errors = root.findall(".//error")
            for idx, err in enumerate(errors):
                err_id = err.get("id", "cppcheck-warning")
                sev_str = err.get("severity", "warning").upper()
                msg = err.get("msg", "Cppcheck warning")
                cwe = err.get("cwe")

                location = err.find("location")
                file_path = location.get("file", "") if location is not None else ""
                line_num = int(location.get("line", 1)) if location is not None else 1

                severity = Severity.HIGH.value if "error" in sev_str.lower() else Severity.MEDIUM.value

                findings.append(Finding(
                    id=f"CPP-{idx+1:04d}",
                    tool=self.name,
                    rule_id=f"cppcheck.{err_id}",
                    language="cpp",
                    file=file_path,
                    start_line=line_num,
                    end_line=line_num,
                    severity=severity,
                    message=msg,
                    evidence=f"{file_path}:{line_num}: {msg}",
                    status=FindingStatus.OPEN.value,
                    cwe=f"CWE-{cwe}" if cwe else None,
                    confidence="HIGH"
                ))
        except Exception:
            pass

        return findings
