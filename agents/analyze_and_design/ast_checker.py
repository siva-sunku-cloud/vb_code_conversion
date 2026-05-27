"""
Step 1 Validator-A · AST Checker

Parses the Java source with a regex-based lexer to verify that all
class/interface/method definitions were captured in the AnalysisResult.
"""
import re
from models.artifacts import AnalysisResult, ValidationResult
from utils.logger import get_logger

logger = get_logger("ASTChecker")

# Patterns for top-level Java constructs
_METHOD_RE = re.compile(
    r"^\s*(public|private|protected|static|final|synchronized|abstract|\s)+"
    r"[\w<>\[\],\s]+\s+(\w+)\s*\(",
    re.MULTILINE,
)
_CLASS_RE = re.compile(
    r"^\s*(public|private|protected|abstract|final|\s)*\s+class\s+(\w+)",
    re.MULTILINE,
)
_INTERFACE_RE = re.compile(r"^\s*(public|private)?\s*interface\s+(\w+)", re.MULTILINE)
_NULL_RETURN_RE = re.compile(r"\breturn\s+null\b")
_INSTANCEOF_RE = re.compile(r"\binstanceof\b")
_SYNC_RE = re.compile(r"\bsynchronized\b")
_RAW_TYPE_RE = re.compile(r"\b(ArrayList|HashMap|HashSet|LinkedList)\s*[^<]")


class ASTChecker:
    def check(self, source: str, analysis: AnalysisResult) -> ValidationResult:
        issues: list[str] = []
        warnings: list[str] = []

        # Collect method names found in source
        src_methods = {m.group(2).lower() for m in _METHOD_RE.finditer(source)
                       if m.group(2) not in ("if", "while", "for", "switch", "catch")}

        # Compare against what the Understand Agent captured
        captured = {p.split("(")[0].strip().lower()
                    for p in analysis.control_flow.get("methods", [])}
        missing = src_methods - captured
        for name in sorted(missing):
            issues.append(f"Method '{name}' found in source but not captured in analysis.")

        # Collect class names found in source
        src_classes = {m.group(2).lower() for m in _CLASS_RE.finditer(source)}
        captured_classes = {
            ds["name"].lower()
            for ds in analysis.data_structures
            if "class" in ds.get("type", "").lower()
        }
        for name in sorted(src_classes - captured_classes):
            issues.append(f"Class '{name}' found in source but not captured in analysis.")

        # Collect interface names found in source
        src_interfaces = {m.group(2).lower() for m in _INTERFACE_RE.finditer(source)}
        captured_interfaces = {
            ds["name"].lower()
            for ds in analysis.data_structures
            if "interface" in ds.get("type", "").lower()
        }
        for name in sorted(src_interfaces - captured_interfaces):
            issues.append(f"Interface '{name}' found in source but not captured in analysis.")

        # Flag Java idioms that need special migration attention
        if _NULL_RETURN_RE.search(source):
            warnings.append("Source contains 'return null' — verify Optional[T] handling in architecture.")
        if _INSTANCEOF_RE.search(source):
            warnings.append("Source contains instanceof — verify type-dispatch is modelled correctly.")
        if _SYNC_RE.search(source):
            warnings.append("Source contains synchronized — verify thread-safety model in Python design.")
        if _RAW_TYPE_RE.search(source):
            warnings.append("Source uses raw collection types — ensure generic equivalents are typed in Python.")

        passed = len(issues) == 0
        logger.info(
            f"[{analysis.module_name}] AST check: {'PASS' if passed else 'FAIL'} "
            f"({len(issues)} issues, {len(warnings)} warnings) "
            f"[methods={len(src_methods)}, classes={len(src_classes)}, interfaces={len(src_interfaces)}]"
        )
        return ValidationResult(passed=passed, issues=issues, warnings=warnings)
