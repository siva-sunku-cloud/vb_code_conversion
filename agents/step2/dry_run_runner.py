"""
Step 2 Runner · Dry Run

Calls the Execution MCP server with pytest --collect-only to confirm test
syntax is valid and all tests are discoverable before any application code
exists.
"""
from pathlib import Path

from mcp.execution_server import ExecutionServer
from models.artifacts import TestSuite, ValidationResult
from utils.logger import get_logger

logger = get_logger("DryRunRunner")


class DryRunRunner:
    def __init__(self, executor: ExecutionServer):
        self.executor = executor

    def run(self, suite: TestSuite) -> ValidationResult:
        logger.info(f"Dry-running test collection for: {suite.module_name}")

        result = self.executor.run_pytest_collect(suite.output_path)

        if result.passed:
            logger.info(f"[{suite.module_name}] dry run PASS — all tests discoverable")
            return ValidationResult(
                passed=True,
                details=result.stdout,
            )
        else:
            issues = [line for line in result.combined.splitlines() if line.strip()]
            logger.warning(f"[{suite.module_name}] dry run FAIL — {len(issues)} issues")
            return ValidationResult(
                passed=False,
                issues=issues,
                details=result.combined,
            )
