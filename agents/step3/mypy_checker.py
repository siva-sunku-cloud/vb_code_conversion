"""
Step 3 Validator-A · mypy Checker

Runs mypy --strict on the generated Python file via the Execution MCP server.
Catches type errors early, before the full pytest run.
"""
from mcp.execution_server import ExecutionServer
from models.artifacts import ValidationResult
from utils.logger import get_logger

logger = get_logger("MypyChecker")


class MypyChecker:
    def __init__(self, executor: ExecutionServer):
        self.executor = executor

    def check(self, python_file_path: str, module_name: str) -> ValidationResult:
        logger.info(f"Running mypy on: {module_name}")

        result = self.executor.run_mypy(python_file_path)

        if result.passed:
            logger.info(f"[{module_name}] mypy PASS")
            return ValidationResult(passed=True, details=result.stdout)

        issues = [
            line for line in result.combined.splitlines()
            if line.strip() and not line.startswith("Found ")
        ]
        logger.warning(f"[{module_name}] mypy FAIL — {len(issues)} errors")
        return ValidationResult(passed=False, issues=issues, details=result.combined)
