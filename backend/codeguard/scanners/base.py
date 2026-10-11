"""
Base scanner adapter interface for CodeGuard AI.
Adheres to scanner adapter contract: availability check, supported languages,
scan execution, machine-readable output parsing, and failure reporting.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path
import shutil
from codeguard.models import Finding


class BaseScannerAdapter(ABC):
    name: str = "base"
    supported_languages: List[str] = []

    def __init__(self, executable_path: Optional[str] = None):
        self.executable_path = executable_path

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the underlying scanner binary or runtime is available."""
        pass

    @abstractmethod
    def scan(self, target_path: str, config: Optional[Dict[str, Any]] = None) -> List[Finding]:
        """
        Execute scan on target path (file or workspace directory) and return normalized findings.
        Must not crash if scanner encounters syntax errors in target files.
        """
        pass

    @abstractmethod
    def parse_output(self, raw_output: str, target_path: str) -> List[Finding]:
        """Parse raw scanner tool output (typically JSON) into normalized Finding list."""
        pass

    def resolve_executable(self, default_name: str) -> Optional[str]:
        """Find executable in PATH or explicit configured path."""
        if self.executable_path and Path(self.executable_path).exists():
            return self.executable_path
        found = shutil.which(default_name)
        return found
