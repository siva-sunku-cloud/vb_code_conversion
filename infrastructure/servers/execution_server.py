"""
Execution MCP Server

Sandboxed runner for pytest and mypy. Returns structured JSON results.
Start: python infrastructure/servers/execution_server.py <working_dir>
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

server = Server("vb2py-execution")

_working_dir: Path = Path(".").resolve()


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="run_pytest_collect",
            description="Check Python syntax of a test file using py_compile (no imports required).",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_file": {"type": "string", "description": "Path to the pytest test file"},
                },
                "required": ["test_file"],
            },
        ),
        types.Tool(
            name="run_pytest",
            description="Run the full pytest test suite and return stdout/stderr/returncode.",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_file": {"type": "string"},
                    "verbose": {"type": "boolean", "default": True},
                },
                "required": ["test_file"],
            },
        ),
        types.Tool(
            name="run_mypy",
            description="Run mypy --strict on a Python source file and return type-check results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_file": {"type": "string", "description": "Path to the Python file to check"},
                },
                "required": ["source_file"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    args = arguments or {}

    if name == "run_pytest_collect":
        # Use py_compile for syntax-only check — no imports executed, so missing
        # application modules don't cause a false ImportError at this stage.
        result = _run([sys.executable, "-m", "py_compile", args["test_file"]])
        if result["returncode"] == 0:
            result["stdout"] = f"Syntax OK: {args['test_file']}"
        return [types.TextContent(type="text", text=json.dumps(result))]

    if name == "run_pytest":
        flags = ["-v"] if args.get("verbose", True) else ["-q"]
        result = _run([sys.executable, "-m", "pytest"] + flags + [args["test_file"]])
        return [types.TextContent(type="text", text=json.dumps(result))]

    if name == "run_mypy":
        result = _run([sys.executable, "-m", "mypy", "--strict", args["source_file"]])
        return [types.TextContent(type="text", text=json.dumps(result))]

    raise ValueError(f"Unknown tool: {name}")


def _run(cmd: list[str]) -> dict:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(_working_dir),
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


async def main() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="vb2py-execution",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _working_dir = Path(sys.argv[1]).resolve()
    asyncio.run(main())
