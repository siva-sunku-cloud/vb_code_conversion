"""
Step 2 Runner · Dry Run

Calls the Execution MCP client with pytest --collect-only to confirm test
syntax is valid and all tests are discoverable before any application code
exists.
"""
from infrastructure.clients.execution_client import ExecutionClient
from models.artifacts import TestSuite, ValidationResult
from utils.logger import get_logger

logger = get_logger("DryRunRunner")


class DryRunRunner:
    def __init__(self, executor: ExecutionClient) -> None:
        self.executor = executor

    async def run(self, suite: TestSuite) -> ValidationResult:
        logger.info(f"Dry-running test collection for: {suite.module_name}")
        logger.debug(
            f"[{suite.module_name}] test_file={suite.output_path}"
            f"  test_count={suite.test_count}"
            f"  test_type={suite.test_type}"
        )

        result = await self.executor.run_pytest_collect(suite.output_path)

        logger.debug(
            f"[{suite.module_name}] dry run stdout_chars={len(result.stdout)}"
            f"  combined_chars={len(result.combined)}"
            f"  passed={result.passed}"
        )

        if result.passed:
            logger.info(f"[{suite.module_name}] dry run PASS — all tests discoverable")
            logger.debug(f"[{suite.module_name}] dry run output: {result.stdout[:500]}")
            return ValidationResult(passed=True, details=result.stdout)

        issues = [line for line in result.combined.splitlines() if line.strip()]
        logger.warning(f"[{suite.module_name}] dry run FAIL — {len(issues)} issues")
        for issue in issues[:10]:
            logger.debug(f"[{suite.module_name}]   dry run issue: {issue}")
        return ValidationResult(passed=False, issues=issues, details=result.combined)
