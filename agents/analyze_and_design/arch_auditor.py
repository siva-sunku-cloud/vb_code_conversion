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
        self.logger.debug(
            f"[{design.module_name}] dataclasses={len(design.dataclasses)}"
            f"  public_api={len(design.public_api)}"
            f"  module_boundaries={len(design.module_boundaries)}"
            f"  dependency_injection={len(design.dependency_injection)}"
        )

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
            f"[{design.module_name}] arch audit: {'PASS' if result.passed else 'FAIL'}"
            f"  issues={len(result.issues)}  warnings={len(result.warnings)}"
        )
        if result.issues:
            for issue in result.issues:
                self.logger.debug(f"[{design.module_name}]   issue: {issue}")
        if result.warnings:
            for warning in result.warnings:
                self.logger.debug(f"[{design.module_name}]   warning: {warning}")
        if result.details:
            self.logger.debug(f"[{design.module_name}] audit details: {result.details[:300]}")
        return result
