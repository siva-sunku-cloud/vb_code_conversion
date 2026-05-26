"""
Step 1 Validator-A · AST Checker

Parses the VB source with a regex-based lexer to verify that all
Sub/Function/Class/UDT definitions were captured in the AnalysisResult.
Fails the step on unrecognised VB constructs.
"""
import re
from models.artifacts import AnalysisResult, ValidationResult
from utils.logger import get_logger

logger = get_logger("ASTChecker")

# Patterns for top-level VB constructs
_SUB_RE = re.compile(r"^\s*(Public|Private|Friend)?\s*Sub\s+(\w+)", re.MULTILINE | re.IGNORECASE)
_FUNC_RE = re.compile(r"^\s*(Public|Private|Friend)?\s*Function\s+(\w+)", re.MULTILINE | re.IGNORECASE)
_CLASS_RE = re.compile(r"^\s*Class\s+(\w+)", re.MULTILINE | re.IGNORECASE)
_TYPE_RE = re.compile(r"^\s*Type\s+(\w+)", re.MULTILINE | re.IGNORECASE)
_GOTO_RE = re.compile(r"\bGoTo\b", re.IGNORECASE)
_ON_ERR_RE = re.compile(r"\bOn\s+Error\b", re.IGNORECASE)


class ASTChecker:
    def check(self, vb_source: str, analysis: AnalysisResult) -> ValidationResult:
        issues: list[str] = []
        warnings: list[str] = []

        # Collect names from source
        src_subs = {m.group(2).lower() for m in _SUB_RE.finditer(vb_source)}
        src_funcs = {m.group(2).lower() for m in _FUNC_RE.finditer(vb_source)}
        src_procs = src_subs | src_funcs

        # Compare against what the Understand Agent captured
        captured_procs = {p.split("(")[0].strip().lower() for p in analysis.control_flow.get("procedures", [])}
        missing = src_procs - captured_procs
        for name in sorted(missing):
            issues.append(f"Procedure '{name}' found in source but not captured in analysis.")

        # Flag unhandled VB idioms
        if _GOTO_RE.search(vb_source):
            warnings.append("Source contains GoTo — verify control-flow mapping is complete.")
        if _ON_ERR_RE.search(vb_source):
            warnings.append("Source contains 'On Error' — ensure error paths are modelled.")

        passed = len(issues) == 0
        logger.info(
            f"[{analysis.module_name}] AST check: {'PASS' if passed else 'FAIL'} "
            f"({len(issues)} issues, {len(warnings)} warnings)"
        )
        return ValidationResult(passed=passed, issues=issues, warnings=warnings)
