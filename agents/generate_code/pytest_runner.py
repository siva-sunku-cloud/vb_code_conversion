"""
Step 3 Runner · pytest

Runs the complete test suite (Functional + Golden Master) via the Execution
MCP client. Always runs every test regardless of failures so the human gate
can see the full picture before deciding whether to accept, retry, or reject.
"""
import re

from infrastructure.clients.execution_client import ExecutionClient
from models.artifacts import ValidationResult
from utils.logger import get_logger

logger = get_logger("PytestRunner")

# Matches lines like "3 failed, 5 passed in 1.23s" or "8 passed in 0.45s"
_SUMMARY_RE = re.compile(r"(\d+)\s+passed|(\d+)\s+(?:failed|error)")


def _parse_counts(output: str) -> tuple[int, int]:
    """Return (passed, failed) counts from pytest's final summary line."""
    passed = 0
    failed = 0
    for m in _SUMMARY_RE.finditer(output):
        if m.group(1):
            passed = int(m.group(1))
        else:
            failed += int(m.group(2))
    return passed, failed


class PytestRunner:
    def __init__(self, executor: ExecutionClient) -> None:
        self.executor = executor

    async def run(self, test_file_path: str, module_name: str) -> ValidationResult:
        logger.info(f"Running pytest for: {module_name}")
        logger.debug(f"[{module_name}] test_file={test_file_path}")

        result = await self.executor.run_pytest(test_file_path)

        passed_count, failed_count = _parse_counts(result.combined)

        logger.debug(
            f"[{module_name}] pytest passed={passed_count}  failed={failed_count}"
            f"  returncode={result.returncode}"
        )

        if result.passed:
            logger.info(f"[{module_name}] pytest PASS ✓  ({passed_count} tests)")
            return ValidationResult(
                passed=True,
                details=result.stdout,
                passed_count=passed_count,
                failed_count=0,
            )

        # Collect focused failure lines for the human gate and retry context
        error_lines = [
            line for line in result.combined.splitlines()
            if any(kw in line for kw in ("FAILED", "ERROR", "AssertionError", "assert", "E "))
        ]
        logger.warning(
            f"[{module_name}] pytest FAIL — {failed_count} failed, {passed_count} passed"
        )
        return ValidationResult(
            passed=False,
            issues=error_lines,
            details=result.combined,
            passed_count=passed_count,
            failed_count=failed_count,
        )
