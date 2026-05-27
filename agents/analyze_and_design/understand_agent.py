"""
Step 1-A · Understand Agent

Extracts business logic, data structures, external API calls, and control
flow from a Java source file. Returns a structured AnalysisResult.
"""
from agents.base_agent import BaseAgent
from models.artifacts import AnalysisResult
from utils.prompts import UNDERSTAND_SYSTEM


class UnderstandAgent(BaseAgent):
    def __init__(self):
        super().__init__("UnderstandAgent")

    def run(self, source_code: str, module_name: str, source_file_path: str) -> AnalysisResult:
        self.logger.info(f"Analysing module: {module_name}")
        self.logger.debug(
            f"[{module_name}] source_file={source_file_path}"
            f"  source_lines={len(source_code.splitlines())}"
            f"  source_chars={len(source_code)}"
        )

        response = self._call_llm(
            system=UNDERSTAND_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Analyse this Java module named '{module_name}'.\n\n"
                        f"```java\n{source_code}\n```"
                    ),
                }
            ],
            max_tokens=4096,
        )

        data = self._parse_json(response)
        data["module_name"] = module_name
        data["source_file_path"] = source_file_path

        result = AnalysisResult(**data)
        self.logger.info(
            f"[{module_name}] complexity={result.complexity_score:.2f}"
            f"  methods={len(result.control_flow.get('methods', []))}"
        )
        self.logger.debug(
            f"[{module_name}] business_logic_items={len(result.business_logic)}"
            f"  data_structures={len(result.data_structures)}"
            f"  external_api_calls={len(result.external_api_calls)}"
            f"  loops={len(result.control_flow.get('loops', []))}"
            f"  exception_handlers={len(result.control_flow.get('exception_handlers', []))}"
        )
        self.logger.debug(f"[{module_name}] summary: {result.raw_summary}")
        if result.data_structures:
            for ds in result.data_structures:
                self.logger.debug(
                    f"[{module_name}]   data_structure: name={ds.get('name')}  type={ds.get('type')}  fields={len(ds.get('fields', []))}"
                )
        return result
