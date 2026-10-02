from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
import requests

from core.glossary.models import GlossaryEntry, GlossaryOccurrence, legacy_entry_id
from core.glossary.notes import _entry_to_dict
from core.i18n import tr
from utils.logging_utils import log_debug, log_info, log_error


def parse_timestamp(ts: Any) -> float:
    """Parse ISO timestamp string or numeric timestamp to epoch seconds float."""
    if not ts:
        return 0.0
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        cleaned = ts.strip()
        if not cleaned:
            return 0.0
        try:
            if cleaned.endswith("Z"):
                cleaned = cleaned[:-1] + "+00:00"
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            return 0.0
    return 0.0


@dataclass
class ConflictRecord:
    """A detected collision where a term was modified both locally and remotely with differing values."""

    original: str
    local_entry: Dict[str, Any]
    remote_entry: Dict[str, Any]
    local_time: str
    remote_time: str
    differing_fields: List[str]
    chosen_source: Optional[str] = None  # 'local' or 'remote'


@dataclass
class MergeResult:
    """Result of glossary diff & merge calculation."""

    merged_entries: List[Dict[str, Any]]
    pulled_count: int
    pushed_count: int
    conflicts: List[ConflictRecord]


def entries_differ(e1: Dict[str, Any], e2: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Determine whether significant fields between two glossary entries differ."""
    fields = [
        "original",   # the same entry (by id) renamed on one side
        "translation",
        "aliases",
        "status",
        "user_notes",
        "notes",
        "section",
        "translation_variants",
        "provisional",
        "suggested_name",
        "suggested_name_evidence",
        "profiled",
    ]
    differing: List[str] = []
    for f in fields:
        v1 = e1.get(f)
        v2 = e2.get(f)
        if v1 is None:
            v1 = ""
        if v2 is None:
            v2 = ""
        if isinstance(v1, tuple):
            v1 = list(v1)
        if isinstance(v2, tuple):
            v2 = list(v2)
        if v1 != v2:
            differing.append(f)
    return bool(differing), differing


def entry_id(entry: Dict[str, Any]) -> str:
    """The entry's id; for one stored before ids existed, the id its term implies."""
    return str(entry.get("id") or "") or legacy_entry_id(str(entry.get("original") or ""))


def _is_live(entry: Any) -> bool:
    return isinstance(entry, dict) and bool(entry.get("original")) and not entry.get("deleted_at")


def _tombstones(entries: Sequence[Any]) -> Dict[str, Dict[str, Any]]:
    """Deletion records in a glossary list, by the id of the entry they deleted."""
    return {entry_id(e): dict(e) for e in entries if isinstance(e, dict) and e.get("deleted_at")}


def _buried(entry: Dict[str, Any], stones: Dict[str, Dict[str, Any]]) -> bool:
    """Whether ``entry`` was deleted on the other side after it was last changed here."""
    stone = stones.get(entry_id(entry))
    return stone is not None and parse_timestamp(stone.get("deleted_at")) >= parse_timestamp(entry.get("updated_at"))


def keep_local_deletions(local_entries: Sequence[Any], remote_entries: Sequence[Any]) -> List[Any]:
    """``remote_entries`` as a plain pull may store them: without what was deleted here."""
    stones = _tombstones(local_entries)
    kept = [e for e in remote_entries if not (_is_live(e) and _buried(e, stones))]
    known = {entry_id(e) for e in kept if isinstance(e, dict)}
    return kept + [stone for stone_id, stone in stones.items() if stone_id not in known]


def merge_glossaries(
    local_entries: List[Dict[str, Any]],
    remote_entries: List[Dict[str, Any]],
    local_mtime: float = 0.0,
    remote_mtime: float = 0.0,
) -> MergeResult:
    """Perform smart diff-based merge of local and remote glossary entries.

    Compares timestamps per entry (or fallback to file/remote mtime) to take
    whichever was updated more recently. Flags true collisions (same term modified
    differently within 2 seconds) as conflicts for user review.
    """
    # Deletions first. Without them a merge is a union, and every entry deleted
    # on one side came back from the other on the next sync.
    local_stones = _tombstones(local_entries)
    remote_stones = _tombstones(remote_entries)
    local_live = [e for e in local_entries if _is_live(e)]
    remote_live = [e for e in remote_entries if _is_live(e)]
    pulled_count = sum(1 for e in local_live if _buried(e, remote_stones))
    pushed_count = sum(1 for e in remote_live if _buried(e, local_stones))
    local_entries = [e for e in local_live if not _buried(e, remote_stones)]
    remote_entries = [e for e in remote_live if not _buried(e, local_stones)]

    loc_map: Dict[str, Dict[str, Any]] = {e["original"]: dict(e) for e in local_entries}
    # A remote entry is the local entry with the same id, whatever either side
    # calls it now (a rename); failing that, the one with the same term.
    local_by_id = {entry_id(e): e["original"] for e in local_entries}
    rem_map: Dict[str, Dict[str, Any]] = {}
    for e in remote_entries:
        key = e["original"] if e["original"] in loc_map else local_by_id.get(entry_id(e), e["original"])
        rem_map[key] = dict(e)

    # Maintain existing order of local entries, then append remote-only entries
    ordered_keys: List[str] = list(dict.fromkeys([*loc_map, *rem_map]))

    merged: List[Dict[str, Any]] = []
    conflicts: List[ConflictRecord] = []

    for key in ordered_keys:
        in_loc = key in loc_map
        in_rem = key in rem_map

        if in_loc and not in_rem:
            # Term added locally
            merged.append(loc_map[key])
            pushed_count += 1
        elif in_rem and not in_loc:
            # Term added remotely
            merged.append(rem_map[key])
            pulled_count += 1
        else:
            loc_e = loc_map[key]
            rem_e = rem_map[key]
            differs, diff_fields = entries_differ(loc_e, rem_e)
            if not differs:
                # Content matches: preserve whichever has timestamp
                entry_to_keep = dict(loc_e)
                if not entry_to_keep.get("updated_at") and rem_e.get("updated_at"):
                    entry_to_keep["updated_at"] = rem_e["updated_at"]
                merged.append(entry_to_keep)
            else:
                # Content differs: determine newer version
                t_loc_str = loc_e.get("updated_at", "")
                t_rem_str = rem_e.get("updated_at", "")
                t_loc = parse_timestamp(t_loc_str) or local_mtime
                t_rem = parse_timestamp(t_rem_str) or remote_mtime

                time_diff = t_rem - t_loc
                if time_diff > 2.0:
                    # Remote is newer
                    merged.append(rem_e)
                    pulled_count += 1
                elif time_diff < -2.0:
                    # Local is newer
                    merged.append(loc_e)
                    pushed_count += 1
                else:
                    # Simultaneous or ambiguous collision -> conflict
                    conflict = ConflictRecord(
                        original=key,
                        local_entry=loc_e,
                        remote_entry=rem_e,
                        local_time=t_loc_str or (datetime.fromtimestamp(t_loc, tz=timezone.utc).isoformat() if t_loc else "unknown"),
                        remote_time=t_rem_str or (datetime.fromtimestamp(t_rem, tz=timezone.utc).isoformat() if t_rem else "unknown"),
                        differing_fields=diff_fields,
                    )
                    conflicts.append(conflict)
                    # Temporary entry pending resolution
                    merged.append(loc_e)

    # The deletions travel with the glossary, so the other side learns of them
    # -- except one whose entry came back newer than the deletion.
    alive = {entry_id(e) for e in merged}
    merged.extend(stone for stone_id, stone in {**remote_stones, **local_stones}.items() if stone_id not in alive)

    return MergeResult(
        merged_entries=merged,
        pulled_count=pulled_count,
        pushed_count=pushed_count,
        conflicts=conflicts,
    )


def apply_conflict_resolutions(
    merge_result: MergeResult,
    resolutions: Dict[str, str],
) -> MergeResult:
    """Apply resolved choices ('local' or 'remote') to a MergeResult."""
    merged = list(merge_result.merged_entries)
    pulled = merge_result.pulled_count
    pushed = merge_result.pushed_count
    remaining_conflicts: List[ConflictRecord] = []

    for conf in merge_result.conflicts:
        choice = resolutions.get(conf.original)
        if choice == "remote":
            conf.chosen_source = "remote"
            pulled += 1
            for i, e in enumerate(merged):
                if e.get("original") == conf.original:
                    merged[i] = conf.remote_entry
                    break
        elif choice == "local":
            conf.chosen_source = "local"
            pushed += 1
            for i, e in enumerate(merged):
                if e.get("original") == conf.original:
                    merged[i] = conf.local_entry
                    break
        else:
            remaining_conflicts.append(conf)

    return MergeResult(
        merged_entries=merged,
        pulled_count=pulled,
        pushed_count=pushed,
        conflicts=remaining_conflicts,
    )


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
        entries: Optional[Sequence[Union[GlossaryEntry, Dict[str, Any]]]] = None,
        occurrence_map: Optional[Dict[str, List[GlossaryOccurrence]]] = None,
        reference_data: Optional[Dict[Tuple[int, int], str]] = None,
    ) -> Tuple[bool, str, int]:
        """Push glossary and occurrences context to the companion server."""
        if not self.is_configured:
            return False, "Companion server URL or API token is not configured.", 0

        # Prepare glossary payload
        serialized_entries: List[Dict[str, Any]] = []
        if entries:
            serialized_entries = [
                e if isinstance(e, dict) else _entry_to_dict(e)
                for e in entries
            ]
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

            # Compare with existing local glossary to count how many entries actually changed
            changed_count = 0
            local_entries = []
            if glossary_path and glossary_path.exists():
                try:
                    local_entries = json.loads(glossary_path.read_text(encoding="utf-8"))
                except Exception:
                    local_entries = []

            # A pull replaces the local file; what was deleted here stays deleted.
            remote_glossary = keep_local_deletions(local_entries, remote_glossary)
            local_lookup = {e.get("original", ""): e for e in local_entries if isinstance(e, dict)}
            for remote_entry in remote_glossary:
                orig = remote_entry.get("original", "")
                local_entry = local_lookup.get(orig)
                if local_entry is None:
                    changed_count += 1
                else:
                    if (
                        local_entry.get("translation") != remote_entry.get("translation")
                        or local_entry.get("status") != remote_entry.get("status")
                        or local_entry.get("notes") != remote_entry.get("notes")
                        or local_entry.get("user_notes") != remote_entry.get("user_notes")
                        or local_entry.get("section") != remote_entry.get("section")
                        or local_entry.get("translation_variants") != remote_entry.get("translation_variants")
                    ):
                        changed_count += 1

            if len(local_entries) > len(remote_glossary):
                changed_count += (len(local_entries) - len(remote_glossary))

            # Only write to disk if there are actual changes or if file didn't exist
            if changed_count > 0 or not (glossary_path and glossary_path.exists()):
                if glossary_path and glossary_path.exists():
                    bak_path = glossary_path.with_suffix(".json.bak")
                    try:
                        bak_path.write_bytes(glossary_path.read_bytes())
                        log_debug(f"CompanionSyncClient: Created backup at {bak_path}")
                    except Exception as e:
                        log_error(f"CompanionSyncClient: Backup creation failed: {e}")

                if glossary_path:
                    raw_json = json.dumps(remote_glossary, ensure_ascii=False, indent=2) + "\n"
                    glossary_path.write_text(raw_json, encoding="utf-8")
                    log_info(f"CompanionSyncClient: Pulled and saved {changed_count} updated terms to {glossary_path}")

                return True, f"Successfully pulled {changed_count} updated terms from Companion server.", changed_count
            else:
                log_debug(f"CompanionSyncClient: Local glossary is already in sync with server ({len(remote_glossary)} terms).")
                return True, "Glossary is already in sync with Companion server.", 0
        except requests.exceptions.RequestException as e:
            log_error(f"CompanionSyncClient: Pull failed: {e}")
            return False, f"Failed to pull from companion server: {e}", 0

    def sync_project(
        self,
        project_name: str,
        glossary_path: Path,
        entries: Optional[Sequence[GlossaryEntry]] = None,
        occurrence_map: Optional[Dict[str, List[GlossaryOccurrence]]] = None,
        reference_data: Optional[Dict[Tuple[int, int], str]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, str, int, int, List[ConflictRecord], Optional[MergeResult]]:
        """Perform bidirectional diff & merge between local glossary and Companion server."""
        if not self.is_configured:
            return False, "Companion server URL or API token is not configured.", 0, 0, [], None

        if on_status:
            on_status(tr("Connecting to Companion server…"))

        try:
            url = f"{self.server_url}/api/sync/pull"
            resp = requests.get(
                url,
                headers=self._get_headers(),
                params={"project": project_name},
                timeout=self.timeout,
            )

            # If project is not found or has no terms on server, push local if available
            if resp.status_code == 404 or (resp.status_code == 200 and not resp.json().get("glossary")):
                local_has_terms = bool(entries) or (glossary_path and glossary_path.exists())
                if local_has_terms:
                    if on_status:
                        on_status(tr("Uploading initial glossary to Companion server…"))
                    ok, msg, count = self.push_project(
                        project_name=project_name,
                        glossary_path=glossary_path,
                        entries=entries,
                        occurrence_map=occurrence_map,
                        reference_data=reference_data,
                    )
                    return ok, msg, 0, count, [], None
                return True, "No glossary terms to synchronize.", 0, 0, [], None

            if resp.status_code != 200:
                if resp.status_code == 401:
                    return False, "Authentication failed: invalid token or PIN.", 0, 0, [], None
                return False, f"Server error {resp.status_code}: {resp.text}", 0, 0, [], None

            data = resp.json()
            remote_glossary = data.get("glossary", [])
            remote_mtime = parse_timestamp(data.get("updated_at", ""))

            local_mtime = (
                glossary_path.stat().st_mtime
                if (glossary_path and glossary_path.exists())
                else 0.0
            )

            local_entries_dict: List[Dict[str, Any]] = []
            file_entries: List[Dict[str, Any]] = []
            if glossary_path and glossary_path.exists():
                try:
                    file_entries = json.loads(glossary_path.read_text(encoding="utf-8"))
                except Exception as exc:
                    log_error(f"CompanionSyncClient: Failed reading local glossary: {exc}")
            if entries:
                # Entry objects carry no deletions; those are in the file.
                local_entries_dict = [_entry_to_dict(e) for e in entries] + list(_tombstones(file_entries).values())
            else:
                local_entries_dict = file_entries

            if on_status:
                on_status(tr("Analyzing local and remote glossary changes…"))

            merge_res = merge_glossaries(
                local_entries=local_entries_dict,
                remote_entries=remote_glossary,
                local_mtime=local_mtime,
                remote_mtime=remote_mtime,
            )

            if merge_res.conflicts:
                return (
                    True,
                    tr("Conflicts detected between local and remote entries."),
                    merge_res.pulled_count,
                    merge_res.pushed_count,
                    merge_res.conflicts,
                    merge_res,
                )

            return self.commit_merge(
                project_name=project_name,
                glossary_path=glossary_path,
                merge_result=merge_res,
                occurrence_map=occurrence_map,
                reference_data=reference_data,
                on_status=on_status,
            )
        except requests.exceptions.RequestException as e:
            log_error(f"CompanionSyncClient: Sync failed: {e}")
            return False, f"Failed to sync with Companion server: {e}", 0, 0, [], None

    def commit_merge(
        self,
        project_name: str,
        glossary_path: Path,
        merge_result: MergeResult,
        occurrence_map: Optional[Dict[str, List[GlossaryOccurrence]]] = None,
        reference_data: Optional[Dict[Tuple[int, int], str]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, str, int, int, List[ConflictRecord], Optional[MergeResult]]:
        """Commit merged glossary locally and push necessary updates to Companion server."""
        pulled = merge_result.pulled_count
        pushed = merge_result.pushed_count
        merged_entries = merge_result.merged_entries

        # 1. Update local file if pulled terms exist or if local file was missing
        if pulled > 0 or not (glossary_path and glossary_path.exists()):
            if on_status:
                on_status(tr("Saving updated terms to local glossary…"))
            if glossary_path and glossary_path.exists():
                bak_path = glossary_path.with_suffix(".json.bak")
                try:
                    bak_path.write_bytes(glossary_path.read_bytes())
                    log_debug(f"CompanionSyncClient: Backup created at {bak_path}")
                except Exception as exc:
                    log_error(f"CompanionSyncClient: Backup creation failed: {exc}")

            if glossary_path:
                try:
                    raw_json = json.dumps(merged_entries, ensure_ascii=False, indent=2) + "\n"
                    glossary_path.write_text(raw_json, encoding="utf-8")
                    log_info(f"CompanionSyncClient: Saved {pulled} pulled terms to {glossary_path}")
                except Exception as exc:
                    log_error(f"CompanionSyncClient: Failed writing local glossary: {exc}")
                    return False, f"Failed writing local glossary: {exc}", 0, 0, [], merge_result

        # 2. Push to server if local updates or additions exist
        if pushed > 0:
            if on_status:
                on_status(tr("Pushing local updates to Companion server…"))
            ok, msg, count = self.push_project(
                project_name=project_name,
                glossary_path=glossary_path,
                entries=merged_entries,
                occurrence_map=occurrence_map,
                reference_data=reference_data,
            )

            if not ok:
                return False, f"Failed to push updates to Companion server: {msg}", pulled, 0, [], merge_result

        if pulled == 0 and pushed == 0:
            msg = tr("Glossary is already in sync with Companion.")
        else:
            msg = tr("Synchronized successfully: {pulled} pulled, {pushed} pushed.").format(
                pulled=pulled, pushed=pushed
            )

        return True, msg, pulled, pushed, [], merge_result


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


class CompanionSyncWorker(QThread):
    """Background worker for smart bidirectional synchronization with Companion server."""

    progress_status = pyqtSignal(str)
    conflicts_detected = pyqtSignal(list, object)  # (List[ConflictRecord], MergeResult)
    finished_with_result = pyqtSignal(bool, str, int, int)  # (ok, msg, pulled_count, pushed_count)

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
        ok, msg, pulled, pushed, conflicts, merge_result = self.client.sync_project(
            project_name=self.project_name,
            glossary_path=self.glossary_path,
            entries=self.entries,
            occurrence_map=self.occurrence_map,
            reference_data=self.reference_data,
            on_status=self.progress_status.emit,
        )
        if conflicts:
            self.conflicts_detected.emit(conflicts, merge_result)
        else:
            self.finished_with_result.emit(ok, msg, pulled, pushed)



def get_companion_client_from_mw(mw: Any, timeout: int = 15) -> Optional[CompanionSyncClient]:
    """Retrieve configured CompanionSyncClient from MainWindow or settings manager."""
    if not mw:
        return None
    settings_mgr = getattr(mw, "settings_manager", None)
    server_url = (settings_mgr.get("companion_server_url", "") if settings_mgr else "") or getattr(mw, "companion_server_url", "")
    token = (settings_mgr.get("companion_api_token", "") if settings_mgr else "") or getattr(mw, "companion_api_token", "picoripi")
    auto_sync = settings_mgr.get("companion_auto_sync", None) if settings_mgr else None
    if auto_sync is None:
        auto_sync = getattr(mw, "companion_auto_sync", None)

    if not server_url:
        try:
            import json
            from utils.constants import SETTINGS_FILE_PATH
            if Path(SETTINGS_FILE_PATH).exists():
                with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
                    disk_data = json.load(f)
                    server_url = disk_data.get("companion_server_url", "")
                    token = disk_data.get("companion_api_token", token or "picoripi")
                    if auto_sync is None:
                        auto_sync = disk_data.get("companion_auto_sync", True)
        except Exception:
            pass

    if auto_sync is None:
        auto_sync = True

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
    glossary_handler = getattr(trans_handler, "glossary_handler", None) if trans_handler else None
    glossary_mgr = (
        getattr(mw, "glossary_manager", None)
        or (getattr(glossary_handler, "glossary_manager", None) if glossary_handler else None)
        or (getattr(trans_handler, "glossary_manager", None) if trans_handler else None)
    )

    glossary_path = None
    if glossary_mgr and getattr(glossary_mgr, "glossary_path", None):
        glossary_path = glossary_mgr.glossary_path
    if not glossary_path and project_mgr:
        # Check project_dir or project_file_path
        p_dir = getattr(project_mgr, "project_dir", None)
        if not p_dir and getattr(project_mgr, "project_file_path", None):
            try:
                p_dir = Path(project_mgr.project_file_path).parent
            except Exception:
                p_dir = None
        if p_dir:
            p_dir = Path(p_dir)
            if (p_dir / "glossary.json").exists():
                glossary_path = p_dir / "glossary.json"
            elif (p_dir / "glossary.md").exists():
                glossary_path = p_dir / "glossary.md"
            else:
                glossary_path = p_dir / "glossary.json"

    # Ensure glossary_mgr has the resolved path bound if it wasn't yet
    if glossary_mgr and glossary_path and not getattr(glossary_mgr, "glossary_path", None):
        glossary_mgr._glossary_path = glossary_path

    return project_name, glossary_path, glossary_mgr


def auto_pull_in_background(mw: Any, on_completed: Optional[Any] = None) -> Optional[CompanionPullWorker]:
    """Automatically pull reviewed glossary from companion server in background without blocking UI."""
    client = get_companion_client_from_mw(mw)
    if not client or not client.is_configured:
        return None

    # Debounce checks: don't pull if worker already running or pulled within last 3 seconds
    existing_worker = getattr(mw, "_companion_pull_worker", None)
    if isinstance(existing_worker, CompanionPullWorker) and existing_worker.isRunning():
        return None
    import time
    now = time.time()
    last_pull = getattr(mw, "_last_companion_pull_ts", 0.0)
    if isinstance(last_pull, (int, float)) and now - last_pull < 3.0:
        return None
    mw._last_companion_pull_ts = now

    project_name, glossary_path, glossary_mgr = resolve_project_glossary_info(mw)
    if not project_name or not glossary_path:
        return None

    worker = CompanionPullWorker(client, project_name, glossary_path)

    def on_finished(ok: bool, msg: str, count: int):
        if ok:
            if count > 0:
                log_info(f"Companion auto-sync: Pulled {count} updated terms for '{project_name}'.")
                if glossary_mgr:
                    if hasattr(glossary_mgr, "refresh_from_disk"):
                        try:
                            glossary_mgr.refresh_from_disk()
                        except Exception as exc:
                            log_debug(f"Companion auto-sync refresh glossary error: {exc}")
                    elif hasattr(glossary_mgr, "load_from_disk"):
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

                glossary_handler = getattr(mw, "glossary_handler", None) or getattr(trans_handler, "glossary_handler", None)
                if glossary_handler and hasattr(glossary_handler, "refresh_open_dialog"):
                    try:
                        glossary_handler.refresh_open_dialog()
                    except Exception as exc:
                        log_debug(f"Companion auto-sync refresh dialog error: {exc}")

                sb = mw.statusBar() if callable(getattr(mw, "statusBar", None)) else getattr(mw, "statusBar", None)
                if sb and hasattr(sb, "showMessage"):
                    sb.showMessage(tr("Companion: auto-synced {count} updated terms from server.").format(count=count), 5000)
            else:
                log_info(f"Companion auto-sync: '{project_name}' is in sync with server.")
                sb = mw.statusBar() if callable(getattr(mw, "statusBar", None)) else getattr(mw, "statusBar", None)
                if sb and hasattr(sb, "showMessage"):
                    sb.showMessage(tr("Companion: glossary is in sync with server."), 3000)
        else:
            log_debug(f"Companion auto-sync pull: {msg}")
            # If server has no terms yet for this project, and local has terms, auto-push initial glossary
            if "No glossary entries returned" in msg and glossary_path and glossary_path.exists():
                try:
                    log_info(f"Companion auto-sync: Server has no terms for '{project_name}'. Auto-pushing initial glossary...")
                    auto_push_in_background(mw)
                except Exception as exc:
                    log_debug(f"Failed to auto-push initial glossary: {exc}")

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

    existing_worker = getattr(mw, "_companion_push_worker", None)
    if isinstance(existing_worker, CompanionPushWorker) and existing_worker.isRunning():
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


def sync_push_on_close(mw: Any, show_dialog: bool = True) -> bool:
    """Synchronous diff-based sync on close to push local changes to Companion server."""
    client = get_companion_client_from_mw(mw, timeout=6)
    if not client or not client.is_configured:
        return False
    project_name, glossary_path, glossary_mgr = resolve_project_glossary_info(mw)
    if not project_name or not glossary_path:
        return False

    # Ensure any pending in-memory changes are persisted to disk
    if glossary_mgr and hasattr(glossary_mgr, "save_to_disk"):
        try:
            glossary_mgr.save_to_disk()
        except Exception as exc:
            log_debug(f"Companion auto-sync (on close): save_to_disk failed: {exc}")

    try:
        entries = glossary_mgr.get_entries() if glossary_mgr and hasattr(glossary_mgr, "get_entries") else None
        occurrence_map = glossary_mgr.get_occurrence_map() if glossary_mgr and hasattr(glossary_mgr, "get_occurrence_map") else None
        reference_data = getattr(getattr(mw, "data_store", None), "reference_data", None)

        is_testing = getattr(mw, "is_testing", False)
        from PyQt6.QtWidgets import QApplication, QWidget

        has_gui = QApplication.instance() is not None and isinstance(mw, QWidget) and not is_testing
        if has_gui and show_dialog:
            try:
                from components.companion.sync_dialog import CompanionSyncDialog
                dlg = CompanionSyncDialog(
                    parent=mw,
                    client=client,
                    project_name=project_name,
                    glossary_path=glossary_path,
                    entries=entries,
                    occurrence_map=occurrence_map,
                    reference_data=reference_data,
                    auto_start=True,
                    auto_close_ms=800,
                    is_closing=True,
                )
                dlg.exec()
                log_info(f"Companion auto-sync (on close dialog): finished with result {dlg.was_successful}")
                return dlg.was_successful
            except Exception as exc:
                log_debug(f"CompanionSyncDialog on close failed to display: {exc}")

        ok, msg, pulled, pushed, conflicts, merge_res = client.sync_project(
            project_name=project_name,
            glossary_path=glossary_path,
            entries=entries,
            occurrence_map=occurrence_map,
            reference_data=reference_data,
        )
        if ok:
            log_info(f"Companion auto-sync (on close): {pushed} pushed, {pulled} pulled.")
        else:
            log_debug(f"Companion auto-sync (on close) skipped/failed: {msg}")
        return ok
    except Exception as exc:
        log_debug(f"Companion sync_push_on_close exception: {exc}")
        return False



def smart_sync_in_background(mw: Any, on_completed: Optional[Any] = None) -> Optional[CompanionSyncWorker]:
    """Execute smart background synchronization with Companion server without blocking UI."""
    client = get_companion_client_from_mw(mw)
    if not client or not client.is_configured:
        return None

    existing_worker = getattr(mw, "_companion_sync_worker", None)
    if isinstance(existing_worker, CompanionSyncWorker) and existing_worker.isRunning():
        return None

    import time
    now = time.time()
    last_sync = getattr(mw, "_last_companion_sync_ts", 0.0)
    if isinstance(last_sync, (int, float)) and now - last_sync < 3.0:
        return None
    mw._last_companion_sync_ts = now

    project_name, glossary_path, glossary_mgr = resolve_project_glossary_info(mw)
    if not project_name or not glossary_path:
        return None

    entries = glossary_mgr.get_entries() if glossary_mgr and hasattr(glossary_mgr, "get_entries") else None
    occurrence_map = glossary_mgr.get_occurrence_map() if glossary_mgr and hasattr(glossary_mgr, "get_occurrence_map") else None
    reference_data = getattr(getattr(mw, "data_store", None), "reference_data", None)

    worker = CompanionSyncWorker(
        client=client,
        project_name=project_name,
        glossary_path=glossary_path,
        entries=entries,
        occurrence_map=occurrence_map,
        reference_data=reference_data,
    )

    def on_finished(ok: bool, msg: str, pulled: int, pushed: int):
        if ok and pulled > 0:
            if glossary_mgr:
                if hasattr(glossary_mgr, "refresh_from_disk"):
                    glossary_mgr.refresh_from_disk()
                elif hasattr(glossary_mgr, "load_from_disk"):
                    glossary_mgr.load_from_disk()
            trans_handler = getattr(mw, "translation_handler", None)
            if trans_handler and hasattr(trans_handler, "initialize_glossary_highlighting"):
                try:
                    trans_handler.initialize_glossary_highlighting()
                except Exception:
                    pass
            active_dialog = getattr(trans_handler, "_active_glossary_dialog", None) if trans_handler else None
            if active_dialog and hasattr(active_dialog, "reload_data"):
                try:
                    active_dialog.reload_data()
                except Exception:
                    pass
            glossary_handler = getattr(mw, "glossary_handler", None) or getattr(trans_handler, "glossary_handler", None)
            if glossary_handler and hasattr(glossary_handler, "refresh_open_dialog"):
                try:
                    glossary_handler.refresh_open_dialog()
                except Exception:
                    pass

        sb = mw.statusBar() if callable(getattr(mw, "statusBar", None)) else getattr(mw, "statusBar", None)
        if sb and hasattr(sb, "showMessage"):
            if ok:
                if pulled > 0 or pushed > 0:
                    sb.showMessage(tr("Companion: synchronized ({pulled} pulled, {pushed} pushed).").format(pulled=pulled, pushed=pushed), 5000)
                else:
                    sb.showMessage(tr("Companion: glossary is in sync with server."), 3000)
            else:
                log_debug(f"Companion smart sync: {msg}")

        if on_completed and callable(on_completed):
            on_completed(ok, msg, pulled, pushed)

        if hasattr(mw, "_companion_sync_worker") and mw._companion_sync_worker is worker:
            mw._companion_sync_worker = None

    worker.finished_with_result.connect(on_finished)
    mw._companion_sync_worker = worker
    worker.start()
    return worker
