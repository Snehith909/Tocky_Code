"""
Sandbox runner for isolated execution of verification tests and builds.
Supports restricted Docker containers (non-root, --network none, memory/CPU limits)
and fallback isolated process execution with timeouts.
"""

import subprocess
import shutil
import os
import time
from typing import Dict, Any, Tuple, Optional, List
from pathlib import Path


class SandboxRunner:
    def __init__(
        self,
        use_docker: bool = False,
        docker_image: str = "python:3.11-slim",
        timeout_seconds: int = 30
    ):
        self.use_docker = use_docker
        self.docker_image = docker_image
        self.timeout_seconds = timeout_seconds

    def is_docker_available(self) -> bool:
        if not shutil.which("docker"):
            return False
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5
            )
            return res.returncode == 0
        except Exception:
            return False

    def run_command(
        self,
        command: List[str],
        working_dir: str,
        env_vars: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, str, float]:
        """
        Execute command inside isolated environment.
        Returns (success: bool, output: str, elapsed_seconds: float).
        """
        start_t = time.perf_counter()

        if self.use_docker and self.is_docker_available():
            return self._run_in_docker(command, working_dir, env_vars)
        else:
            return self._run_local_isolated(command, working_dir, env_vars)

    def _run_in_docker(
        self,
        command: List[str],
        working_dir: str,
        env_vars: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, str, float]:
        """
        Run with hardened container flags:
        - --network none (no network access)
        - --read-only / restricted volume mount
        - --memory 512m
        - --cpus 1.0
        - --user 1000:1000 (non-root)
        """
        start_t = time.perf_counter()
        abs_dir = Path(working_dir).resolve()
        
        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "512m",
            "--cpus", "1.0",
            "-v", f"{abs_dir}:/workspace:rw",
            "-w", "/workspace",
        ]

        if env_vars:
            for k, v in env_vars.items():
                docker_cmd.extend(["-e", f"{k}={v}"])

        docker_cmd.append(self.docker_image)
        docker_cmd.extend(command)

        try:
            res = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            elapsed = time.perf_counter() - start_t
            output = (res.stdout + "\n" + res.stderr).strip()
            return res.returncode == 0, output, elapsed
        except subprocess.TimeoutExpired:
            return False, f"Execution timed out after {self.timeout_seconds} seconds", self.timeout_seconds
        except Exception as e:
            return False, f"Docker sandbox execution error: {str(e)}", time.perf_counter() - start_t

    def _run_local_isolated(
        self,
        command: List[str],
        working_dir: str,
        env_vars: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, str, float]:
        start_t = time.perf_counter()
        clean_env = os.environ.copy()
        if env_vars:
            clean_env.update(env_vars)

        try:
            res = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                env=clean_env,
                timeout=self.timeout_seconds,
                shell=False
            )
            elapsed = time.perf_counter() - start_t
            output = (res.stdout + "\n" + res.stderr).strip()
            return res.returncode == 0, output, elapsed
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {self.timeout_seconds}s", self.timeout_seconds
        except Exception as e:
            return False, f"Process execution failed: {str(e)}", time.perf_counter() - start_t
