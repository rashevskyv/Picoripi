"""Storage manager for Picoripi Companion server."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from companion.server.models import GlossaryEntryUpdate, ProjectSummary
import logging


def sanitize_project_name(name: str) -> str:
    """Convert arbitrary project name into safe directory name."""
    clean = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name.strip())
    return clean or "default_project"


class StorageManager:
    """Manages project data persistence, backups and retrieval."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.projects_dir = self.data_dir / "projects"
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def _get_project_dir(self, project_name: str) -> Path:
        safe_name = sanitize_project_name(project_name)
        pdir = self.projects_dir / safe_name
        pdir.mkdir(parents=True, exist_ok=True)
        return pdir

    def list_projects(self) -> List[ProjectSummary]:
        """List all stored projects with basic statistics."""
        summaries: List[ProjectSummary] = []
        if not self.projects_dir.exists():
            return summaries

        for pdir in sorted(self.projects_dir.iterdir()):
            if not pdir.is_dir():
                continue
            glossary_file = pdir / "glossary.json"
            meta_file = pdir / "metadata.json"

            name = pdir.name
            updated_at = ""
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    name = meta.get("name", name)
                    updated_at = meta.get("updated_at", "")
                except Exception as exc:
                    logging.getLogger(__name__).debug("storage.StorageManager.list_projects: ignored %r", exc)

            if not updated_at and glossary_file.exists():
                mtime = glossary_file.stat().st_mtime
                updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

            total = 0
            confirmed = 0
            needs_review = 0
            if glossary_file.exists():
                try:
                    entries = [e for e in json.loads(glossary_file.read_text(encoding="utf-8")) if not e.get("deleted_at")]
                    total = len(entries)
                    for e in entries:
                        status = (e.get("status") or "").lower()
                        if status == "confirmed":
                            confirmed += 1
                        elif status in {"seeded", "fragments", "synthesized", "translated"} or len(e.get("translation_variants", [])) > 1:
                            needs_review += 1
                except Exception as exc:
                    logging.getLogger(__name__).debug("storage.StorageManager.list_projects: ignored %r", exc)

            summaries.append(
                ProjectSummary(
                    id=pdir.name,
                    name=name,
                    updated_at=updated_at,
                    total_terms=total,
                    confirmed_terms=confirmed,
                    needs_review_terms=needs_review,
                )
            )
        return summaries

    def save_project(
        self,
        project_name: str,
        glossary: List[Dict[str, Any]],
        occurrences: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProjectSummary:
        """Save pushed glossary, occurrences, and metadata with backup creation."""
        pdir = self._get_project_dir(project_name)
        glossary_file = pdir / "glossary.json"

        # Backup existing glossary before overwriting
        if glossary_file.exists():
            bak_file = pdir / "glossary.json.bak"
            try:
                bak_file.write_bytes(glossary_file.read_bytes())
            except Exception as exc:
                logging.getLogger(__name__).debug("storage.StorageManager.save_project: ignored %r", exc)

        now_iso = datetime.now(timezone.utc).isoformat()
        for entry in glossary:
            if not entry.get("updated_at") and not entry.get("deleted_at"):
                entry["updated_at"] = now_iso

        # Write new glossary atomically
        tmp_glossary = pdir / "glossary.json.tmp"
        tmp_glossary.write_text(json.dumps(glossary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_glossary.replace(glossary_file)

        # Save occurrences if provided
        if occurrences is not None:
            occ_file = pdir / "occurrences.json"
            tmp_occ = pdir / "occurrences.json.tmp"
            tmp_occ.write_text(json.dumps(occurrences, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            tmp_occ.replace(occ_file)

        # Update metadata
        meta_file = pdir / "metadata.json"
        now_iso = datetime.now(timezone.utc).isoformat()
        meta_data: Dict[str, Any] = {
            "name": project_name,
            "updated_at": now_iso,
        }
        if metadata:
            meta_data.update(metadata)
        meta_file.write_text(json.dumps(meta_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        glossary = [e for e in glossary if not e.get("deleted_at")]   # counted below; already written whole
        total = len(glossary)
        confirmed = sum(1 for e in glossary if (e.get("status") or "").lower() == "confirmed")
        needs_review = sum(
            1
            for e in glossary
            if (e.get("status") or "").lower() != "confirmed"
            and (
                (e.get("status") or "").lower() in {"seeded", "fragments", "synthesized", "translated"}
                or len(e.get("translation_variants", [])) > 1
            )
        )

        return ProjectSummary(
            id=pdir.name,
            name=project_name,
            updated_at=now_iso,
            total_terms=total,
            confirmed_terms=confirmed,
            needs_review_terms=needs_review,
        )

    def get_glossary(self, project_name: str, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Retrieve the glossary entries of a project.

        The stored list also holds deletion records (``deleted_at``) that the
        desktop sync needs; they are not entries, so only sync asks for them.
        """
        pdir = self._get_project_dir(project_name)
        glossary_file = pdir / "glossary.json"
        if not glossary_file.exists():
            return []
        try:
            entries = json.loads(glossary_file.read_text(encoding="utf-8"))
        except Exception:
            return []
        if include_deleted:
            return entries
        return [e for e in entries if not (isinstance(e, dict) and e.get("deleted_at"))]

    def get_occurrences(self, project_name: str, term: str) -> List[Dict[str, Any]]:
        """Retrieve occurrences for a specific term."""
        pdir = self._get_project_dir(project_name)
        occ_file = pdir / "occurrences.json"
        if not occ_file.exists():
            return []
        try:
            data = json.loads(occ_file.read_text(encoding="utf-8"))
            return data.get(term, [])
        except Exception:
            return []

    def update_entry(self, project_name: str, update: GlossaryEntryUpdate) -> Optional[Dict[str, Any]]:
        """Update an individual entry in the glossary and persist to disk."""
        pdir = self._get_project_dir(project_name)
        glossary_file = pdir / "glossary.json"
        if not glossary_file.exists():
            return None

        # The whole stored list, deletion records included: it is written back below.
        entries = self.get_glossary(project_name, include_deleted=True)
        target_entry = None
        for entry in entries:
            if entry.get("original") == update.original and not entry.get("deleted_at"):
                target_entry = entry
                break

        if target_entry is None:
            return None

        # Create backup before mutation
        bak_file = pdir / "glossary.json.bak"
        try:
            bak_file.write_bytes(glossary_file.read_bytes())
        except Exception as exc:
            logging.getLogger(__name__).debug("storage.StorageManager.update_entry: ignored %r", exc)

        # Apply update
        if update.translation is not None:
            target_entry["translation"] = update.translation
        if update.status is not None:
            target_entry["status"] = update.status
        if update.user_notes is not None:
            target_entry["user_notes"] = update.user_notes
        if update.notes is not None:
            target_entry["notes"] = update.notes
        if update.section is not None:
            target_entry["section"] = update.section
        now_iso = getattr(update, "updated_at", None) or datetime.now(timezone.utc).isoformat()
        target_entry["updated_at"] = now_iso

        # Write back safely
        tmp_glossary = pdir / "glossary.json.tmp"
        tmp_glossary.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_glossary.replace(glossary_file)

        # Update metadata timestamp
        meta_file = pdir / "metadata.json"
        meta = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception as exc:
                logging.getLogger(__name__).debug("storage.StorageManager.update_entry: ignored %r", exc)
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        return target_entry

    def get_metadata(self, project_name: str) -> Dict[str, Any]:
        """Retrieve metadata for project."""
        pdir = self._get_project_dir(project_name)
        meta_file = pdir / "metadata.json"
        if meta_file.exists():
            try:
                return json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception as exc:
                logging.getLogger(__name__).debug("storage.StorageManager.get_metadata: ignored %r", exc)
        return {"name": project_name, "updated_at": ""}


STRINGS_FILE = "strings.json"


class StringsStore:
    """The project's translation rows, for editing from the phone (``strings.json`` next to ``glossary.json``).

    A row holds ``translation`` (the text on the server) and ``base`` (what the desktop pushed last). A row whose
    ``translation`` differs from its ``base`` was changed on the phone and waits for the desktop to take it. The state
    lives here, so nothing new is written into the desktop project or session files.
    """

    def __init__(self, storage: StorageManager):
        self.storage = storage
        self._lock = threading.Lock()
        # ponytail: the parsed file per path, checked by mtime and size; enough for one process and one owner.
        self._cache: Dict[Path, Tuple[Tuple[int, int], Dict[str, Any]]] = {}

    def _path(self, project: str) -> Path:
        return self.storage._get_project_dir(project) / STRINGS_FILE

    def _load(self, project: str) -> Dict[str, Any]:
        path = self._path(project)
        try:
            stat = path.stat()
        except OSError:
            return {"blocks": [], "rows": {}}
        stamp = (stat.st_mtime_ns, stat.st_size)
        cached = self._cache.get(path)
        if cached is not None and cached[0] == stamp:
            return cached[1]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logging.getLogger(__name__).warning("strings: %s is unreadable: %r", path, exc)
            return {"blocks": [], "rows": {}}
        data.setdefault("blocks", [])
        data.setdefault("rows", {})
        self._cache[path] = (stamp, data)
        return data

    def _save(self, project: str, data: Dict[str, Any]) -> None:
        path = self._path(project)
        tmp = path.with_name(STRINGS_FILE + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
        stat = path.stat()
        self._cache[path] = ((stat.st_mtime_ns, stat.st_size), data)

    def push(self, project: str, blocks: List[Dict[str, Any]], rows: List[Dict[str, Any]],
             resolved: Dict[str, str]) -> Dict[str, int]:
        """The desktop's rows replace the stored ones; a phone edit the desktop has not taken stays.

        ``resolved[key]`` is the phone text the desktop saw and decided on: that edit is closed. An edit made on the
        phone after the desktop looked does not match it and stays open.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            old = self._load(project)["rows"]
            new: Dict[str, Dict[str, Any]] = {}
            kept = 0
            for row in rows:
                key = row["key"]
                text = row["translation"]
                prev = old.get(key)
                item = {"key": key, "block": row["block"], "string": row["string"], "original": row["original"],
                        "translation": text, "base": text,
                        "updated_at": prev["updated_at"] if prev and prev["translation"] == text else now}
                if prev and prev["translation"] != prev["base"] and text != prev["translation"] \
                        and resolved.get(key) != prev["translation"]:
                    item.update(translation=prev["translation"], base=prev["base"], updated_at=prev["updated_at"])
                    kept += 1
                new[key] = item
            for key, prev in old.items():                  # a phone edit on a row the desktop no longer has
                if key not in new and prev["translation"] != prev["base"]:
                    new[key] = prev
                    kept += 1
            self._save(project, {"blocks": blocks, "rows": new, "updated_at": now})
        return {"rows": len(new), "pending": kept}

    def pending(self, project: str) -> List[Dict[str, Any]]:
        """The rows changed on the phone and not taken by the desktop yet."""
        with self._lock:
            rows = self._load(project)["rows"]
            return [dict(r) for r in rows.values() if r["translation"] != r["base"]]

    def blocks(self, project: str) -> List[Dict[str, Any]]:
        """Every block with its row count, untranslated rows and phone edits."""
        with self._lock:
            data = self._load(project)
            counts: Dict[int, Dict[str, int]] = {}
            for r in data["rows"].values():
                c = counts.setdefault(r["block"], {"total": 0, "untranslated": 0, "changed": 0})
                c["total"] += 1
                c["untranslated"] += r["translation"] == r["original"]
                c["changed"] += r["translation"] != r["base"]
            names = {b.get("block"): b.get("name", "") for b in data["blocks"]}
        return [{"block": idx, "name": names.get(idx) or f"#{idx}", **c} for idx, c in sorted(counts.items())]

    def rows(self, project: str, block: Optional[int] = None, search: str = "", only: str = "") -> List[Dict[str, Any]]:
        """Rows of one block (or of every block when ``block`` is None), in game order.

        ``only``: ``untranslated`` (the text is still the original) or ``changed`` (edited on the phone).
        """
        needle = search.strip().casefold()
        with self._lock:
            rows = list(self._load(project)["rows"].values())
        out = []
        for r in rows:
            if block is not None and r["block"] != block:
                continue
            if only == "untranslated" and r["translation"] != r["original"]:
                continue
            if only == "changed" and r["translation"] == r["base"]:
                continue
            if needle and needle not in r["original"].casefold() and needle not in r["translation"].casefold():
                continue
            out.append(r)
        out.sort(key=lambda r: (r["block"], r["string"]))
        return out

    def update(self, project: str, key: str, translation: str, base: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """A phone edit. ``base`` is the text the phone showed; returns ``(row, conflict)``.

        When the text on the server is no longer ``base`` (the desktop pushed a new one meanwhile), nothing is
        written and the row comes back with ``conflict`` set, so the phone can show both texts.
        """
        with self._lock:
            data = self._load(project)
            row = data["rows"].get(key)
            if row is None:
                return None, False
            if row["translation"] != base:
                return dict(row), True
            row = {**row, "translation": translation, "updated_at": datetime.now(timezone.utc).isoformat()}
            self._save(project, {**data, "rows": {**data["rows"], key: row}})   # the cache changes only once written
            return dict(row), False
