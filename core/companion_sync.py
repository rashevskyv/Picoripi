"""Desktop sync client for Picoripi Companion Server."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import requests

from core.glossary.models import GlossaryEntry, GlossaryOccurrence
from core.glossary.notes import _entry_to_dict
from utils.logging_utils import log_debug, log_info, log_error


class CompanionSyncClient:
    """Client for synchronizing glossaries and context with Picoripi Companion Server."""

    def __init__(self, server_url: str, token: str, timeout: int = 15):
        clean_url = (server_url or "").strip().rstrip("/")
        self.server_url = clean_url
        self.token = (token or "").strip()
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        """Whether the sync client has a valid server URL and token."""
        return bool(self.server_url and self.token)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def test_connection(self) -> Tuple[bool, str]:
        """Test reachability and authentication with the companion server."""
        if not self.is_configured:
            return False, "Companion server URL or API token is not configured."

        try:
            url = f"{self.server_url}/api/projects"
            resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code == 200:
                projects = resp.json()
                return True, f"Connection successful! Found {len(projects)} project(s) on server."
            elif resp.status_code == 401:
                return False, "Authentication failed: invalid token or PIN."
            else:
                return False, f"Server returned error code {resp.status_code}: {resp.text}"
        except requests.exceptions.RequestException as e:
            return False, f"Failed to connect to companion server: {e}"

    def push_project(
        self,
        project_name: str,
        glossary_path: Path,
        entries: Optional[Sequence[GlossaryEntry]] = None,
        occurrence_map: Optional[Dict[str, List[GlossaryOccurrence]]] = None,
        reference_data: Optional[Dict[Tuple[int, int], str]] = None,
    ) -> Tuple[bool, str, int]:
        """Push glossary and occurrences context to the companion server."""
        if not self.is_configured:
            return False, "Companion server URL or API token is not configured.", 0

        # Prepare glossary payload
        serialized_entries: List[Dict[str, Any]] = []
        if entries:
            serialized_entries = [_entry_to_dict(e) for e in entries]
        elif glossary_path and glossary_path.exists():
            try:
                raw = glossary_path.read_text(encoding="utf-8")
                serialized_entries = json.loads(raw)
            except Exception as e:
                return False, f"Failed to read local glossary file: {e}", 0

        if not serialized_entries:
            return False, "No glossary entries to push.", 0

        # Prepare occurrences payload
        serialized_occurrences: Dict[str, List[Dict[str, Any]]] = {}
        if occurrence_map:
            ref_lookup = reference_data or {}
            for term, occs in occurrence_map.items():
                occ_list = []
                for occ in occs:
                    ref_text = ref_lookup.get((occ.block_idx, occ.string_idx), "")
                    occ_list.append({
                        "line_text": occ.line_text,
                        "kind": occ.kind,
                        "block_idx": occ.block_idx,
                        "string_idx": occ.string_idx,
                        "ref_text": ref_text,
                    })
                if occ_list:
                    serialized_occurrences[term] = occ_list

        payload = {
            "project_name": project_name,
            "glossary": serialized_entries,
            "occurrences": serialized_occurrences,
            "metadata": {
                "source": "Picoripi Desktop",
            },
        }

        try:
            url = f"{self.server_url}/api/sync/push"
            resp = requests.post(url, headers=self._get_headers(), json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                count = data.get("total_terms", len(serialized_entries))
                log_info(f"CompanionSyncClient: Pushed {count} terms to {self.server_url}")
                return True, f"Successfully pushed {count} terms to Companion server.", count
            elif resp.status_code == 401:
                return False, "Authentication failed: invalid token or PIN.", 0
            else:
                return False, f"Server error {resp.status_code}: {resp.text}", 0
        except requests.exceptions.RequestException as e:
            log_error(f"CompanionSyncClient: Push failed: {e}")
            return False, f"Failed to push to companion server: {e}", 0

    def pull_project(
        self,
        project_name: str,
        glossary_path: Path,
    ) -> Tuple[bool, str, int]:
        """Pull updated glossary from the companion server and update local file."""
        if not self.is_configured:
            return False, "Companion server URL or API token is not configured.", 0

        try:
            url = f"{self.server_url}/api/sync/pull"
            resp = requests.get(url, headers=self._get_headers(), params={"project": project_name}, timeout=self.timeout)
            if resp.status_code != 200:
                if resp.status_code == 401:
                    return False, "Authentication failed: invalid token or PIN.", 0
                return False, f"Server error {resp.status_code}: {resp.text}", 0

            data = resp.json()
            remote_glossary = data.get("glossary", [])
            if not remote_glossary:
                return False, f"No glossary entries returned for project '{project_name}'.", 0

            # Backup existing local glossary before overwriting
            if glossary_path and glossary_path.exists():
                bak_path = glossary_path.with_suffix(".json.bak")
                try:
                    bak_path.write_bytes(glossary_path.read_bytes())
                    log_debug(f"CompanionSyncClient: Created backup at {bak_path}")
                except Exception as e:
                    log_error(f"CompanionSyncClient: Backup creation failed: {e}")

            # Write updated glossary to disk
            if glossary_path:
                raw_json = json.dumps(remote_glossary, ensure_ascii=False, indent=2) + "\n"
                glossary_path.write_text(raw_json, encoding="utf-8")
                log_info(f"CompanionSyncClient: Pulled and saved {len(remote_glossary)} terms to {glossary_path}")

            return True, f"Successfully pulled {len(remote_glossary)} terms from Companion server.", len(remote_glossary)
        except requests.exceptions.RequestException as e:
            log_error(f"CompanionSyncClient: Pull failed: {e}")
            return False, f"Failed to pull from companion server: {e}", 0


try:
    from PyQt6.QtCore import QThread, pyqtSignal
except ImportError:
    class QThread:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

    class _MockSignal:
        def emit(self, *args, **kwargs):
            pass

        def connect(self, slot):
            pass

    def pyqtSignal(*args, **kwargs):  # type: ignore[no-redef]
        return _MockSignal()


class CompanionPullWorker(QThread):
    """Background worker for pulling glossary updates without blocking the UI."""
    finished_with_result = pyqtSignal(bool, str, int)

    def __init__(self, client: CompanionSyncClient, project_name: str, glossary_path: Path):
        super().__init__()
        self.client = client
        self.project_name = project_name
        self.glossary_path = glossary_path

    def run(self):
        ok, msg, count = self.client.pull_project(self.project_name, self.glossary_path)
        self.finished_with_result.emit(ok, msg, count)


class CompanionPushWorker(QThread):
    """Background worker for pushing glossary updates without blocking the UI."""
    finished_with_result = pyqtSignal(bool, str, int)

    def __init__(
        self,
        client: CompanionSyncClient,
        project_name: str,
        glossary_path: Path,
        entries: Optional[Sequence[GlossaryEntry]] = None,
        occurrence_map: Optional[Dict[str, List[GlossaryOccurrence]]] = None,
        reference_data: Optional[Dict[Tuple[int, int], str]] = None,
    ):
        super().__init__()
        self.client = client
        self.project_name = project_name
        self.glossary_path = glossary_path
        self.entries = entries
        self.occurrence_map = occurrence_map
        self.reference_data = reference_data

    def run(self):
        ok, msg, count = self.client.push_project(
            self.project_name,
            self.glossary_path,
            entries=self.entries,
            occurrence_map=self.occurrence_map,
            reference_data=self.reference_data,
        )
        self.finished_with_result.emit(ok, msg, count)


def get_companion_client_from_mw(mw: Any, timeout: int = 15) -> Optional[CompanionSyncClient]:
    """Retrieve configured CompanionSyncClient from MainWindow or settings manager."""
    if not mw:
        return None
    settings_mgr = getattr(mw, "settings_manager", None)
    server_url = settings_mgr.get("companion_server_url", "") if settings_mgr else getattr(mw, "companion_server_url", "")
    token = settings_mgr.get("companion_api_token", "") if settings_mgr else getattr(mw, "companion_api_token", "picoripi")
    auto_sync = settings_mgr.get("companion_auto_sync", True) if settings_mgr else getattr(mw, "companion_auto_sync", True)

    if not auto_sync or not server_url:
        return None
    return CompanionSyncClient(server_url, token, timeout=timeout)


def resolve_project_glossary_info(mw: Any) -> Tuple[Optional[str], Optional[Path], Optional[Any]]:
    """Resolve (project_name, glossary_path, glossary_manager) for the active project."""
    if not mw:
        return None, None, None
    project_mgr = getattr(mw, "project_manager", None)
    project_obj = getattr(project_mgr, "project", None) if project_mgr else None
    if not project_obj:
        return None, None, None
    project_name = getattr(project_obj, "name", "DefaultProject")

    trans_handler = getattr(mw, "translation_handler", None)
    glossary_mgr = getattr(mw, "glossary_manager", None)
    if not glossary_mgr and trans_handler:
        glossary_mgr = getattr(trans_handler, "glossary_manager", None)

    glossary_path = None
    if glossary_mgr and getattr(glossary_mgr, "glossary_path", None):
        glossary_path = glossary_mgr.glossary_path
    if not glossary_path and getattr(project_mgr, "project_path", None):
        candidate = Path(project_mgr.project_path).parent / "glossary.json"
        glossary_path = candidate

    return project_name, glossary_path, glossary_mgr


def auto_pull_in_background(mw: Any, on_completed: Optional[Any] = None) -> Optional[CompanionPullWorker]:
    """Automatically pull reviewed glossary from companion server in background without blocking UI."""
    client = get_companion_client_from_mw(mw)
    if not client or not client.is_configured:
        return None
    project_name, glossary_path, glossary_mgr = resolve_project_glossary_info(mw)
    if not project_name or not glossary_path:
        return None

    worker = CompanionPullWorker(client, project_name, glossary_path)

    def on_finished(ok: bool, msg: str, count: int):
        if ok and count > 0:
            log_info(f"Companion auto-sync: Pulled {count} terms for '{project_name}'.")
            if glossary_mgr and hasattr(glossary_mgr, "load_from_disk"):
                try:
                    glossary_mgr.load_from_disk()
                except Exception as exc:
                    log_debug(f"Companion auto-sync reload glossary error: {exc}")
            trans_handler = getattr(mw, "translation_handler", None)
            if trans_handler and hasattr(trans_handler, "initialize_glossary_highlighting"):
                try:
                    trans_handler.initialize_glossary_highlighting()
                except Exception as exc:
                    log_debug(f"Companion auto-sync highlight reinit error: {exc}")
            active_dialog = getattr(trans_handler, "_active_glossary_dialog", None) if trans_handler else None
            if active_dialog and hasattr(active_dialog, "reload_data"):
                try:
                    active_dialog.reload_data()
                except Exception as exc:
                    log_debug(f"Companion auto-sync reload dialog error: {exc}")
            if hasattr(mw, "statusBar") and mw.statusBar():
                mw.statusBar().showMessage(f"Companion: auto-synced {count} terms from server.", 4000)
        elif not ok:
            log_debug(f"Companion auto-sync pull skipped/failed: {msg}")

        if on_completed and callable(on_completed):
            on_completed(ok, msg, count)

        if hasattr(mw, "_companion_pull_worker") and mw._companion_pull_worker is worker:
            mw._companion_pull_worker = None

    worker.finished_with_result.connect(on_finished)
    mw._companion_pull_worker = worker
    worker.start()
    return worker


def auto_push_in_background(mw: Any, on_completed: Optional[Any] = None) -> Optional[CompanionPushWorker]:
    """Automatically push glossary and context to companion server in background without blocking UI."""
    client = get_companion_client_from_mw(mw)
    if not client or not client.is_configured:
        return None
    project_name, glossary_path, glossary_mgr = resolve_project_glossary_info(mw)
    if not project_name or not glossary_path:
        return None

    entries = glossary_mgr.get_entries() if glossary_mgr and hasattr(glossary_mgr, "get_entries") else None
    occurrence_map = glossary_mgr.get_occurrence_map() if glossary_mgr and hasattr(glossary_mgr, "get_occurrence_map") else None
    reference_data = getattr(getattr(mw, "data_store", None), "reference_data", None)

    worker = CompanionPushWorker(
        client,
        project_name,
        glossary_path,
        entries=entries,
        occurrence_map=occurrence_map,
        reference_data=reference_data,
    )

    def on_finished(ok: bool, msg: str, count: int):
        if ok:
            log_info(f"Companion auto-sync: Pushed {count} terms for '{project_name}'.")
        else:
            log_debug(f"Companion auto-sync push skipped/failed: {msg}")

        if on_completed and callable(on_completed):
            on_completed(ok, msg, count)

        if hasattr(mw, "_companion_push_worker") and mw._companion_push_worker is worker:
            mw._companion_push_worker = None

    worker.finished_with_result.connect(on_finished)
    mw._companion_push_worker = worker
    worker.start()
    return worker


def sync_push_on_close(mw: Any) -> None:
    """Fast synchronous push on close with short timeout to ensure server is updated."""
    client = get_companion_client_from_mw(mw, timeout=3)
    if not client or not client.is_configured:
        return
    project_name, glossary_path, glossary_mgr = resolve_project_glossary_info(mw)
    if not project_name or not glossary_path:
        return
    try:
        entries = glossary_mgr.get_entries() if glossary_mgr and hasattr(glossary_mgr, "get_entries") else None
        occurrence_map = glossary_mgr.get_occurrence_map() if glossary_mgr and hasattr(glossary_mgr, "get_occurrence_map") else None
        reference_data = getattr(getattr(mw, "data_store", None), "reference_data", None)
        ok, msg, count = client.push_project(
            project_name,
            glossary_path,
            entries=entries,
            occurrence_map=occurrence_map,
            reference_data=reference_data,
        )
        if ok:
            log_info(f"Companion auto-sync (on close): Pushed {count} terms.")
        else:
            log_debug(f"Companion auto-sync (on close) skipped/failed: {msg}")
    except Exception as exc:
        log_debug(f"Companion sync_push_on_close exception: {exc}")
