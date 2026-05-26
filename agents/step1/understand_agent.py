"""
Step 1-A · Understand Agent

Extracts business logic, data structures, COM/API calls, and control flow
from a VB source file.  Returns a structured AnalysisResult.
"""
from pathlib import Path

from agents.base_agent import BaseAgent
from models.artifacts import AnalysisResult
from utils.prompts import UNDERSTAND_SYSTEM


class UnderstandAgent(BaseAgent):
    def __init__(self):
        super().__init__("UnderstandAgent")

    def run(self, vb_source: str, module_name: str, vb_file_path: str) -> AnalysisResult:
        self.logger.info(f"Analysing module: {module_name}")

        response = self._call_llm(
            system=UNDERSTAND_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Analyse this Visual Basic module named '{module_name}'.\n\n"
                        f"```vb\n{vb_source}\n```"
                    ),
                }
            ],
            max_tokens=4096,
        )

        data = self._parse_json(response)
        data["module_name"] = module_name
        data["vb_file_path"] = vb_file_path

        result = AnalysisResult(**data)
        self.logger.info(
            f"[{module_name}] complexity={result.complexity_score:.2f}  "
            f"procedures={len(result.control_flow.get('procedures', []))}"
        )
        return result
