"""Storage manager for Picoripi Companion server."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from companion.server.models import GlossaryEntryUpdate, ProjectSummary


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
                except Exception:
                    pass

            if not updated_at and glossary_file.exists():
                mtime = glossary_file.stat().st_mtime
                updated_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

            total = 0
            confirmed = 0
            needs_review = 0
            if glossary_file.exists():
                try:
                    entries = json.loads(glossary_file.read_text(encoding="utf-8"))
                    total = len(entries)
                    for e in entries:
                        status = (e.get("status") or "").lower()
                        if status == "confirmed":
                            confirmed += 1
                        elif status in {"seeded", "fragments", "synthesized", "translated"} or len(e.get("translation_variants", [])) > 1:
                            needs_review += 1
                except Exception:
                    pass

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
            except Exception:
                pass

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

    def get_glossary(self, project_name: str) -> List[Dict[str, Any]]:
        """Retrieve full glossary entries list for a project."""
        pdir = self._get_project_dir(project_name)
        glossary_file = pdir / "glossary.json"
        if not glossary_file.exists():
            return []
        try:
            return json.loads(glossary_file.read_text(encoding="utf-8"))
        except Exception:
            return []

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

        entries = self.get_glossary(project_name)
        target_entry = None
        for entry in entries:
            if entry.get("original") == update.original:
                target_entry = entry
                break

        if target_entry is None:
            return None

        # Create backup before mutation
        bak_file = pdir / "glossary.json.bak"
        try:
            bak_file.write_bytes(glossary_file.read_bytes())
        except Exception:
            pass

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
            except Exception:
                pass
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
            except Exception:
                pass
        return {"name": project_name, "updated_at": ""}
