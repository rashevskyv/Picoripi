"""Series glossary: one glossary file shared by the projects of a game series.

The file has the project ``glossary.json`` schema, so ``GlossaryManager``
loads, edits and saves it as it does a project glossary. A project links to
one series glossary through ``project.metadata["series_glossary"]``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import utils.constants as constants
from core.glossary.manager import GlossaryManager
from core.glossary.models import STATUS_CONFIRMED, STATUS_TRANSLATED, GlossaryEntry, legacy_entry_id
from utils.atomic_io import atomic_write_text

METADATA_KEY = "series_glossary"

# Statuses of the multi-source series document (``{"terms": [...]}``): the
# first two are settled, the other two still need a person's decision.
_SETTLED_SERIES_STATUSES = frozenset({"agreed", "resolved"})


def series_dir() -> Path:
    """Where imported series glossaries live (read at call time: tests move SETTINGS_DIR)."""
    return constants.SETTINGS_DIR / "series_glossaries"


def linked_series_path(project: Any) -> Optional[Path]:
    """The series glossary file ``project`` links to, or None (old projects have no key)."""
    metadata = getattr(project, "metadata", None)
    value = metadata.get(METADATA_KEY) if isinstance(metadata, dict) else None
    return Path(value) if isinstance(value, str) and value.strip() else None


def link_series(project: Any, path: Optional[Path]) -> None:
    """Link ``project`` to the series glossary at ``path``; None unlinks. The caller saves the project."""
    metadata = project.metadata
    if path is None:
        metadata.pop(METADATA_KEY, None)
    else:
        metadata[METADATA_KEY] = str(path)


def _split_option(option: str) -> tuple[str, str]:
    """``"Набору (Japanese ナボール, Kovalenko)"`` -> ("Набору", "Japanese ナボール, Kovalenko")."""
    match = re.match(r"^(.*?)\s*\((.*)\)\s*$", option)
    return (match.group(1), match.group(2)) if match else (option, "")


def _entry_from_series_term(term: Dict[str, Any]) -> Dict[str, Any]:
    """One term of the multi-source series document as a glossary.json entry."""
    variants: Dict[str, List[str]] = {}
    forms: Dict[str, List[str]] = {}
    for rendering in term.get("renderings") or ():
        text = str(rendering.get("uk", "") or "").strip()
        if not text:
            continue
        variants.setdefault(text, []).append(str(rendering.get("source", "") or "?"))
        for form in rendering.get("forms") or ():
            if form and form != text and form not in forms.setdefault(text, []):
                forms[text].append(form)
    out_variants = []
    for text, sources in variants.items():
        rationale = ", ".join(sources)
        if forms.get(text):
            rationale += "; forms: " + ", ".join(forms[text])
        out_variants.append({"translation": text, "rationale": rationale})
    for option in term.get("options") or ():
        text, why = _split_option(str(option))
        if text and text not in variants:
            out_variants.append({"translation": text, "rationale": why})

    status = str(term.get("status", "") or "")
    remarks = [f"Series status: {status}" if status else ""]
    if term.get("games"):
        remarks.append("Games: " + ", ".join(map(str, term["games"])))
    if term.get("reason"):
        remarks.append("Reason: " + str(term["reason"]))
    original = str(term.get("term", "") or "").strip()
    entry: Dict[str, Any] = {
        "original": original,
        "translation": str(term.get("recommended", "") or "").strip(),
        "notes": str(term.get("note", "") or ""),
        "section": term.get("category") or None,
        "profiled": False,
        "status": STATUS_CONFIRMED if status in _SETTLED_SERIES_STATUSES else STATUS_TRANSLATED,
        "user_notes": "\n".join(r for r in remarks if r),
        "id": legacy_entry_id(original),
    }
    if out_variants:
        entry["translation_variants"] = out_variants
    aliases = [str(a).strip() for a in term.get("aliases") or () if str(a).strip()]
    if aliases:
        entry["aliases"] = aliases
    return entry


def entries_from_json(data: Any) -> List[Dict[str, Any]]:
    """glossary.json entries from a project glossary list or a series ``{"terms": [...]}`` document."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("terms"), list):
        rows = [_entry_from_series_term(t) for t in data["terms"] if isinstance(t, dict)]
        return [row for row in rows if row["original"]]
    raise ValueError("not a glossary: expected a list of entries or an object with a \"terms\" list")


def import_series_glossary(source: Path, target: Optional[Path] = None) -> Path:
    """Convert ``source`` into a series glossary file (default: ``series_dir()/<stem>.json``)."""
    rows = entries_from_json(json.loads(Path(source).read_text(encoding="utf-8-sig")))
    target = target or series_dir() / f"{Path(source).stem}.json"
    atomic_write_text(target, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    return target


def project_covers(project: Optional[GlossaryManager], entry: GlossaryEntry) -> bool:
    """Whether the project glossary already translates ``entry``'s term (then the series row is not needed)."""
    found = project.find_entry(entry.original) if isinstance(project, GlossaryManager) else None
    return bool(found and (found.translation or "").strip())


def series_rows_for(text: str, series: Optional[GlossaryManager], project: Optional[GlossaryManager]) -> List[GlossaryEntry]:
    """Series entries found in ``text`` for terms the project glossary does not translate."""
    if not isinstance(series, GlossaryManager) or not text or not series.get_entries():
        return []
    return [entry for entry in series.get_relevant_terms(text) if not project_covers(project, entry)]


def find_conflicts(
    project_entries: Iterable[GlossaryEntry], series_entries: Iterable[GlossaryEntry]
) -> Dict[str, tuple[str, str]]:
    """Terms both glossaries translate differently: canonical key -> (project, series) translation."""
    series = {
        GlossaryManager.canonical_key(e.original): e.translation.strip()
        for e in series_entries
        if e.translation.strip()
    }
    conflicts = {}
    for entry in project_entries:
        key = GlossaryManager.canonical_key(entry.original)
        mine, theirs = entry.translation.strip(), series.get(key, "")
        if mine and theirs and mine.casefold() != theirs.casefold():
            conflicts[key] = (mine, theirs)
    return conflicts
