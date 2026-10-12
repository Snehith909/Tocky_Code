#!/usr/bin/env python3
"""
CodeGuard AI CLI entrypoint.
Convenience runner so users can execute CodeGuard directly from the project root:
  python codeguard.py scan --target tests/fixtures
  python codeguard.py metrics
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from codeguard.cli import main

if __name__ == "__main__":
    main()
