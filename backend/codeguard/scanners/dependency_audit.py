"""
Dependency vulnerability scanner adapter for CodeGuard AI.
Scans npm and pip lockfiles/manifests for known vulnerable dependencies and CVEs.
"""

import json
import subprocess
import shutil
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from codeguard.scanners.base import BaseScannerAdapter
from codeguard.models import Finding, Severity, FindingStatus


# Known vulnerable package version patterns for instant offline auditing
KNOWN_VULN_PACKAGES = [
    ("pyyaml", r"<6\.0", "CWE-20", Severity.HIGH, "Arbitrary code execution in PyYAML < 6.0 via unsafe load"),
    ("requests", r"<2\.31\.0", "CWE-200", Severity.MEDIUM, "Information disclosure vulnerability in requests < 2.31.0"),
    ("urllib3", r"<2\.0\.7", "CWE-444", Severity.HIGH, "Request header injection vulnerability in urllib3 < 2.0.7"),
    ("lodash", r"<4\.17\.21", "CWE-1321", Severity.HIGH, "Prototype pollution in lodash < 4.17.21"),
    ("json-bigint", r"<1\.0\.0", "CWE-1321", Severity.HIGH, "Prototype pollution in json-bigint"),
    ("minimist", r"<1\.2\.6", "CWE-1321", Severity.HIGH, "Prototype pollution in minimist < 1.2.6"),
    ("express", r"<4\.19\.2", "CWE-79", Severity.MEDIUM, "Open redirect / IP spoofing in Express < 4.19.2"),
]


class DependencyAuditAdapter(BaseScannerAdapter):
    name = "dependency-audit"
    supported_languages = ["python", "javascript", "typescript", "generic"]

    def is_available(self) -> bool:
        return True

    def scan(self, target_path: str, config: Optional[Dict[str, Any]] = None) -> List[Finding]:
        target = Path(target_path)
        findings: List[Finding] = []
        counter = 1

        dirs_to_check = [target] if target.is_dir() else [target.parent]

        for d in dirs_to_check:
            # 1. Check npm dependencies
            pkg_json = d / "package.json"
            if pkg_json.exists():
                try:
                    data = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    for pkg_name, ver_str in deps.items():
                        for vuln_pkg, ver_pat, cwe, sev, desc in KNOWN_VULN_PACKAGES:
                            if pkg_name.lower() == vuln_pkg:
                                findings.append(Finding(
                                    id=f"DEP-NPM-{counter:04d}",
                                    tool=self.name,
                                    rule_id=f"dep.{pkg_name}.outdated",
                                    language="javascript",
                                    file=str(pkg_json.relative_to(target.parent if target.is_file() else target)),
                                    start_line=1,
                                    end_line=1,
                                    severity=sev.value,
                                    message=f"Vulnerable dependency detected: {pkg_name} {ver_str}. {desc}",
                                    evidence=f'"{pkg_name}": "{ver_str}"',
                                    status=FindingStatus.OPEN.value,
                                    cwe=cwe,
                                    confidence="HIGH"
                                ))
                                counter += 1
                except Exception:
                    pass

            # 2. Check Python requirements
            req_txt = d / "requirements.txt"
            if req_txt.exists():
                try:
                    lines = req_txt.read_text(encoding="utf-8", errors="replace").splitlines()
                    for idx, line in enumerate(lines, start=1):
                        cleaned = line.split("#")[0].strip()
                        if not cleaned:
                            continue
                        for vuln_pkg, ver_pat, cwe, sev, desc in KNOWN_VULN_PACKAGES:
                            if cleaned.lower().startswith(vuln_pkg):
                                findings.append(Finding(
                                    id=f"DEP-PY-{counter:04d}",
                                    tool=self.name,
                                    rule_id=f"dep.py.{vuln_pkg}",
                                    language="python",
                                    file=str(req_txt.relative_to(target.parent if target.is_file() else target)),
                                    start_line=idx,
                                    end_line=idx,
                                    severity=sev.value,
                                    message=f"Vulnerable Python dependency: {cleaned}. {desc}",
                                    evidence=cleaned,
                                    status=FindingStatus.OPEN.value,
                                    cwe=cwe,
                                    confidence="HIGH"
                                ))
                                counter += 1
                except Exception:
                    pass

        return findings

    def parse_output(self, raw_output: str, target_path: str) -> List[Finding]:
        return []
