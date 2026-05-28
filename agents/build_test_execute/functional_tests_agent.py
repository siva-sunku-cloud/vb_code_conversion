"""
Step 2-A · Functional Tests Agent

Writes pytest unit tests covering edge cases, boundary conditions, and logic
branches derived directly from the Markdown spec.
"""
from agents.base_agent import BaseAgent
from models.artifacts import MarkdownSpec, ArchitectureDesign, TestSuite
from utils.prompts import FUNCTIONAL_TESTS_SYSTEM


class FunctionalTestsAgent(BaseAgent):
    def __init__(self):
        super().__init__("FunctionalTestsAgent")

    def run(
        self,
        spec: MarkdownSpec,
        design: ArchitectureDesign,
        output_path: str,
    ) -> TestSuite:
        self.logger.info(f"Generating functional tests for: {spec.module_name}")
        self.logger.debug(
            f"[{spec.module_name}] output_path={output_path}"
            f"  spec_chars={len(spec.content)}"
            f"  design_dataclasses={len(design.dataclasses)}"
            f"  design_public_api={len(design.public_api)}"
        )

        response = self._call_llm(
            system=FUNCTIONAL_TESTS_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Write pytest functional tests for the following module.\n\n"
                        "## Functional Specification\n"
                        f"{spec.content}\n\n"
                        "## Architecture Blueprint (JSON)\n"
                        f"```json\n{design.model_dump_json(indent=2)}\n```"
                    ),
                }
            ],
            max_tokens=4096,
        )

        test_code = self._extract_code(self._text(response))

        test_count = test_code.count("def test_")
        self.logger.info(f"[{spec.module_name}] {test_count} functional tests generated")
        self.logger.debug(
            f"[{spec.module_name}] test_code_lines={len(test_code.splitlines())}"
            f"  test_code_chars={len(test_code)}"
        )

        return TestSuite(
            module_name=spec.module_name,
            test_type="functional",
            test_code=test_code,
            output_path=output_path,
            test_count=test_count,
        )
