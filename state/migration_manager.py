from pathlib import Path
from typing import Optional
from datetime import datetime

from models.migration_state import GlobalMigrationState, ModuleState, ModuleStatus
from utils.logger import get_logger

logger = get_logger(__name__)


class MigrationManager:
    """Maintains and persists the global migration state across all pipeline steps."""

    def __init__(self, state: GlobalMigrationState):
        self.state = state
        self._state_file: Optional[Path] = None

    def set_state_file(self, path: Path) -> None:
        self._state_file = path

    # ── Module lifecycle ──────────────────────────────────────────────────────

    def update_module_status(
        self,
        module_name: str,
        status: ModuleStatus,
        error: Optional[str] = None,
    ) -> None:
        module = self._get_module(module_name)
        module.status = status
        module.updated_at = datetime.now()
        if error:
            module.error = error
        if status == ModuleStatus.COMPLETED:
            self.state.completed_modules += 1
        elif status == ModuleStatus.FAILED:
            self.state.failed_modules += 1
        self.log(f"[{module_name}] → {status.value}" + (f" ({error})" if error else ""))
        self._persist()

    def add_artifact(self, module_name: str, artifact_type: str, file_path: str) -> None:
        self._get_module(module_name).artifacts[artifact_type] = file_path
        self._persist()

    def increment_retry(self, module_name: str) -> int:
        module = self._get_module(module_name)
        module.retry_count += 1
        self._persist()
        return module.retry_count

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_pending_modules(self) -> list[ModuleState]:
        return [m for m in self.state.modules.values() if m.status == ModuleStatus.PENDING]

    def get_artifact_path(self, module_name: str, artifact_type: str) -> Optional[str]:
        return self.state.modules.get(module_name, ModuleState(name="", vb_file_path="")).artifacts.get(artifact_type)

    # ── Logging ───────────────────────────────────────────────────────────────

    def log(self, message: str) -> None:
        entry = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
        self.state.migration_log.append(entry)
        logger.info(message)

    # ── Private ───────────────────────────────────────────────────────────────

    def _get_module(self, name: str) -> ModuleState:
        if name not in self.state.modules:
            raise KeyError(f"Module '{name}' not found in migration state.")
        return self.state.modules[name]

    def _persist(self) -> None:
        if self._state_file:
            self._state_file.write_text(self.state.model_dump_json(indent=2))
