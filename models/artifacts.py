from pydantic import BaseModel, Field
from typing import Optional


class AnalysisResult(BaseModel):
    """Output of the Understand Agent — structured representation of a Java module."""
    module_name: str
    source_file_path: str
    business_logic: list[str] = Field(default_factory=list)
    data_structures: list[dict] = Field(default_factory=list)
    external_api_calls: list[str] = Field(default_factory=list)
    control_flow: dict = Field(default_factory=dict)
    complexity_score: float = 0.0
    raw_summary: str = ""


class MarkdownSpec(BaseModel):
    """Output of the Document Agent — human-readable functional spec."""
    module_name: str
    content: str
    output_path: str


class ArchitectureDesign(BaseModel):
    """Output of the Architect Agent — Python module design blueprint."""
    module_name: str
    dataclasses: list[dict] = Field(default_factory=list)
    type_hints: dict[str, str] = Field(default_factory=dict)
    module_boundaries: list[str] = Field(default_factory=list)
    dependency_injection: list[str] = Field(default_factory=list)
    public_api: list[dict] = Field(default_factory=list)
    output_path: str
    design_notes: str = ""


class ValidationResult(BaseModel):
    """Generic pass/fail result from any validator or checker."""
    passed: bool
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    details: str = ""
    passed_count: int = 0
    failed_count: int = 0


class TestSuite(BaseModel):
    """Output of a test-generation agent."""
    module_name: str
    test_type: str   # "functional" | "golden_master"
    test_code: str
    output_path: str
    test_count: int = 0


class ConversionResult(BaseModel):
    """Output of the Converter Agent."""
    module_name: str
    python_code: str
    output_path: str
    passed_all_tests: bool = False
    retry_count: int = 0
    final_error: Optional[str] = None
