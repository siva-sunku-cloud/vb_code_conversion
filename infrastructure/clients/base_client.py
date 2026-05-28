"""
Base MCP Client

Async context manager that spawns an MCP server subprocess and connects to it
via the stdio transport. Subclasses set `server_script` and add typed methods.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from utils.logger import get_logger

# Project root — injected into PYTHONPATH for server subprocesses so they can
# import config, utils, etc. even when launched from a different cwd.
_PROJECT_ROOT = str(Path(__file__).parent.parent.parent)


class BaseMCPClient:
    """Async context manager that owns the lifecycle of one MCP server process."""

    server_script: str  # absolute path to the server script; set by each subclass

    def __init__(self, *server_args: str) -> None:
        self._server_args = list(server_args)
        self.logger = get_logger(self.__class__.__name__)
        self._stdio_cm: Any = None
        self._session_cm: Any = None
        self.session: ClientSession | None = None

    async def __aenter__(self) -> BaseMCPClient:
        env = {**os.environ, "PYTHONPATH": _PROJECT_ROOT}
        params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script] + self._server_args,
            env=env,
        )
        self._stdio_cm = stdio_client(params)
        read, write = await self._stdio_cm.__aenter__()

        self._session_cm = ClientSession(read, write)
        self.session = await self._session_cm.__aenter__()
        await self.session.initialize()

        self.logger.info(f"Connected → {Path(self.server_script).name}")
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._session_cm is not None:
            await self._session_cm.__aexit__(*exc_info)
        if self._stdio_cm is not None:
            await self._stdio_cm.__aexit__(*exc_info)

    async def _call(self, tool: str, **kwargs: Any) -> str:
        """Call an MCP tool and return the first text content block."""
        assert self.session is not None, "Client is not connected — use async with"
        try:
            result = await asyncio.wait_for(self.session.call_tool(tool, kwargs), timeout=180.0)
        except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
            # Python 3.8 wait_for bug: CancelledError can leak out instead of TimeoutError.
            # Re-raise as TimeoutError (subclass of Exception) so callers see a consistent type.
            raise asyncio.TimeoutError(f"MCP tool call timed out: {tool}") from exc
        if not result.content:
            return ""
        return result.content[0].text or ""  # type: ignore[union-attr]
