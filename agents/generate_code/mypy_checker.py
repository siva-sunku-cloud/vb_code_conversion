"""
Step 3 Validator-A · mypy Checker

Runs mypy --strict on the generated Python file via the Execution MCP client.
Catches type errors early, before the full pytest run.
"""
from infrastructure.clients.execution_client import ExecutionClient
from models.artifacts import ValidationResult
from utils.logger import get_logger

logger = get_logger("MypyChecker")


class MypyChecker:
    def __init__(self, executor: ExecutionClient) -> None:
        self.executor = executor

    async def check(self, python_file_path: str, module_name: str) -> ValidationResult:
        logger.info(f"Running mypy on: {module_name}")
        logger.debug(f"[{module_name}] file={python_file_path}")

        result = await self.executor.run_mypy(python_file_path)

        logger.debug(
            f"[{module_name}] mypy stdout_chars={len(result.stdout)}"
            f"  combined_chars={len(result.combined)}"
            f"  passed={result.passed}"
        )

        if result.passed:
            logger.info(f"[{module_name}] mypy PASS")
            logger.debug(f"[{module_name}] mypy output: {result.stdout[:300]}")
            return ValidationResult(passed=True, details=result.stdout)

        issues = [
            line for line in result.combined.splitlines()
            if line.strip() and not line.startswith("Found ")
        ]
        logger.warning(f"[{module_name}] mypy FAIL — {len(issues)} errors")
        for issue in issues[:10]:
            logger.debug(f"[{module_name}]   mypy error: {issue}")
        return ValidationResult(passed=False, issues=issues, details=result.combined)
