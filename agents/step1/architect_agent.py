"""
Step 1-C · Architect Agent

Designs the Python equivalent module: dataclasses, type hints, module
boundaries, and dependency injection points.
"""
from agents.base_agent import BaseAgent
from models.artifacts import AnalysisResult, MarkdownSpec, ArchitectureDesign
from utils.prompts import ARCHITECT_SYSTEM


class ArchitectAgent(BaseAgent):
    def __init__(self):
        super().__init__("ArchitectAgent")

    def run(
        self,
        analysis: AnalysisResult,
        spec: MarkdownSpec,
        output_path: str,
    ) -> ArchitectureDesign:
        self.logger.info(f"Designing architecture for: {analysis.module_name}")

        response = self._call_llm(
            system=ARCHITECT_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Design the Python architecture for this VB module.\n\n"
                        "## Structured Analysis (JSON)\n"
                        f"```json\n{analysis.model_dump_json(indent=2)}\n```\n\n"
                        "## Functional Specification (Markdown)\n"
                        f"{spec.content}"
                    ),
                }
            ],
            max_tokens=4096,
        )

        data = self._parse_json(response)
        data["module_name"] = analysis.module_name
        data["output_path"] = output_path

        design = ArchitectureDesign(**data)
        self.logger.info(
            f"[{analysis.module_name}] "
            f"dataclasses={len(design.dataclasses)}  "
            f"public_api={len(design.public_api)}"
        )
        return design
