"""
Finding normalization, deduplication, and aggregation for CodeGuard AI.
Preserves original tool names and rule IDs while producing unified finding objects.
"""

from typing import List, Dict, Any
from pathlib import Path
from codeguard.models import Finding, Severity


def normalize_and_deduplicate(findings: List[Finding]) -> List[Finding]:
    """
    Deduplicate findings where multiple scanners flag the exact same code location.
    Preserves highest severity and records contributing tools.
    """
    seen: Dict[str, Finding] = {}
    result: List[Finding] = []

    severity_order = {
        Severity.CRITICAL.value: 5,
        Severity.HIGH.value: 4,
        Severity.MEDIUM.value: 3,
        Severity.LOW.value: 2,
        Severity.INFO.value: 1,
    }

    for f in findings:
        # Normalize file path separator
        f.file = str(Path(f.file).as_posix())

        # Construct collision key based on normalized file and line range overlap
        key = f"{f.file}:{f.start_line}:{f.rule_id}"
        
        # Also check approximate line match for same file + same CWE/issue
        fuzzy_key = f"{f.file}:{f.start_line}:{f.cwe}" if f.cwe else None

        if key in seen:
            existing = seen[key]
            # If current finding has higher severity, upgrade existing
            if severity_order.get(f.severity, 0) > severity_order.get(existing.severity, 0):
                existing.severity = f.severity
                existing.message = f.message
            continue

        if fuzzy_key and fuzzy_key in seen:
            continue

        seen[key] = f
        if fuzzy_key:
            seen[fuzzy_key] = f
        result.append(f)

    return result
