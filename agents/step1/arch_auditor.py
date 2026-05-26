"""
Step 1 Validator-B · Architecture Auditor

LLM reviewer that inspects the proposed architecture for Python idioms.
Checks: no global mutable state, proper OOP, no VB-isms carried over.
"""
from agents.base_agent import BaseAgent
from models.artifacts import ArchitectureDesign, ValidationResult
from utils.prompts import ARCH_AUDIT_SYSTEM


class ArchAuditor(BaseAgent):
    def __init__(self):
        super().__init__("ArchAuditor")

    def check(self, design: ArchitectureDesign) -> ValidationResult:
        self.logger.info(f"Auditing architecture for: {design.module_name}")

        response = self._call_llm(
            system=ARCH_AUDIT_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Audit this Python architecture blueprint.\n\n"
                        f"```json\n{design.model_dump_json(indent=2)}\n```"
                    ),
                }
            ],
            max_tokens=2048,
        )

        data = self._parse_json(response)
        result = ValidationResult(**data)
        self.logger.info(
            f"[{design.module_name}] arch audit: {'PASS' if result.passed else 'FAIL'} "
            f"({len(result.issues)} issues)"
        )
        return result
