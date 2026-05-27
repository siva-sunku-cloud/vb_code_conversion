"""
Step 2-B · Golden Master Agent

Creates characterization tests by replaying legacy VB I/O data.
If no historical I/O data is available, generates synthetic samples
based on the functional spec.
"""
from agents.base_agent import BaseAgent
from models.artifacts import MarkdownSpec, TestSuite
from utils.prompts import GOLDEN_MASTER_SYSTEM


class GoldenMasterAgent(BaseAgent):
    def __init__(self):
        super().__init__("GoldenMasterAgent")

    def run(
        self,
        spec: MarkdownSpec,
        output_path: str,
        io_samples: list[dict] | None = None,
    ) -> TestSuite:
        self.logger.info(f"Generating golden-master tests for: {spec.module_name}")
        self.logger.debug(
            f"[{spec.module_name}] output_path={output_path}"
            f"  io_samples={'synthetic (none provided)' if not io_samples else len(io_samples)}"
        )

        samples_section = ""
        if io_samples:
            import json
            samples_section = (
                "\n\n## Historical I/O Samples (JSON)\n"
                f"```json\n{json.dumps(io_samples, indent=2)}\n```"
            )
            self.logger.debug(f"[{spec.module_name}] using {len(io_samples)} historical I/O samples")
        else:
            samples_section = (
                "\n\n*No historical I/O data provided — generate representative "
                "synthetic samples based on the specification.*"
            )
            self.logger.debug(f"[{spec.module_name}] no I/O samples — LLM will generate synthetic ones")

        response = self._call_llm(
            system=GOLDEN_MASTER_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Write golden-master pytest tests for the following module.\n\n"
                        "## Functional Specification\n"
                        f"{spec.content}"
                        f"{samples_section}"
                    ),
                }
            ],
            max_tokens=4096,
        )

        test_code = self._text(response).strip()
        if test_code.startswith("```"):
            test_code = test_code.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        test_count = test_code.count("def test_")
        self.logger.info(f"[{spec.module_name}] {test_count} golden-master tests generated")
        self.logger.debug(
            f"[{spec.module_name}] test_code_lines={len(test_code.splitlines())}"
            f"  test_code_chars={len(test_code)}"
        )

        return TestSuite(
            module_name=spec.module_name,
            test_type="golden_master",
            test_code=test_code,
            output_path=output_path,
            test_count=test_count,
        )
