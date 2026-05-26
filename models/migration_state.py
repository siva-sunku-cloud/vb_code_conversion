from pydantic import BaseModel, Field
from typing import Optional
from pathlib import Path
from enum import Enum
from datetime import datetime


class ModuleStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    DOCUMENTED = "documented"
    ARCHITECTED = "architected"
    HUMAN_REVIEW = "human_review"
    TESTS_GENERATED = "tests_generated"
    CONVERTING = "converting"
    COMPLETED = "completed"
    FAILED = "failed"


class MigrationRequest(BaseModel):
    source_dir: Path
    output_dir: Path
    max_retries: int = 3
    complexity_threshold: float = 0.7


class ModuleState(BaseModel):
    name: str
    vb_file_path: str
    status: ModuleStatus = ModuleStatus.PENDING
    retry_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    # artifact_type → file path on disk
    artifacts: dict[str, str] = Field(default_factory=dict)
    error: Optional[str] = None


class GlobalMigrationState(BaseModel):
    request: MigrationRequest
    vb_source_files: list[str] = Field(default_factory=list)
    dependency_graph: dict[str, list[str]] = Field(default_factory=dict)
    modules: dict[str, ModuleState] = Field(default_factory=dict)
    migration_log: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.now)
    completed_modules: int = 0
    failed_modules: int = 0
