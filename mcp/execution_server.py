"""
Host Execution MCP Server

Sandboxed shell runner for pytest and mypy.
Returns full stdout/stderr to the requesting agent.

In a production deployment this becomes a proper sandboxed MCP server.
"""
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("mcp.execution")


@dataclass
class ExecResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0

    @property
    def combined(self) -> str:
        return (self.stdout + "\n" + self.stderr).strip()


class ExecutionServer:
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir

    def run_pytest_collect(self, test_file: str) -> ExecResult:
        """Validate test syntax without running any tests."""
        return self._run([sys.executable, "-m", "pytest", "--collect-only", "-q", test_file])

    def run_pytest(self, test_file: str, verbose: bool = True) -> ExecResult:
        """Run the full test suite and return results."""
        flags = ["-v"] if verbose else ["-q"]
        return self._run([sys.executable, "-m", "pytest"] + flags + [test_file])

    def run_mypy(self, source_file: str) -> ExecResult:
        """Run mypy static type checking on a Python file."""
        return self._run([sys.executable, "-m", "mypy", "--strict", source_file])

    # ── Private ───────────────────────────────────────────────────────────────

    def _run(self, cmd: list[str]) -> ExecResult:
        logger.debug(f"exec: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.working_dir),
        )
        logger.debug(f"exit {result.returncode}")
        return ExecResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
