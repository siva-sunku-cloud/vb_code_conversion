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
        self.logger.debug(
            f"[{analysis.module_name}] output_path={output_path}"
            f"  spec_chars={len(spec.content)}"
            f"  complexity={analysis.complexity_score:.2f}"
        )

        response = self._call_llm(
            system=ARCHITECT_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Design the Python architecture for this Java module.\n\n"
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
        self.logger.debug(
            f"[{analysis.module_name}] type_hints={len(design.type_hints)}"
            f"  module_boundaries={len(design.module_boundaries)}"
            f"  dependency_injection={len(design.dependency_injection)}"
        )
        if design.dataclasses:
            for dc in design.dataclasses:
                self.logger.debug(
                    f"[{analysis.module_name}]   dataclass: name={dc.get('name')}  fields={len(dc.get('fields', []))}"
                )
        if design.public_api:
            for api in design.public_api:
                self.logger.debug(
                    f"[{analysis.module_name}]   public_api: {api.get('name', api)}"
                )
        if design.design_notes:
            self.logger.debug(f"[{analysis.module_name}] design_notes: {design.design_notes[:200]}")
        return design
