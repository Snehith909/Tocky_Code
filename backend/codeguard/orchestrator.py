"""
Scan orchestrator for CodeGuard AI.
Coordinates language detection, scanner adapter selection, execution,
finding normalization, and deterministic triage.
"""

import time
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path

from codeguard.models import Finding, ScanSummary, LanguageProfile
from codeguard.language_detection import detect_languages
from codeguard.scanners.base import BaseScannerAdapter
from codeguard.scanners.semgrep import SemgrepAdapter
from codeguard.scanners.bandit import BanditAdapter
from codeguard.scanners.eslint import ESLintAdapter
from codeguard.scanners.gitleaks import GitleaksAdapter
from codeguard.scanners.builtin_rules import BuiltinRulesScanner
from codeguard.findings import normalize_and_deduplicate
from codeguard.triage import prioritize_findings
from codeguard.storage import StorageManager


class ScanOrchestrator:
    def __init__(self, storage_manager: Optional[StorageManager] = None):
        self.storage = storage_manager or StorageManager()
        self.scanners: List[BaseScannerAdapter] = [
            SemgrepAdapter(),
            BanditAdapter(),
            ESLintAdapter(),
            GitleaksAdapter(),
            BuiltinRulesScanner(),
        ]

    def scan_target(self, target_path: str, config: Optional[Dict[str, Any]] = None) -> ScanSummary:
        start_t = time.perf_counter()
        abs_target = Path(target_path).resolve()

        # 1. Language and workspace detection
        profile: LanguageProfile = detect_languages(str(abs_target))
        langs = set(profile.detected_languages)

        raw_findings: List[Finding] = []
        scanners_run: List[str] = []
        scanners_unavailable: List[str] = []

        for scanner in self.scanners:
            # Check if scanner supports any detected language or generic
            applicable = any(l in langs or l == "generic" for l in scanner.supported_languages)
            if not applicable:
                continue

            if scanner.is_available():
                scanners_run.append(scanner.name)
                try:
                    res = scanner.scan(str(abs_target), config)
                    raw_findings.extend(res)
                except Exception as e:
                    # Log / record scanner failure without aborting others
                    pass
            else:
                scanners_unavailable.append(scanner.name)

        # 2. Finding Normalization & Deduplication
        deduped = normalize_and_deduplicate(raw_findings)

        # 3. Deterministic Triage
        triaged = prioritize_findings(deduped)

        elapsed_ms = round((time.perf_counter() - start_t) * 1000.0, 2)

        # 4. Summary counts
        by_sev = {s: 0 for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]}
        by_tool: Dict[str, int] = {}
        for f in triaged:
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
            by_tool[f.tool] = by_tool.get(f.tool, 0) + 1

        scan_id = f"SCAN-{uuid.uuid4().hex[:8]}"

        summary = ScanSummary(
            workspace_path=str(abs_target),
            total_findings=len(triaged),
            by_severity=by_sev,
            by_tool=by_tool,
            scanners_run=scanners_run,
            scanners_unavailable=scanners_unavailable,
            languages_detected=profile.detected_languages,
            duration_ms=elapsed_ms,
            findings=triaged
        )

        # 5. Persist scan in SQLite history
        try:
            self.storage.record_scan(scan_id, str(abs_target), triaged, elapsed_ms)
        except Exception:
            pass

        return summary
