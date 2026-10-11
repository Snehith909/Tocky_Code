"""
Data models for CodeGuard AI.
Standardized finding schema, patch proposal, verification states, and scan summaries.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any
import hashlib
import json


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    @classmethod
    def from_str(cls, val: str) -> Severity:
        v = (val or "").upper()
        if "CRIT" in v:
            return cls.CRITICAL
        elif "HIGH" in v or "ERROR" in v:
            return cls.HIGH
        elif "MED" in v or "WARN" in v:
            return cls.MEDIUM
        elif "LOW" in v:
            return cls.LOW
        return cls.INFO


class FindingStatus(str, Enum):
    OPEN = "OPEN"
    PATCH_PROPOSED = "PATCH_PROPOSED"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED_BY_USER = "REJECTED_BY_USER"
    VERIFICATION_RUNNING = "VERIFICATION_RUNNING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NOT_RUN = "NOT_RUN"


@dataclass
class Finding:
    id: str
    tool: str
    rule_id: str
    language: str
    file: str
    start_line: int
    end_line: int
    severity: str
    message: str
    evidence: str
    fingerprint: str = ""
    status: str = FindingStatus.OPEN.value
    start_col: Optional[int] = None
    end_col: Optional[int] = None
    cwe: Optional[str] = None
    help_uri: Optional[str] = None
    confidence: Optional[str] = None
    raw_details: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.fingerprint:
            # Deterministic fingerprint based on rule, file, and line content
            content = f"{self.tool}:{self.rule_id}:{self.file}:{self.start_line}:{self.evidence.strip()}"
            self.fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Finding:
        return cls(
            id=data.get("id", ""),
            tool=data.get("tool", ""),
            rule_id=data.get("rule_id", ""),
            language=data.get("language", ""),
            file=data.get("file", ""),
            start_line=int(data.get("start_line", 1)),
            end_line=int(data.get("end_line", 1)),
            severity=data.get("severity", "MEDIUM"),
            message=data.get("message", ""),
            evidence=data.get("evidence", ""),
            fingerprint=data.get("fingerprint", ""),
            status=data.get("status", FindingStatus.OPEN.value),
            start_col=data.get("start_col"),
            end_col=data.get("end_col"),
            cwe=data.get("cwe"),
            help_uri=data.get("help_uri"),
            confidence=data.get("confidence"),
            raw_details=data.get("raw_details"),
        )


@dataclass
class PatchProposal:
    id: str
    finding_id: str
    target_file: str
    diff: str
    explanation: str
    provider: str
    model: str
    status: str = FindingStatus.AWAITING_REVIEW.value
    approved_by_user: bool = False
    verification_status: str = FindingStatus.NOT_RUN.value
    original_snippet: str = ""
    replacement_snippet: str = ""
    start_line: int = 1
    end_line: int = 1
    tokens_used: Dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PatchProposal:
        return cls(
            id=data.get("id", ""),
            finding_id=data.get("finding_id", ""),
            target_file=data.get("target_file", ""),
            diff=data.get("diff", ""),
            explanation=data.get("explanation", ""),
            provider=data.get("provider", "mock"),
            model=data.get("model", "default"),
            status=data.get("status", FindingStatus.AWAITING_REVIEW.value),
            approved_by_user=bool(data.get("approved_by_user", False)),
            verification_status=data.get("verification_status", FindingStatus.NOT_RUN.value),
            original_snippet=data.get("original_snippet", ""),
            replacement_snippet=data.get("replacement_snippet", ""),
            start_line=int(data.get("start_line", 1)),
            end_line=int(data.get("end_line", 1)),
            tokens_used=data.get("tokens_used", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            latency_ms=float(data.get("latency_ms", 0.0)),
        )


@dataclass
class VerificationCheck:
    name: str
    check_type: str  # "rescan", "test", "build", "syntax"
    passed: bool
    details: str
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationResult:
    patch_id: str
    finding_id: str
    status: str  # VERIFIED, REJECTED, NEEDS_REVIEW
    rescan_passed: bool
    tests_passed: bool
    tests_run: bool
    details: str
    checks_executed: List[VerificationCheck] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "finding_id": self.finding_id,
            "status": self.status,
            "rescan_passed": self.rescan_passed,
            "tests_passed": self.tests_passed,
            "tests_run": self.tests_run,
            "details": self.details,
            "checks_executed": [c.to_dict() for c in self.checks_executed],
            "elapsed_seconds": self.elapsed_seconds,
        }


@dataclass
class LanguageProfile:
    detected_languages: List[str]
    manifest_files: List[str]
    primary_language: Optional[str] = None
    configured_scanners: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScanSummary:
    workspace_path: str
    total_findings: int
    by_severity: Dict[str, int]
    by_tool: Dict[str, int]
    scanners_run: List[str]
    scanners_unavailable: List[str]
    languages_detected: List[str]
    duration_ms: float
    findings: List[Finding]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_path": self.workspace_path,
            "total_findings": self.total_findings,
            "by_severity": self.by_severity,
            "by_tool": self.by_tool,
            "scanners_run": self.scanners_run,
            "scanners_unavailable": self.scanners_unavailable,
            "languages_detected": self.languages_detected,
            "duration_ms": self.duration_ms,
            "findings": [f.to_dict() for f in self.findings],
        }
