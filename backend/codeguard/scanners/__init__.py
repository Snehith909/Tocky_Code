"""
Scanner adapters module for CodeGuard AI.
"""

from codeguard.scanners.base import BaseScannerAdapter
from codeguard.scanners.semgrep import SemgrepAdapter
from codeguard.scanners.bandit import BanditAdapter
from codeguard.scanners.eslint import ESLintAdapter
from codeguard.scanners.gitleaks import GitleaksAdapter
from codeguard.scanners.builtin_rules import BuiltinRulesScanner

__all__ = [
    "BaseScannerAdapter",
    "SemgrepAdapter",
    "BanditAdapter",
    "ESLintAdapter",
    "GitleaksAdapter",
    "BuiltinRulesScanner",
]
