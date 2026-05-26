"""
Step 2 Validator · Test Auditor

Reviews both test suites: flags trivial assertions, over-mocking of real
logic, and missing coverage.  Returns an improved, merged test file.
"""
from agents.base_agent import BaseAgent
from models.artifacts import TestSuite
from utils.prompts import TEST_AUDITOR_SYSTEM


class TestAuditor(BaseAgent):
    def __init__(self):
        super().__init__("TestAuditor")

    def audit(
        self,
        functional: TestSuite,
        golden: TestSuite,
        output_path: str,
    ) -> TestSuite:
        self.logger.info(f"Auditing test suites for: {functional.module_name}")

        response = self._call_llm(
            system=TEST_AUDITOR_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Review and improve these two test files for module '{functional.module_name}'.\n\n"
                        "## Functional Tests\n"
                        f"```python\n{functional.test_code}\n```\n\n"
                        "## Golden Master Tests\n"
                        f"```python\n{golden.test_code}\n```"
                    ),
                }
            ],
            max_tokens=6000,
        )

        merged_code = self._text(response).strip()
        if merged_code.startswith("```"):
            merged_code = merged_code.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        test_count = merged_code.count("def test_")
        self.logger.info(
            f"[{functional.module_name}] audited test suite: "
            f"{functional.test_count + golden.test_count} → {test_count} tests"
        )

        return TestSuite(
            module_name=functional.module_name,
            test_type="merged",
            test_code=merged_code,
            output_path=output_path,
            test_count=test_count,
        )
