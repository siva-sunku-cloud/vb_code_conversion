"""
Step 1-B · Document Agent

Converts an AnalysisResult into a human-readable Markdown functional spec.
"""
import json

from agents.base_agent import BaseAgent
from models.artifacts import AnalysisResult, MarkdownSpec
from utils.prompts import DOCUMENT_SYSTEM


class DocumentAgent(BaseAgent):
    def __init__(self):
        super().__init__("DocumentAgent")

    def run(self, analysis: AnalysisResult, output_path: str) -> MarkdownSpec:
        self.logger.info(f"Documenting module: {analysis.module_name}")

        response = self._call_llm(
            system=DOCUMENT_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Write the Markdown specification for the following VB module analysis.\n\n"
                        f"```json\n{analysis.model_dump_json(indent=2)}\n```"
                    ),
                }
            ],
            max_tokens=4096,
        )

        content = self._text(response)
        self.logger.info(f"[{analysis.module_name}] spec written ({len(content)} chars)")
        return MarkdownSpec(
            module_name=analysis.module_name,
            content=content,
            output_path=output_path,
        )
