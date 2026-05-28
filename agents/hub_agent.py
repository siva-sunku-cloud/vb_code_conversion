"""
Hub Agent — Central Orchestrator

Maintains global migration state and dispatches tasks through the three-step
pipeline:
  Step 1 — Discovery, Documentation & Architecture
  Step 2 — Test-Driven Development (parallel generation)
  Step 3 — Conversion & Closed-Loop Execution

Each infrastructure service runs as a real MCP server subprocess connected
via stdio transport. All four servers are kept alive for the full migration
run inside an AsyncExitStack.
"""
from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from config import Config
from models.migration_state import (
    GlobalMigrationState,
    MigrationRequest,
    ModuleState,
    ModuleStatus,
)
from models.artifacts import (
    AnalysisResult,
    ArchitectureDesign,
    ConversionResult,
    MarkdownSpec,
    TestSuite,
)
from state.migration_manager import MigrationManager

from agents.analyze_and_design.understand_agent import UnderstandAgent
from agents.analyze_and_design.document_agent import DocumentAgent
from agents.analyze_and_design.architect_agent import ArchitectAgent
from agents.analyze_and_design.ast_checker import ASTChecker
from agents.analyze_and_design.arch_auditor import ArchAuditor

from agents.build_test_execute.functional_tests_agent import FunctionalTestsAgent
from agents.build_test_execute.golden_master_agent import GoldenMasterAgent
from agents.build_test_execute.test_auditor import TestAuditor
from agents.build_test_execute.dry_run_runner import DryRunRunner

from agents.generate_code.converter_agent import ConverterAgent
from agents.generate_code.mypy_checker import MypyChecker
from agents.generate_code.pytest_runner import PytestRunner

from infrastructure.clients.filesystem_client import FilesystemClient
from infrastructure.clients.execution_client import ExecutionClient
from infrastructure.clients.vectordb_client import VectorDBClient
from infrastructure.clients.github_client import GitHubClient

from utils.logger import get_logger

logger = get_logger("HubAgent")
console = Console()


class HubAgent:
    """Hub / Orchestrator — the single source of truth for the migration pipeline."""

    def __init__(self) -> None:
        self.fs: FilesystemClient | None = None
        self.executor: ExecutionClient | None = None
        self.vectordb: VectorDBClient | None = None
        self.github: GitHubClient | None = None
        self.manager: MigrationManager | None = None

    # ══════════════════════════════════════════════════════════════════════════
    # Public entry point
    # ══════════════════════════════════════════════════════════════════════════

    async def run(self, request: MigrationRequest) -> None:
        request.output_dir.mkdir(parents=True, exist_ok=True)

        console.print(Panel.fit(
            f"[bold]Source:[/bold] {request.source_dir}\n"
            f"[bold]Output:[/bold] {request.output_dir}\n"
            f"[bold]Max retries:[/bold] {request.max_retries}\n"
            f"[bold]Human gates:[/bold] after every step (Step 1, Step 2, Step 3)",
            title="[bold blue]Migration Request[/bold blue]",
        ))

        # Start all four MCP server processes and keep them alive for the
        # entire migration run.
        async with AsyncExitStack() as stack:
            logger.debug(f"Starting MCP infrastructure services for output_dir={request.output_dir}")
            self.fs = await stack.enter_async_context(
                FilesystemClient(request.output_dir)
            )
            logger.debug("FilesystemClient started")
            self.executor = await stack.enter_async_context(
                ExecutionClient(request.output_dir)
            )
            logger.debug("ExecutionClient started")
            self.vectordb = await stack.enter_async_context(
                VectorDBClient(use_memory=True)
            )
            logger.debug("VectorDBClient started (in-memory)")
            self.github = await stack.enter_async_context(GitHubClient())
            logger.debug("GitHubClient started")

            # Initialise migration state
            global_state = GlobalMigrationState(request=request)
            self.manager = MigrationManager(global_state)
            self.manager.set_state_file(request.output_dir / "migration_state.json")
            self.manager.log("Migration pipeline initialised")
            logger.debug(f"State file: {request.output_dir / 'migration_state.json'}")

            # Discover VB files via the filesystem MCP server
            java_files = await self.fs.find_java_files(request.source_dir)
            if not java_files:
                console.print("[yellow]No Java files found. Exiting.[/yellow]")
                logger.warning(f"No Java files found in source_dir={request.source_dir}")
                return

            console.print(f"\nFound [bold]{len(java_files)}[/bold] Java file(s) to migrate.\n")
            logger.debug(f"Discovered {len(java_files)} Java files:")
            for f in java_files:
                logger.debug(f"  {f}")

            for f in java_files:
                name = f.stem
                self.manager.state.source_files.append(str(f))
                self.manager.state.modules[name] = ModuleState(
                    name=name, source_file_path=str(f)
                )

            logger.debug(f"Registered {len(self.manager.state.modules)} modules for migration")
            for module_state in list(self.manager.state.modules.values()):
                await self._process_module(module_state, request)

        # Final summary (printed after all servers have shut down cleanly)
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
        start = request.start_step
        console.rule(f"[bold cyan]Module: {name}[/bold cyan]")
        if start != "1a":
            console.print(f"  [dim]Resuming from step [bold]{start}[/bold][/dim]")

        try:
            logger.debug(f"[{name}] Reading source file: {module_state.source_file_path}")
            source_code = await self.fs.read_text(module_state.source_file_path)
            logger.debug(f"[{name}] Source loaded — {len(source_code.splitlines())} lines  {len(source_code)} chars")

            if start in ("1a", "1b", "1c"):
                analysis, spec, design = await self._analyze_and_design(
                    name, source_code, module_state.source_file_path, request
                )
                logger.debug(f"[{name}] Step 1 complete — proceeding to Step 2")
            else:
                analysis, spec, design = await self._load_step1_artifacts(name, request)
                logger.debug(f"[{name}] Step 1 skipped — artifacts loaded from disk")

            if start in ("1a", "1b", "1c", "2"):
                test_suite = await self._build_test_execute(name, spec, design, request)
                logger.debug(f"[{name}] Step 2 complete — proceeding to Step 3")
            else:
                test_suite = await self._load_test_suite(name, request)
                logger.debug(f"[{name}] Step 2 skipped — test suite loaded from disk")

            await self._generate_code(name, design, test_suite, request)
            logger.debug(f"[{name}] Step 3 complete")

        except HumanRejectionError:
            self.manager.update_module_status(name, ModuleStatus.FAILED, "Rejected at human gate")
            logger.warning(f"[{name}] Rejected at human gate")
            console.print(f"[red]Module {name} rejected by human reviewer.[/red]")
        except Exception as exc:
            logger.exception(f"Unhandled error for module {name}")
            self.manager.update_module_status(name, ModuleStatus.FAILED, str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # Step 1 — Discovery, Documentation & Architecture
    # ══════════════════════════════════════════════════════════════════════════

    async def _analyze_and_design(
        self,
        name: str,
        source_code: str,
        source_file_path: str,
        request: MigrationRequest,
    ) -> tuple[AnalysisResult, MarkdownSpec, ArchitectureDesign]:
        assert self.fs and self.manager
        start = request.start_step
        logger.debug(f"[{name}] Step 1 start — source_file={source_file_path}  start_step={start}")

        analysis_path = str(request.output_dir / name / f"{name}_analysis.json")
        spec_path     = str(request.output_dir / name / f"{name}_spec.md")
        arch_path     = str(request.output_dir / name / f"{name}_architecture.json")

        # ── 1-A: Understand ───────────────────────────────────────────────────
        if start == "1a":
            self.manager.update_module_status(name, ModuleStatus.ANALYZING)
            console.print("  [cyan]Step 1-A[/cyan] Understanding Java module…")
            analysis = UnderstandAgent().run(source_code, name, source_file_path)
            # Persist so later sub-steps can reload without re-running the LLM
            await self.fs.write_json(analysis_path, analysis.model_dump())
            self.manager.add_artifact(name, "analysis", analysis_path)
        else:
            console.print(f"  [dim]Step 1-A skipped — loading analysis from disk[/dim]")
            data = await self.fs.read_json(analysis_path)
            analysis = AnalysisResult(**data)

        # Validation A: AST check (always run — cheap, needed for human-gate summary)
        logger.debug(f"[{name}] Running AST checker")
        ast_result = ASTChecker().check(source_code, analysis)
        logger.debug(f"[{name}] AST check result: passed={ast_result.passed}  issues={len(ast_result.issues)}  warnings={len(ast_result.warnings)}")
        if not ast_result.passed:
            for issue in ast_result.issues:
                console.print(f"    [yellow]⚠ AST:[/yellow] {issue}")

        # ── 1-B: Document ─────────────────────────────────────────────────────
        if start in ("1a", "1b"):
            console.print("  [cyan]Step 1-B[/cyan] Writing Markdown spec…")
            spec = DocumentAgent().run(analysis, spec_path)
            await self.fs.write_text(spec_path, spec.content)
            self.manager.add_artifact(name, "spec", spec_path)
            self.manager.update_module_status(name, ModuleStatus.DOCUMENTED)
        else:
            console.print(f"  [dim]Step 1-B skipped — loading spec from disk[/dim]")
            content = await self.fs.read_text(spec_path)
            spec = MarkdownSpec(module_name=name, content=content, output_path=spec_path)

        # ── 1-C: Architect (always run when inside Step 1) ────────────────────
        console.print("  [cyan]Step 1-C[/cyan] Designing Python architecture…")
        design = ArchitectAgent().run(analysis, spec, arch_path)
        await self.fs.write_json(arch_path, design.model_dump())
        self.manager.add_artifact(name, "architecture", arch_path)

        # Validation B: Architecture audit
        console.print("  [cyan]Step 1 Audit[/cyan] Reviewing architecture…")
        logger.debug(f"[{name}] Running architecture auditor")
        audit_result = ArchAuditor().check(design)
        logger.debug(f"[{name}] Arch audit result: passed={audit_result.passed}  issues={len(audit_result.issues)}  warnings={len(audit_result.warnings)}")
        if not audit_result.passed:
            for issue in audit_result.issues:
                console.print(f"    [red]✗ Arch:[/red] {issue}")

        # Human gate — always required after Step 1
        audit_status = "[green]PASS[/green]" if audit_result.passed else "[red]FAIL[/red]"
        ast_summary = (
            "\n".join(f"  • {i}" for i in ast_result.issues[:5])
            if ast_result.issues else "  None"
        )
        arch_issues = (
            "\n".join(f"  • {i}" for i in audit_result.issues[:5])
            if audit_result.issues else "  None"
        )
        approved = self._human_gate(
            title="Step 1 Complete — Analysis, Spec & Architecture",
            body=(
                f"Module: [bold]{name}[/bold]\n"
                f"Complexity score: [bold]{analysis.complexity_score:.2f}[/bold]\n\n"
                f"Spec written to:          {spec_path}\n"
                f"Architecture written to:  {arch_path}\n\n"
                f"AST issues:        {ast_summary}\n"
                f"Architecture audit: {audit_status}\n"
                + (f"  Issues:\n{arch_issues}" if audit_result.issues else "")
            ),
            question="Approve spec & architecture? Proceed to test generation?",
        )
        if not approved:
            raise HumanRejectionError(name)

        self.manager.update_module_status(name, ModuleStatus.ARCHITECTED)
        return analysis, spec, design

    # ══════════════════════════════════════════════════════════════════════════
    # Step 2 — Test-Driven Development (parallel)
    # ══════════════════════════════════════════════════════════════════════════

    async def _build_test_execute(
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

        # Parallel: Functional Tests (2-A) + Golden Master (2-B)
        functional, golden = await asyncio.gather(
            asyncio.to_thread(FunctionalTestsAgent().run, spec, design, func_path),
            asyncio.to_thread(GoldenMasterAgent().run, spec, gm_path),
        )

        # Audit — merge and improve both test suites
        console.print("  [magenta]Step 2 Audit[/magenta] Reviewing test suites…")
        merged_path = str(request.output_dir / name / f"test_{name}.py")
        merged_suite = TestAuditor().audit(functional, golden, merged_path)
        await self.fs.write_text(merged_path, merged_suite.test_code)
        self.manager.add_artifact(name, "test_suite", merged_path)

        # Dry run — validate syntax before any application code exists
        console.print("  [magenta]Step 2 Dry Run[/magenta] pytest --collect-only…")
        dry_result = await DryRunRunner(self.executor).run(merged_suite)
        dry_status = "[green]PASS[/green]" if dry_result.passed else "[yellow]WARN — syntax issues[/yellow]"
        if not dry_result.passed:
            console.print(f"  [yellow]Dry run issues:[/yellow] {dry_result.issues[:3]}")

        # Human gate — always required after Step 2
        dry_issues = (
            "\n".join(f"  • {i}" for i in dry_result.issues[:5])
            if dry_result.issues else ""
        )
        approved = self._human_gate(
            title="Step 2 Complete — Test Suite",
            body=(
                f"Module: [bold]{name}[/bold]\n"
                f"Tests generated: [bold]{merged_suite.test_count}[/bold]\n"
                f"Test file: {merged_path}\n"
                f"Dry run: {dry_status}\n"
                + (f"\n  {dry_issues}" if dry_issues else "")
            ),
            question="Approve test suite? Proceed to code generation?",
        )
        if not approved:
            raise HumanRejectionError(name)

        self.manager.update_module_status(name, ModuleStatus.TESTS_GENERATED)
        return merged_suite

    # ══════════════════════════════════════════════════════════════════════════
    # Step 3 — Conversion & Closed-Loop Execution
    # ══════════════════════════════════════════════════════════════════════════

    async def _generate_code(
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

        logger.debug(f"[{name}] Step 3 start — max_retries={request.max_retries}  py_path={py_path}")
        for attempt in range(request.max_retries + 1):
            label = "initial" if attempt == 0 else f"retry {attempt}/{request.max_retries}"
            console.print(f"  [green]Step 3[/green] Converting ({label})…")
            logger.debug(f"[{name}] Conversion attempt {attempt + 1}/{request.max_retries + 1}")

            conversion = await ConverterAgent(self.vectordb).run(
                design, test_suite, py_path,
                previous_error=previous_error,
                retry_count=attempt,
            )
            await self.fs.write_text(py_path, conversion.python_code)
            self.manager.add_artifact(name, "python_source", py_path)

            # Log clearly that new code was written and where
            lines_generated = len(conversion.python_code.splitlines())
            console.print(
                f"  [green]✓ Code written:[/green] [bold]{lines_generated} lines[/bold]"
                f" → [bold cyan]{py_path}[/bold cyan]"
            )
            logger.info(f"[{name}] Code written to disk: {py_path}  ({lines_generated} lines)")

            # Human gate — review generated code before running any checks
            gate_approved = self._human_gate(
                title=f"Step 3 — Review Generated Code (attempt {attempt + 1}/{request.max_retries + 1})",
                body=(
                    f"Module:    [bold]{name}[/bold]\n"
                    f"Lines:     [bold]{lines_generated}[/bold]\n"
                    f"File:      [bold cyan]{py_path}[/bold cyan]\n\n"
                    f"Open the file above to inspect the generated Python code.\n"
                    f"Proceeding will run mypy then pytest."
                ),
                question="Approve generated code? Proceed to mypy and pytest?",
            )
            if not gate_approved:
                raise HumanRejectionError(name)

            # mypy — fast type check before full pytest run
            console.print("  [green]Step 3[/green] mypy check…")
            mypy_result = await MypyChecker(self.executor).check(py_path, name)
            logger.debug(f"[{name}] mypy result: passed={mypy_result.passed}  issues={len(mypy_result.issues)}")
            if not mypy_result.passed:
                console.print(
                    f"    [yellow]mypy issues ({len(mypy_result.issues)}):[/yellow] "
                    f"{mypy_result.issues[:2]}"
                )
                previous_error = f"mypy errors:\n{mypy_result.details}"
                self.manager.increment_retry(name)
                logger.debug(f"[{name}] mypy failed — will retry conversion")
                continue

            # pytest — show command then run full test suite
            pytest_cmd = f"python -m pytest -v {test_suite.output_path}"
            console.print(f"  [green]Step 3[/green] Running pytest…")
            console.print(f"  [dim]Command:[/dim] [cyan]{pytest_cmd}[/cyan]")
            logger.info(f"[{name}] Invoking: {pytest_cmd}")
            test_result = await PytestRunner(self.executor).run(test_suite.output_path, name)
            logger.debug(f"[{name}] pytest result: passed={test_result.passed}  error_lines={len(test_result.issues)}")
            if test_result.passed:
                console.print(f"  [bold green]✓ {name} — all tests pass![/bold green]")

                # Human gate — always required after Step 3
                approved = self._human_gate(
                    title="Step 3 Complete — Generated Python Code",
                    body=(
                        f"Module: [bold]{name}[/bold]\n"
                        f"Python file: {py_path}\n"
                        f"Retries used: [bold]{attempt}[/bold] / {request.max_retries}\n"
                        f"Tests: [green]ALL PASS[/green]\n\n"
                        f"Approving will save the pattern to translation memory and create a PR."
                    ),
                    question="Approve generated code? Create PR and mark as completed?",
                )
                if not approved:
                    raise HumanRejectionError(name)

                self.manager.update_module_status(name, ModuleStatus.COMPLETED)
                await self._on_success(name, design, conversion, test_result.details, request)
                return

            previous_error = test_result.details
            self.manager.increment_retry(name)
            console.print(
                f"  [red]Tests failed (attempt {attempt + 1}/{request.max_retries + 1})[/red]"
            )

        # Retry budget exhausted — escalate to CLI
        console.print(f"  [bold red]✗ {name} — retry budget exhausted. Escalating to CLI.[/bold red]")
        self._escalate_to_cli(name, previous_error or "Unknown error")
        self.manager.update_module_status(name, ModuleStatus.FAILED, "Retry budget exhausted")

    # ══════════════════════════════════════════════════════════════════════════
    # Artifact loaders (used when skipping completed steps)
    # ══════════════════════════════════════════════════════════════════════════

    async def _load_step1_artifacts(
        self, name: str, request: MigrationRequest
    ) -> tuple[AnalysisResult, MarkdownSpec, ArchitectureDesign]:
        assert self.fs
        console.print(f"  [dim]Step 1 skipped — loading artifacts from disk[/dim]")

        analysis_path = str(request.output_dir / name / f"{name}_analysis.json")
        spec_path     = str(request.output_dir / name / f"{name}_spec.md")
        arch_path     = str(request.output_dir / name / f"{name}_architecture.json")

        analysis_data = await self.fs.read_json(analysis_path)
        analysis = AnalysisResult(**analysis_data)

        spec_content = await self.fs.read_text(spec_path)
        spec = MarkdownSpec(module_name=name, content=spec_content, output_path=spec_path)

        arch_data = await self.fs.read_json(arch_path)
        arch_data.setdefault("output_path", arch_path)
        design = ArchitectureDesign(**arch_data)

        logger.debug(f"[{name}] Step 1 artifacts loaded from disk")
        return analysis, spec, design

    async def _load_test_suite(
        self, name: str, request: MigrationRequest
    ) -> TestSuite:
        assert self.fs
        console.print(f"  [dim]Step 2 skipped — loading test suite from disk[/dim]")

        test_path = str(request.output_dir / name / f"test_{name}.py")
        test_code = await self.fs.read_text(test_path)
        suite = TestSuite(
            module_name=name,
            test_type="merged",
            test_code=test_code,
            output_path=test_path,
            test_count=test_code.count("\ndef test_"),
        )
        logger.debug(f"[{name}] Test suite loaded from disk — {suite.test_count} tests")
        return suite

    # ══════════════════════════════════════════════════════════════════════════
    # Human-in-the-loop helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _human_gate(self, title: str, body: str, question: str) -> bool:
        console.print(Panel(
            body,
            title=f"[bold yellow]⚠ Human Review — {title}[/bold yellow]",
            border_style="yellow",
        ))
        return Confirm.ask(question)

    def _escalate_to_cli(self, name: str, error: str) -> None:
        console.print(Panel(
            f"Module [bold]{name}[/bold] failed after all retries.\n\n"
            f"Last error:\n[red]{error[:500]}[/red]",
            title="[bold red]Escalation — Human Intervention Needed[/bold red]",
            border_style="red",
        ))
        Prompt.ask("Press Enter to acknowledge and continue to the next module")

    # ══════════════════════════════════════════════════════════════════════════
    # Post-success: save to translation memory, create PR
    # ══════════════════════════════════════════════════════════════════════════

    async def _on_success(
        self,
        name: str,
        design: ArchitectureDesign,
        conversion: ConversionResult,
        test_summary: str,
        request: MigrationRequest,
    ) -> None:
        assert self.vectordb and self.github

        await self.vectordb.store_pattern(
            java_snippet=name,
            python_snippet=conversion.python_code[:500],
            description=f"Module: {name}",
        )

        py_path = Path(conversion.output_path)
        pr_url = await self.github.create_pr(
            module_name=name,
            python_file_path=py_path,
            python_code=conversion.python_code,
            test_results_summary=test_summary[:1000],
        )
        if pr_url:
            console.print(f"  [blue]PR created:[/blue] {pr_url}")


class HumanRejectionError(Exception):
    """Raised when the human gate rejects an architecture."""
    pass
