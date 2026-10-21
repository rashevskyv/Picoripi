"""Shared glossary management for Project Manager groups: validation, conversion, linking, unlinking and project updates."""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from core.glossary.manager import GlossaryManager
from core.glossary.series import (
    GROUP_METADATA_KEY,
    entries_from_json,
    import_series_glossary,
    series_chain,
    series_dir,
)
from core.i18n import tr
from core.project.persist_mixin import (
    is_latest_project_sequence,
    project_persistence_lock,
)
from core.project_library import registry
from utils.atomic_io import atomic_write_bytes, atomic_write_json, atomic_write_text
from utils.logging_utils import log_debug, log_error
from utils.thread_utils import WorkerThread


def same_project_file(first: str | os.PathLike, second: str | os.PathLike) -> bool:
    """True when two paths point to the same project file."""
    return registry.project_key(first) == registry.project_key(second)


def read_project_group_glossary(project_file: str | os.PathLike) -> Optional[str]:
    """Read the current ``group_series_glossary`` metadata without modifying the file."""
    path = Path(project_file)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            metadata = data.get("metadata")
            if isinstance(metadata, dict):
                return metadata.get(GROUP_METADATA_KEY)
    except Exception as exc:
        log_debug(f"Could not read metadata from {path}: {exc}")
    return None


def update_project_group_glossary(
    project_file: str | os.PathLike,
    glossary_path: Optional[str | os.PathLike],
    request_seq: Optional[int] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    is_rollback: bool = False,
) -> bool:
    """Set or remove ``metadata['group_series_glossary']`` in the project file on disk atomically.

    Returns True if the file was changed and written, False if it was already matching.
    Raises OSError or ValueError if reading, validation or writing fails.
    Raises InterruptedError if superseded or cancelled before commit.
    """
    path = Path(project_file)
    if not path.is_file():
        raise FileNotFoundError(f"Project file does not exist: {path}")

    resolved = str(Path(glossary_path).resolve()) if glossary_path and str(glossary_path).strip() else None

    with project_persistence_lock(path):
        if not is_rollback:
            if is_cancelled is not None and is_cancelled():
                raise InterruptedError(f"Update for {path} was cancelled")
            if request_seq is not None and not is_latest_project_sequence(path, request_seq):
                raise InterruptedError(f"Update for {path} was superseded (seq {request_seq})")

        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise OSError(f"Could not read project file {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Project file {path} content is not a JSON object (type: {type(data).__name__})")
        metadata = data.get("metadata")
        if metadata is None:
            metadata = {}
            data["metadata"] = metadata
        elif not isinstance(metadata, dict):
            raise ValueError(f"Project file {path} metadata is not a JSON object (type: {type(metadata).__name__})")

        current_val = metadata.get(GROUP_METADATA_KEY)
        if resolved is not None:
            if current_val == resolved:
                return False
            metadata[GROUP_METADATA_KEY] = resolved
        else:
            if GROUP_METADATA_KEY not in metadata:
                return False
            metadata.pop(GROUP_METADATA_KEY, None)

        if not is_rollback:
            if is_cancelled is not None and is_cancelled():
                raise InterruptedError(f"Update for {path} was cancelled")
            if request_seq is not None and not is_latest_project_sequence(path, request_seq):
                raise InterruptedError(f"Update for {path} was superseded (seq {request_seq})")

        try:
            atomic_write_json(path, data, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            raise OSError(f"Could not update project file {path}: {exc}") from exc


class MutationResult(list):
    """A list of updated project file paths that also acts as a rollback callable if registry saving fails."""

    def __init__(self, items: Iterable[str] = (), rollback_fn: Optional[Callable[[], None]] = None):
        super().__init__(items)
        self._rollback_fn = rollback_fn

    def __call__(self) -> None:
        if callable(self._rollback_fn):
            self._rollback_fn()


def apply_folder_glossary_mutation(
    reg: registry.Registry,
    folder_id: str,
    glossary_path: Optional[str | os.PathLike],
    open_project_file: Optional[str] = None,
) -> MutationResult:
    """Store the glossary on the folder and update each project in that folder on disk (open project skipped)."""
    target = str(Path(glossary_path).resolve()) if glossary_path and str(glossary_path).strip() else None
    reg.set_folder_glossary(folder_id, target)

    updated: List[str] = []
    modified_history: List[Tuple[str, Optional[str]]] = []

    for entry in reg.document["projects"]:
        if entry.get("folder_id") == folder_id:
            p_path = entry["path"]
            if open_project_file and same_project_file(p_path, open_project_file):
                continue
            prev = read_project_group_glossary(p_path)
            try:
                changed = update_project_group_glossary(p_path, target)
                if changed:
                    modified_history.append((p_path, prev))
                updated.append(p_path)
            except Exception as exc:
                log_error(f"Failed to update group glossary for {p_path}: {exc}")
                for m_path, m_prev in reversed(modified_history):
                    try:
                        update_project_group_glossary(m_path, m_prev, is_rollback=True)
                    except Exception as rb_exc:
                        log_error(f"Rollback failed for {m_path}: {rb_exc}")
                raise OSError(f"Failed to apply group glossary mutation on {p_path}: {exc}") from exc

    def rollback() -> None:
        for m_path, m_prev in reversed(modified_history):
            try:
                update_project_group_glossary(m_path, m_prev, is_rollback=True)
            except Exception as rb_exc:
                log_error(f"Rollback failed for {m_path}: {rb_exc}")

    return MutationResult(updated, rollback)


class GroupGlossaryFileJob(WorkerThread):
    """Creates an empty glossary or validates and converts an existing one, off the UI thread."""

    done = pyqtSignal(str)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(
        self,
        mode: str,
        path: Path | str,
        target_dir: Optional[Path | str] = None,
        overwrite: bool = False,
        collision_free: bool = False,
    ):
        super().__init__()
        self._mode = mode
        self._path = Path(path)
        self._target_dir = Path(target_dir) if target_dir else series_dir()
        self._overwrite = overwrite
        self._collision_free = collision_free

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            if self._mode == "create":
                self._create()
            elif self._mode == "link":
                self._link()
            else:
                raise ValueError(f"Unknown mode: {self._mode}")
        except Exception as exc:
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            log_error(f"Group glossary file job failed: {exc}", exc_info=True)
            self.failed.emit(str(exc))

    def _create(self) -> None:
        target = self._path.resolve()
        if self.isInterruptionRequested():
            self.cancelled.emit()
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        if self.isInterruptionRequested():
            self.cancelled.emit()
            return
        if not target.exists():
            atomic_write_text(target, "[]\n")
        else:
            text = target.read_text(encoding="utf-8-sig")
            data = json.loads(text)
            entries_from_json(data)
        if self.isInterruptionRequested():
            self.cancelled.emit()
            return
        self.done.emit(str(target))

    def _link(self) -> None:
        source = self._path.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Glossary file does not exist: {source}")
        if self.isInterruptionRequested():
            self.cancelled.emit()
            return
        text = source.read_text(encoding="utf-8-sig")
        data = json.loads(text)
        entries_from_json(data)
        if self.isInterruptionRequested():
            self.cancelled.emit()
            return
        if isinstance(data, list):
            self.done.emit(str(source))
            return

        self._target_dir.mkdir(parents=True, exist_ok=True)
        target = self._resolve_target(source)
        if self.isInterruptionRequested():
            self.cancelled.emit()
            return
        target_existed_before = target.exists()
        original_bytes = target.read_bytes() if target_existed_before else None
        import_series_glossary(source, target)
        if self.isInterruptionRequested():
            if not target_existed_before and target.exists():
                try:
                    target.unlink()
                except OSError as exc:
                    log_error(f"Failed to remove target after cancellation {target}: {exc}")
                    self.failed.emit(f"Failed to clean up {target}: {exc}")
                    return
            elif target_existed_before and original_bytes is not None:
                try:
                    atomic_write_bytes(target, original_bytes)
                except OSError as exc:
                    log_error(f"Failed to restore original glossary {target}: {exc}")
                    self.failed.emit(f"Failed to restore {target}: {exc}")
                    return
            self.cancelled.emit()
            return
        self.done.emit(str(target.resolve()))

    def _resolve_target(self, source: Path) -> Path:
        base_target = (self._target_dir / f"{source.stem}.json").resolve()
        norm_source = os.path.normcase(str(source.resolve()))
        norm_base = os.path.normcase(str(base_target))

        if norm_base == norm_source:
            if self._collision_free:
                return self._find_collision_free(source.stem, norm_source)
            raise FileExistsError(f"Target destination is the source file itself: {source}")

        if base_target.exists():
            if self._overwrite and not self._collision_free:
                return base_target
            if self._collision_free:
                return self._find_collision_free(source.stem, norm_source)
            raise FileExistsError(f"Glossary destination already exists: {base_target}")

        return base_target

    def _find_collision_free(self, stem: str, norm_source: str) -> Path:
        counter = 1
        while True:
            candidate = (self._target_dir / f"{stem}_{counter}.json").resolve()
            norm_cand = os.path.normcase(str(candidate))
            if norm_cand != norm_source and not candidate.exists():
                return candidate
            counter += 1


class InspectGlossaryJob(WorkerThread):
    """Inspects a glossary file off the UI thread to determine conversion requirements."""

    done = pyqtSignal(bool)  # needs_conversion
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, source_path: Path | str):
        super().__init__()
        self._source_path = Path(source_path)

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            needs_conv, err = check_conversion_needed(self._source_path)
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            if err:
                self.failed.emit(err)
            else:
                self.done.emit(needs_conv)
        except Exception as exc:
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return
            log_error(f"Inspect glossary job failed: {exc}", exc_info=True)
            self.failed.emit(str(exc))


class OpenProjectSyncJob(WorkerThread):
    """Saves the open project's group glossary association and prepares series glossaries off the UI thread."""

    done = pyqtSignal(list, list)  # (managers: List[GlossaryManager], warnings: List[str])
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(
        self,
        project_file: Path | str,
        target_glossary_or_dict: Any,
        metadata: Dict[str, Any],
        request_seq: Optional[int] = None,
    ):
        super().__init__()
        self._project_file = Path(project_file)
        if isinstance(target_glossary_or_dict, dict):
            self._target_glossary = target_glossary_or_dict.get("metadata", {}).get(GROUP_METADATA_KEY)
        else:
            self._target_glossary = str(target_glossary_or_dict) if target_glossary_or_dict else None
        self._metadata = dict(metadata)
        self._request_seq = request_seq
        self.committed = False

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                self.cancelled.emit()
                return

            if self._request_seq is not None and not is_latest_project_sequence(self._project_file, self._request_seq):
                self.cancelled.emit()
                return

            # Commit point: update project on disk atomically without touching unrelated fields
            update_project_group_glossary(
                self._project_file,
                self._target_glossary,
                request_seq=self._request_seq,
                is_cancelled=self.isInterruptionRequested,
            )
            self.committed = True

            managers: list[GlossaryManager] = []
            warnings: list[str] = []

            # The chain lists folders on disk, so it is built here and not on the UI thread.
            chain = series_chain(SimpleNamespace(metadata=self._metadata), self._project_file.parent)
            for path in chain:
                if not path.is_file():
                    warnings.append(f"Glossary file missing: {path.name}")
                    continue
                try:
                    text = path.read_text(encoding="utf-8-sig")
                except OSError as exc:
                    warnings.append(f"Cannot read glossary {path.name}: {exc}")
                    continue
                if text.strip() and not text.lstrip().startswith("["):
                    warnings.append(f"Glossary {path.name} is not a glossary JSON list")
                    continue
                try:
                    gm = GlossaryManager()
                    gm.load_from_text(plugin_name=None, glossary_path=path, raw_text=text)
                    gm.get_entries()
                    managers.append(gm)
                except Exception as exc:
                    warnings.append(f"Failed to parse glossary {path.name}: {exc}")

            # Once committed, reconcile success consistently so live state agrees with disk
            self.done.emit(managers, warnings)

        except InterruptedError:
            self.cancelled.emit()
            return
        except Exception as exc:
            if not self.committed and self.isInterruptionRequested():
                self.cancelled.emit()
                return
            log_error(f"Open project sync job failed: {exc}", exc_info=True)
            self.failed.emit(str(exc))


def check_conversion_needed(source_path: Path) -> tuple[bool, Optional[str]]:
    """Check whether choosing this file requires converting a multi-source series document."""
    try:
        text = source_path.read_text(encoding="utf-8-sig")
        data = json.loads(text)
        if isinstance(data, list):
            entries_from_json(data)
            return False, None
        if isinstance(data, dict):
            entries_from_json(data)
            return True, None
        return False, "Not a recognized glossary format"
    except Exception as exc:
        return False, str(exc)


def prompt_new_shared_glossary(parent_widget: Any, folder_name: str) -> Optional[Path]:
    """Prompt the user for a new shared glossary JSON file location."""
    default_stem = f"{folder_name.strip() or 'group'}_glossary.json"
    dest, _ = QFileDialog.getSaveFileName(
        parent_widget,
        tr("New Shared Glossary"),
        str(series_dir() / default_stem),
        tr("Glossary JSON (*.json)"),
    )
    return Path(dest) if dest else None


def prompt_link_shared_glossary(parent_widget: Any) -> Optional[Path]:
    """Prompt the user to choose an existing shared glossary JSON file."""
    source, _ = QFileDialog.getOpenFileName(
        parent_widget,
        tr("Link or Import Shared Glossary"),
        str(series_dir()),
        tr("Glossary JSON (*.json)"),
    )
    return Path(source) if source else None


def confirm_unlink_shared_glossary(parent_widget: Any, folder_name: str) -> bool:
    """Ask the user to confirm unlinking the shared glossary."""
    answer = QMessageBox.question(
        parent_widget,
        tr("Unlink shared glossary"),
        tr("Unlink the shared glossary from group \"{name}\"?\n\nThe glossary file itself will not be deleted.", name=folder_name),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return answer == QMessageBox.StandardButton.Yes
