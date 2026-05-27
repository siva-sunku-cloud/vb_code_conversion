#!/usr/bin/env python3
"""
Java → Python Migration Orchestrator
CLI entry point.
"""
import asyncio
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from agents.hub_agent import HubAgent
from config import Config
from models.migration_state import MigrationRequest
from utils.logger import setup_logging

app = typer.Typer(
    name="java2py",
    help="Java → Python Migration Orchestrator — Hub & Spoke Architecture",
    add_completion=False,
)
console = Console()


@app.command()
def migrate(
    source_dir: Path = typer.Argument(..., help="Directory containing .java source files"),
    output_dir: Optional[Path] = typer.Option(None, "--out", "-o", help="Output directory (default: DATA_FOLDER/<source_dir_name>)"),
    max_retries: int = typer.Option(3, "--retries", "-r", help="Max self-correction cycles in Step 3"),
    log_level: str = typer.Option("", "--log-level", "-l", help="Log level: DEBUG | INFO | WARNING | ERROR (default: DEBUG)"),
    start_step: str = typer.Option("1a", "--start-step", "-s", help="Resume from step: 1a | 1b | 1c | 2 | 3"),
):
    """
    Run the full Java → Python migration pipeline on SOURCE_DIR.

    The pipeline has three steps, each with a mandatory human review gate:

      Step 1 — Discovery, Documentation & Architecture  → Human gate
        1a: Understand · 1b: Document · 1c: Architect
      Step 2 — Test-Driven Development (parallel)       → Human gate
      Step 3 — Conversion & Closed-Loop Execution       → Human gate

    Results are written to DATA_FOLDER/<source_dir_name>/<module_name>/ by default.
    DATA_FOLDER is configured in config.py (default: ~/data_code_conversion).
    Override the output location with --out.
    Use --start-step to resume a partial run (e.g. --start-step 1c skips Understand & Document).
    """
    valid_steps = {"1a", "1b", "1c", "2", "3"}
    if start_step not in valid_steps:
        console.print(f"[red]Invalid --start-step '{start_step}'. Choose from: {', '.join(sorted(valid_steps))}[/red]")
        raise typer.Exit(1)

    if log_level:
        os.environ["LOG_LEVEL"] = log_level.upper()

    setup_logging()

    resolved_source = source_dir.resolve()
    resolved_output = (
        output_dir.resolve()
        if output_dir is not None
        else Path(Config.DATA_FOLDER) / resolved_source.name
    )

    console.print(Panel.fit(
        "[bold blue]Java → Python Migration Orchestrator[/bold blue]\n"
        "[dim]Hub & Spoke · Test-Driven · MCP Infrastructure[/dim]",
        border_style="blue",
    ))

    request = MigrationRequest(
        source_dir=resolved_source,
        output_dir=resolved_output,
        max_retries=max_retries,
        start_step=start_step,
    )

    asyncio.run(_run(request))


async def _run(request: MigrationRequest) -> None:
    hub = HubAgent()
    await hub.run(request)


if __name__ == "__main__":
    app()
