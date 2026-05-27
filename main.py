#!/usr/bin/env python3
"""
Java → Python Migration Orchestrator
CLI entry point.
"""
import asyncio
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from agents.hub_agent import HubAgent
from models.migration_state import MigrationRequest
from utils.logger import setup_logging

app = typer.Typer(
    name="java2py",
    help="Java → Python Migration Orchestrator — Hub & Spoke Architecture",
    add_completion=False,
)
console = Console()

_DEFAULT_OUTPUT = Path.home() / "output"


@app.command()
def migrate(
    source_dir: Path = typer.Argument(..., help="Directory containing .java source files"),
    output_dir: Path = typer.Option(_DEFAULT_OUTPUT, "--out", "-o", help="Directory for generated Python output"),
    max_retries: int = typer.Option(3, "--retries", "-r", help="Max self-correction cycles in Step 3"),
    log_level: str = typer.Option("", "--log-level", "-l", help="Log level: DEBUG | INFO | WARNING | ERROR (default: DEBUG)"),
):
    """
    Run the full Java → Python migration pipeline on SOURCE_DIR.

    The pipeline has three steps, each with a mandatory human review gate:

      Step 1 — Discovery, Documentation & Architecture  → Human gate
      Step 2 — Test-Driven Development (parallel)       → Human gate
      Step 3 — Conversion & Closed-Loop Execution       → Human gate

    Results are written to OUTPUT_DIR/<module_name>/. Defaults to ~/output.
    """
    if log_level:
        os.environ["LOG_LEVEL"] = log_level.upper()

    setup_logging()

    console.print(Panel.fit(
        "[bold blue]Java → Python Migration Orchestrator[/bold blue]\n"
        "[dim]Hub & Spoke · Test-Driven · MCP Infrastructure[/dim]",
        border_style="blue",
    ))

    request = MigrationRequest(
        source_dir=source_dir.resolve(),
        output_dir=output_dir.resolve(),
        max_retries=max_retries,
    )

    asyncio.run(_run(request))


async def _run(request: MigrationRequest) -> None:
    hub = HubAgent()
    await hub.run(request)


if __name__ == "__main__":
    app()
