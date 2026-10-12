"""
Scanner adapters module for CodeGuard AI.
Includes cross-language, language-specific, secret, dependency, and C/C++ analyzers.
"""

from codeguard.scanners.base import BaseScannerAdapter
from codeguard.scanners.semgrep import SemgrepAdapter
from codeguard.scanners.bandit import BanditAdapter
from codeguard.scanners.eslint import ESLintAdapter
from codeguard.scanners.gitleaks import GitleaksAdapter
from codeguard.scanners.builtin_rules import BuiltinRulesScanner
from codeguard.scanners.dependency_audit import DependencyAuditAdapter
from codeguard.scanners.cppcheck import CppcheckAdapter

__all__ = [
    "BaseScannerAdapter",
    "SemgrepAdapter",
    "BanditAdapter",
    "ESLintAdapter",
    "GitleaksAdapter",
    "BuiltinRulesScanner",
    "DependencyAuditAdapter",
    "CppcheckAdapter",
]
