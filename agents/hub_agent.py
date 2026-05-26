"""
Hub Agent — Central Orchestrator

Maintains global migration state and dispatches tasks through the three-step
pipeline:
  Step 1 — Discovery, Documentation & Architecture
  Step 2 — Test-Driven Development (parallel generation)
  Step 3 — Conversion & Closed-Loop Execution

Escalates to the CLI when human judgment is required (complexity gate,
architecture rejection, or exhausted retry budget).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt

from config import Config
from models.migration_state import (
    GlobalMigrationState,
    ModuleState,
    ModuleStatus,
    MigrationRequest,
)
from models.artifacts import (
    AnalysisResult,
    MarkdownSpec,
    ArchitectureDesign,
    TestSuite,
    ConversionResult,
)
from state.migration_manager import MigrationManager

from agents.step1.understand_agent import UnderstandAgent
from agents.step1.document_agent import DocumentAgent
from agents.step1.architect_agent import ArchitectAgent
from agents.step1.ast_checker import ASTChecker
from agents.step1.arch_auditor import ArchAuditor

from agents.step2.functional_tests_agent import FunctionalTestsAgent
from agents.step2.golden_master_agent import GoldenMasterAgent
from agents.step2.test_auditor import TestAuditor
from agents.step2.dry_run_runner import DryRunRunner

from agents.step3.converter_agent import ConverterAgent
from agents.step3.mypy_checker import MypyChecker
from agents.step3.pytest_runner import PytestRunner

from mcp.filesystem_server import FileSystemServer
from mcp.execution_server import ExecutionServer
from mcp.vectordb_server import VectorDBServer
from mcp.github_server import GitHubServer

from utils.logger import get_logger

logger = get_logger("HubAgent")
console = Console()


class HubAgent:
    """Hub / Orchestrator — the single source of truth for the migration pipeline."""

    def __init__(self):
        self.fs: FileSystemServer | None = None
        self.executor: ExecutionServer | None = None
        self.vectordb = VectorDBServer(use_memory=True)
        self.github = GitHubServer()
        self.manager: MigrationManager | None = None

    # ══════════════════════════════════════════════════════════════════════════
    # Public entry point
    # ══════════════════════════════════════════════════════════════════════════

    async def run(self, request: MigrationRequest) -> None:
        self._init_infra(request)
        assert self.fs and self.executor and self.manager

        console.print(Panel.fit(
            f"[bold]Source:[/bold] {request.source_dir}\n"
            f"[bold]Output:[/bold] {request.output_dir}\n"
            f"[bold]Max retries:[/bold] {request.max_retries}  "
            f"[bold]Complexity gate:[/bold] {request.complexity_threshold}",
            title="[bold blue]Migration Request[/bold blue]",
        ))

        # Discover VB files
        vb_files = self.fs.find_vb_files(request.source_dir)
        if not vb_files:
            console.print("[yellow]No VB files found. Exiting.[/yellow]")
            return

        console.print(f"\nFound [bold]{len(vb_files)}[/bold] VB file(s) to migrate.\n")

        # Register modules in global state
        for f in vb_files:
            name = f.stem
            self.manager.state.vb_source_files.append(str(f))
            self.manager.state.modules[name] = ModuleState(
                name=name, vb_file_path=str(f)
            )

        # Process each module sequentially (parallelise if needed)
        for module_state in list(self.manager.state.modules.values()):
            await self._process_module(module_state, request)

        # Final summary
        s = self.manager.state
        console.print(Panel.fit(
            f"[green]Completed: {s.completed_modules}[/green]  "
            f"[red]Failed: {s.failed_modules}[/red]  "
            f"[dim]Total: {len(s.modules)}[/dim]",
            title="[bold]Migration Complete[/bold]",
        ))

    # ══════════════════════════════════════════════════════════════════════════
    # Per-module pipeline
    # ══════════════════════════════════════════════════════════════════════════

    async def _process_module(
        self, module_state: ModuleState, request: MigrationRequest
    ) -> None:
        assert self.fs and self.executor and self.manager
        name = module_state.name
        console.rule(f"[bold cyan]Module: {name}[/bold cyan]")

        try:
            vb_source = self.fs.read_text(module_state.vb_file_path)

            # ── Step 1 ────────────────────────────────────────────────────────
            analysis, spec, design = await self._step1(name, vb_source, module_state.vb_file_path, request)

            # ── Step 2 ────────────────────────────────────────────────────────
            test_suite = await self._step2(name, spec, design, request)

            # ── Step 3 ────────────────────────────────────────────────────────
            await self._step3(name, design, test_suite, request)

        except HumanRejectionError:
            self.manager.update_module_status(name, ModuleStatus.FAILED, "Rejected at human gate")
            console.print(f"[red]Module {name} rejected by human reviewer.[/red]")
        except Exception as exc:
            logger.exception(f"Unhandled error for module {name}")
            self.manager.update_module_status(name, ModuleStatus.FAILED, str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # Step 1 — Discovery, Documentation & Architecture
    # ══════════════════════════════════════════════════════════════════════════

    async def _step1(
        self,
        name: str,
        vb_source: str,
        vb_file_path: str,
        request: MigrationRequest,
    ) -> tuple[AnalysisResult, MarkdownSpec, ArchitectureDesign]:
        assert self.fs and self.manager
        self.manager.update_module_status(name, ModuleStatus.ANALYZING)

        # 1-A: Understand
        console.print("  [cyan]Step 1-A[/cyan] Understanding VB module…")
        analysis = UnderstandAgent().run(vb_source, name, vb_file_path)

        # Validation A: AST check
        ast_result = ASTChecker().check(vb_source, analysis)
        if not ast_result.passed:
            for issue in ast_result.issues:
                console.print(f"    [yellow]⚠ AST:[/yellow] {issue}")

        # 1-B: Document
        console.print("  [cyan]Step 1-B[/cyan] Writing Markdown spec…")
        spec_path = str(request.output_dir / name / f"{name}_spec.md")
        spec = DocumentAgent().run(analysis, spec_path)
        self.fs.write_text(spec_path, spec.content)
        self.manager.add_artifact(name, "spec", spec_path)
        self.manager.update_module_status(name, ModuleStatus.DOCUMENTED)

        # 1-C: Architect
        console.print("  [cyan]Step 1-C[/cyan] Designing Python architecture…")
        arch_path = str(request.output_dir / name / f"{name}_architecture.json")
        design = ArchitectAgent().run(analysis, spec, arch_path)
        self.fs.write_json(arch_path, design.model_dump())
        self.manager.add_artifact(name, "architecture", arch_path)

        # Validation B: Architecture audit
        console.print("  [cyan]Step 1 Audit[/cyan] Reviewing architecture…")
        audit_result = ArchAuditor().check(design)
        if not audit_result.passed:
            for issue in audit_result.issues:
                console.print(f"    [red]✗ Arch:[/red] {issue}")

        # Human gate — triggered when complexity is high
        if analysis.complexity_score >= request.complexity_threshold or not audit_result.passed:
            approved = self._human_gate(name, analysis, design, audit_result.issues)
            if not approved:
                raise HumanRejectionError(name)

        self.manager.update_module_status(name, ModuleStatus.ARCHITECTED)
        return analysis, spec, design

    # ══════════════════════════════════════════════════════════════════════════
    # Step 2 — Test-Driven Development (parallel)
    # ══════════════════════════════════════════════════════════════════════════

    async def _step2(
        self,
        name: str,
        spec: MarkdownSpec,
        design: ArchitectureDesign,
        request: MigrationRequest,
    ) -> TestSuite:
        assert self.fs and self.executor and self.manager

        console.print("  [magenta]Step 2[/magenta] Generating tests (parallel)…")

        func_path = str(request.output_dir / name / f"test_{name}_functional.py")
        gm_path = str(request.output_dir / name / f"test_{name}_golden.py")

        # Parallel: Functional Tests (2A) + Golden Master (2B)
        functional, golden = await asyncio.gather(
            asyncio.to_thread(FunctionalTestsAgent().run, spec, design, func_path),
            asyncio.to_thread(GoldenMasterAgent().run, spec, gm_path),
        )

        # Audit
        console.print("  [magenta]Step 2 Audit[/magenta] Reviewing test suites…")
        merged_path = str(request.output_dir / name / f"test_{name}.py")
        merged_suite = TestAuditor().audit(functional, golden, merged_path)
        self.fs.write_text(merged_path, merged_suite.test_code)
        self.manager.add_artifact(name, "test_suite", merged_path)

        # Dry run — validate syntax before any application code exists
        console.print("  [magenta]Step 2 Dry Run[/magenta] pytest --collect-only…")
        dry_result = DryRunRunner(self.executor).run(merged_suite)
        if not dry_result.passed:
            console.print(f"  [yellow]Dry run issues:[/yellow] {dry_result.issues[:3]}")

        self.manager.update_module_status(name, ModuleStatus.TESTS_GENERATED)
        return merged_suite

    # ══════════════════════════════════════════════════════════════════════════
    # Step 3 — Conversion & Closed-Loop Execution
    # ══════════════════════════════════════════════════════════════════════════

    async def _step3(
        self,
        name: str,
        design: ArchitectureDesign,
        test_suite: TestSuite,
        request: MigrationRequest,
    ) -> None:
        assert self.fs and self.executor and self.manager
        self.manager.update_module_status(name, ModuleStatus.CONVERTING)

        py_path = str(request.output_dir / name / f"{name}.py")
        previous_error: str | None = None

        for attempt in range(request.max_retries + 1):
            # Convert
            label = "initial" if attempt == 0 else f"retry {attempt}/{request.max_retries}"
            console.print(f"  [green]Step 3[/green] Converting ({label})…")

            conversion = ConverterAgent(self.vectordb).run(
                design, test_suite, py_path,
                previous_error=previous_error,
                retry_count=attempt,
            )
            self.fs.write_text(py_path, conversion.python_code)
            self.manager.add_artifact(name, "python_source", py_path)

            # mypy
            console.print("  [green]Step 3[/green] mypy check…")
            mypy_result = MypyChecker(self.executor).check(py_path, name)
            if not mypy_result.passed:
                console.print(f"    [yellow]mypy issues ({len(mypy_result.issues)}):[/yellow] "
                               f"{mypy_result.issues[:2]}")
                previous_error = f"mypy errors:\n{mypy_result.details}"
                self.manager.increment_retry(name)
                continue

            # pytest
            console.print("  [green]Step 3[/green] Running pytest…")
            test_result = PytestRunner(self.executor).run(test_suite.output_path, name)
            if test_result.passed:
                console.print(f"  [bold green]✓ {name} — all tests pass![/bold green]")
                self.manager.update_module_status(name, ModuleStatus.COMPLETED)
                self._on_success(name, design, conversion, test_result.details, request)
                return
            else:
                previous_error = test_result.details
                self.manager.increment_retry(name)
                console.print(
                    f"  [red]Tests failed (attempt {attempt + 1}/{request.max_retries + 1})[/red]"
                )

        # Exhausted retries → escalate to CLI
        console.print(f"  [bold red]✗ {name} — retry budget exhausted. Escalating to CLI.[/bold red]")
        self._escalate_to_cli(name, previous_error or "Unknown error")
        self.manager.update_module_status(name, ModuleStatus.FAILED, "Retry budget exhausted")

    # ══════════════════════════════════════════════════════════════════════════
    # Human-in-the-loop helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _human_gate(
        self,
        name: str,
        analysis: AnalysisResult,
        design: ArchitectureDesign,
        audit_issues: list[str],
    ) -> bool:
        console.print(Panel(
            f"[bold yellow]Human Gate triggered for module: {name}[/bold yellow]\n\n"
            f"Complexity score: [bold]{analysis.complexity_score:.2f}[/bold]\n"
            f"Architecture issues: {len(audit_issues)}\n"
            + ("\n".join(f"  • {i}" for i in audit_issues[:5])),
            title="[bold red]⚠ Human Review Required[/bold red]",
            border_style="red",
        ))
        return Confirm.ask("Approve this architecture and continue?")

    def _escalate_to_cli(self, name: str, error: str) -> None:
        console.print(Panel(
            f"Module [bold]{name}[/bold] failed after all retries.\n\n"
            f"Last error:\n[red]{error[:500]}[/red]",
            title="[bold red]Escalation — Human Intervention Needed[/bold red]",
            border_style="red",
        ))
        Prompt.ask("Press Enter to acknowledge and continue to the next module")

    # ══════════════════════════════════════════════════════════════════════════
    # Post-success: save to DB, create PR
    # ══════════════════════════════════════════════════════════════════════════

    def _on_success(
        self,
        name: str,
        design: ArchitectureDesign,
        conversion: ConversionResult,
        test_summary: str,
        request: MigrationRequest,
    ) -> None:
        # Store pattern in translation memory
        self.vectordb.store_pattern(
            vb_snippet=name,
            python_snippet=conversion.python_code[:500],
            description=f"Module: {name}",
        )

        # Create GitHub PR
        py_path = Path(conversion.output_path)
        pr_url = self.github.create_pr(
            module_name=name,
            python_file_path=py_path,
            python_code=conversion.python_code,
            test_results_summary=test_summary[:1000],
        )
        if pr_url:
            console.print(f"  [blue]PR created:[/blue] {pr_url}")

    # ══════════════════════════════════════════════════════════════════════════
    # Infrastructure initialisation
    # ══════════════════════════════════════════════════════════════════════════

    def _init_infra(self, request: MigrationRequest) -> None:
        request.output_dir.mkdir(parents=True, exist_ok=True)

        self.fs = FileSystemServer(request.output_dir)
        self.executor = ExecutionServer(request.output_dir)

        global_state = GlobalMigrationState(request=request)
        self.manager = MigrationManager(global_state)
        state_file = request.output_dir / "migration_state.json"
        self.manager.set_state_file(state_file)
        self.manager.log("Migration pipeline initialised")


class HumanRejectionError(Exception):
    """Raised when the human gate rejects an architecture."""
    pass
