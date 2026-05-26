"""
Step 3-A · Converter Agent

Writes Python application code targeting the architecture blueprint and the
full test suite.  On failure, receives formatted pytest error output and
iterates until all tests pass or the retry budget is exhausted.
"""
from agents.base_agent import BaseAgent
from models.artifacts import ArchitectureDesign, TestSuite, ConversionResult
from mcp.vectordb_server import VectorDBServer
from utils.prompts import CONVERTER_SYSTEM


class ConverterAgent(BaseAgent):
    def __init__(self, vectordb: VectorDBServer | None = None):
        super().__init__("ConverterAgent")
        self.vectordb = vectordb

    def run(
        self,
        design: ArchitectureDesign,
        test_suite: TestSuite,
        output_path: str,
        previous_error: str | None = None,
        retry_count: int = 0,
    ) -> ConversionResult:
        attempt = f"attempt {retry_count + 1}" if retry_count > 0 else "initial"
        self.logger.info(f"Converting {design.module_name} ({attempt})")

        # Retrieve similar patterns from translation memory
        patterns_section = self._fetch_patterns(design.module_name)

        error_section = ""
        if previous_error:
            error_section = (
                "\n\n## Previous Attempt — pytest Error Output\n"
                f"```\n{previous_error}\n```\n"
                "Fix ALL failing tests."
            )

        response = self._call_llm(
            system=CONVERTER_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Convert this VB module to Python.\n\n"
                        "## Architecture Blueprint (JSON)\n"
                        f"```json\n{design.model_dump_json(indent=2)}\n```\n\n"
                        "## Full Test Suite\n"
                        f"```python\n{test_suite.test_code}\n```"
                        f"{patterns_section}"
                        f"{error_section}"
                    ),
                }
            ],
            max_tokens=8192,
        )

        python_code = self._text(response).strip()
        if python_code.startswith("```"):
            python_code = python_code.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        self.logger.info(f"[{design.module_name}] generated {len(python_code.splitlines())} lines")

        return ConversionResult(
            module_name=design.module_name,
            python_code=python_code,
            output_path=output_path,
            retry_count=retry_count,
        )

    # ── Private ───────────────────────────────────────────────────────────────

    def _fetch_patterns(self, module_name: str) -> str:
        if not self.vectordb:
            return ""
        patterns = self.vectordb.search_patterns(module_name)
        if not patterns:
            return ""
        lines = ["\n\n## Translation Memory — Similar Patterns"]
        for i, p in enumerate(patterns, 1):
            lines.append(
                f"\n### Pattern {i}: {p.get('description', '')}\n"
                f"**VB:**\n```vb\n{p.get('vb_snippet', '')}\n```\n"
                f"**Python:**\n```python\n{p.get('python_snippet', '')}\n```"
            )
        return "\n".join(lines)
