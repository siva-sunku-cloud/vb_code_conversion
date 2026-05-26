#!/usr/bin/env python3
"""
VB → Python Migration Orchestrator
CLI entry point.
"""
import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from agents.hub_agent import HubAgent
from models.migration_state import MigrationRequest
from utils.logger import setup_logging

app = typer.Typer(
    name="vb2py",
    help="VB → Python Migration Orchestrator — Hub & Spoke Architecture",
    add_completion=False,
)
console = Console()


@app.command()
def migrate(
    source_dir: Path = typer.Argument(..., help="Directory containing .vb / .bas / .cls source files"),
    output_dir: Path = typer.Option(Path("./output"), "--out", "-o", help="Directory for generated Python output"),
    max_retries: int = typer.Option(3, "--retries", "-r", help="Max self-correction cycles in Step 3"),
    complexity_threshold: float = typer.Option(
        0.7, "--threshold", "-t",
        help="Complexity score (0-1) above which the human gate is triggered",
    ),
):
    """
    Run the full VB → Python migration pipeline on SOURCE_DIR.

    The pipeline has three steps:

      Step 1 — Discovery, Documentation & Architecture
      Step 2 — Test-Driven Development (parallel test generation)
      Step 3 — Conversion & Closed-Loop Execution

    Results are written to OUTPUT_DIR/<module_name>/.
    """
    setup_logging()

    console.print(Panel.fit(
        "[bold blue]VB → Python Migration Orchestrator[/bold blue]\n"
        "[dim]Hub & Spoke · Test-Driven · MCP Infrastructure[/dim]",
        border_style="blue",
    ))

    request = MigrationRequest(
        source_dir=source_dir.resolve(),
        output_dir=output_dir.resolve(),
        max_retries=max_retries,
        complexity_threshold=complexity_threshold,
    )

    asyncio.run(_run(request))


async def _run(request: MigrationRequest) -> None:
    hub = HubAgent()
    await hub.run(request)


if __name__ == "__main__":
    app()
