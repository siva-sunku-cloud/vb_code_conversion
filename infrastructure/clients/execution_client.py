"""
Execution MCP Client

Typed async wrapper around the vb2py-execution MCP server.
Also owns the ExecResult dataclass used by MypyChecker, PytestRunner,
and DryRunRunner.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from infrastructure.clients.base_client import BaseMCPClient

_SERVER = str(Path(__file__).parent.parent / "servers" / "execution_server.py")


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


class ExecutionClient(BaseMCPClient):
    server_script = _SERVER

    def __init__(self, working_dir: str | Path) -> None:
        super().__init__(str(working_dir))

    async def run_pytest_collect(self, test_file: str) -> ExecResult:
        raw = await self._call("run_pytest_collect", test_file=test_file)
        return ExecResult(**json.loads(raw))

    async def run_pytest(self, test_file: str, verbose: bool = True) -> ExecResult:
        raw = await self._call("run_pytest", test_file=test_file, verbose=verbose)
        return ExecResult(**json.loads(raw))

    async def run_mypy(self, source_file: str) -> ExecResult:
        try:
            raw = await self._call("run_mypy", source_file=source_file)
            return ExecResult(**json.loads(raw))
        except asyncio.TimeoutError:
            return ExecResult(returncode=-1, stdout="", stderr="mypy timed out")
