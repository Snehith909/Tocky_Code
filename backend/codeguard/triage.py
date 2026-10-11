"""
Deterministic triage and prioritization for CodeGuard AI findings.
Adheres to rule: deterministic prioritization first, never delete raw findings.
"""

from typing import List
from codeguard.models import Finding, Severity


SEVERITY_WEIGHTS = {
    Severity.CRITICAL.value: 100,
    Severity.HIGH.value: 80,
    Severity.MEDIUM.value: 50,
    Severity.LOW.value: 20,
    Severity.INFO.value: 10,
}


def prioritize_findings(findings: List[Finding]) -> List[Finding]:
    """
    Sort findings deterministically:
    1. Severity weight descending (CRITICAL -> HIGH -> MEDIUM -> LOW -> INFO)
    2. File name ascending
    3. Line number ascending
    """
    return sorted(
        findings,
        key=lambda f: (
            -SEVERITY_WEIGHTS.get(f.severity.upper(), 0),
            f.file,
            f.start_line
        )
    )
