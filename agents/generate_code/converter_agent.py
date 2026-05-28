"""
Step 3-A · Converter Agent

Writes Python application code targeting the architecture blueprint and the
full test suite. On failure, receives formatted pytest error output and
iterates until all tests pass or the retry budget is exhausted.
"""
from __future__ import annotations

import re
from typing import Optional

from agents.base_agent import BaseAgent
from infrastructure.clients.vectordb_client import VectorDBClient
from models.artifacts import ArchitectureDesign, ConversionResult, TestSuite
from utils.prompts import CONVERTER_SYSTEM


class ConverterAgent(BaseAgent):
    def __init__(self, vectordb: Optional[VectorDBClient] = None) -> None:
        super().__init__("ConverterAgent")
        self.vectordb = vectordb
        self.logger.debug(f"vectordb={'enabled' if vectordb else 'disabled'}")

    async def run(
        self,
        design: ArchitectureDesign,
        test_suite: TestSuite,
        output_path: str,
        previous_error: Optional[str] = None,
        retry_count: int = 0,
    ) -> ConversionResult:
        attempt = f"attempt {retry_count + 1}" if retry_count > 0 else "initial"
        self.logger.info(f"Converting {design.module_name} ({attempt})")
        self.logger.debug(
            f"[{design.module_name}] output_path={output_path}"
            f"  retry_count={retry_count}"
            f"  has_previous_error={previous_error is not None}"
            f"  test_count={test_suite.test_count}"
        )
        if previous_error:
            self.logger.debug(
                f"[{design.module_name}] previous_error preview: {previous_error[:300]}"
            )

        patterns_section = await self._fetch_patterns(design.module_name)

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
                        f"Convert this Java module to Python.\n\n"
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

        # Extract the first ```python … ``` or ``` … ``` block if the LLM added
        # prose/markdown around the code despite the system prompt instructions.
        fence_match = re.search(r"```(?:python)?\n(.*?)```", python_code, re.DOTALL)
        if fence_match:
            python_code = fence_match.group(1).strip()
            self.logger.debug(f"[{design.module_name}] stripped markdown fences from response")

        lines = python_code.splitlines()
        self.logger.info(f"[{design.module_name}] generated {len(lines)} lines")
        self.logger.debug(
            f"[{design.module_name}] python_code_chars={len(python_code)}"
            f"  output_path={output_path}"
        )

        return ConversionResult(
            module_name=design.module_name,
            python_code=python_code,
            output_path=output_path,
            retry_count=retry_count,
        )

    async def _fetch_patterns(self, module_name: str) -> str:
        if not self.vectordb:
            self.logger.debug(f"[{module_name}] translation memory skipped (no vectordb)")
            return ""
        patterns = await self.vectordb.search_patterns(module_name)
        if not patterns:
            self.logger.debug(f"[{module_name}] no translation memory patterns found")
            return ""
        self.logger.debug(f"[{module_name}] {len(patterns)} translation memory patterns loaded")
        lines = ["\n\n## Translation Memory — Similar Patterns"]
        for i, p in enumerate(patterns, 1):
            lines.append(
                f"\n### Pattern {i}: {p.get('description', '')}\n"
                f"**Java:**\n```java\n{p.get('java_snippet', '')}\n```\n"
                f"**Python:**\n```python\n{p.get('python_snippet', '')}\n```"
            )
        return "\n".join(lines)
