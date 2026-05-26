"""
File System MCP Server

Wraps all file I/O for the pipeline.  In a full deployment this would be a
proper MCP server (modelcontextprotocol/server-filesystem).  Here we expose
the same operations as plain Python methods so agents can call them directly
and the interface can be swapped for a real MCP client later.
"""
import json
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger("mcp.filesystem")


class FileSystemServer:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ── Read ──────────────────────────────────────────────────────────────────

    def read_text(self, path: str | Path) -> str:
        full = self._resolve(path)
        logger.debug(f"read  {full}")
        return full.read_text(encoding="utf-8")

    def list_files(self, pattern: str = "**/*") -> list[str]:
        return [str(p) for p in self.base_dir.glob(pattern) if p.is_file()]

    # ── Write ─────────────────────────────────────────────────────────────────

    def write_text(self, path: str | Path, content: str) -> str:
        full = self._resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        logger.debug(f"wrote {full}")
        return str(full)

    def write_json(self, path: str | Path, data: dict) -> str:
        return self.write_text(path, json.dumps(data, indent=2))

    def read_json(self, path: str | Path) -> dict:
        return json.loads(self.read_text(path))

    # ── VB discovery ─────────────────────────────────────────────────────────

    def find_vb_files(self, source_dir: Path) -> list[Path]:
        exts = {".vb", ".bas", ".cls", ".frm", ".vbs"}
        return [p for p in source_dir.rglob("*") if p.suffix.lower() in exts]

    # ── Private ───────────────────────────────────────────────────────────────

    def _resolve(self, path: str | Path) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.base_dir / p
        return p
