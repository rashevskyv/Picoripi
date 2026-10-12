"""Series glossaries: glossary files shared by the projects of a game series.

Each file has the project ``glossary.json`` schema, so ``GlossaryManager``
loads, edits and saves it as it does a project glossary. A project has a
chain of them, nearest first: the files it links explicitly
(``project.metadata["series_glossary"]``, one path or a list) and then every
``_glossary/glossary.json`` in the folders above the project folder (a game
folder, then its series folder), unless ``series_glossary_auto`` is false.
The project glossary wins; a nearer level wins over a farther one.
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
AUTO_KEY = "series_glossary_auto"
FOLDER_NAME = "_glossary"
FOLDER_FILE = "glossary.json"

# Statuses of the multi-source series document (``{"terms": [...]}``): the
# first two are settled, the other two still need a person's decision.
_SETTLED_SERIES_STATUSES = frozenset({"agreed", "resolved"})


def series_dir() -> Path:
    """Where imported series glossaries live (read at call time: tests move SETTINGS_DIR)."""
    return constants.SETTINGS_DIR / "series_glossaries"


def linked_series_paths(project: Any) -> List[Path]:
    """The series glossary files ``project`` links to explicitly, nearest first (old projects link none)."""
    metadata = getattr(project, "metadata", None)
    value = metadata.get(METADATA_KEY) if isinstance(metadata, dict) else None
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [Path(item) for item in value if isinstance(item, str) and item.strip()]


def set_series_links(project: Any, paths: Iterable[Path]) -> None:
    """Make ``paths`` the explicit series links of ``project`` (none removes the key). The caller saves the project."""
    paths = [str(path) for path in paths]
    if paths:
        project.metadata[METADATA_KEY] = paths[0] if len(paths) == 1 else paths
    else:
        project.metadata.pop(METADATA_KEY, None)


def link_series(project: Any, path: Optional[Path]) -> None:
    """Link ``project`` to exactly the series glossary at ``path``; None unlinks every explicit link."""
    set_series_links(project, [path] if path is not None else [])


def folder_glossaries_enabled(project: Any) -> bool:
    """Whether the ``_glossary`` files above the project folder count (the default)."""
    metadata = getattr(project, "metadata", None)
    return not (isinstance(metadata, dict) and metadata.get(AUTO_KEY) is False)


def discovered_series_paths(project_dir: Optional[Path]) -> List[Path]:
    """``_glossary/glossary.json`` in the project folder and in every folder above it, nearest first."""
    if project_dir is None:
        return []
    start = Path(project_dir)
    found = []
    for folder in (start, *start.parents):
        candidate = folder / FOLDER_NAME / FOLDER_FILE
        if candidate.is_file():
            found.append(candidate)
    return found


def series_chain(project: Any, project_dir: Optional[Path]) -> List[Path]:
    """Every series glossary file of ``project``, nearest first: explicit links, then folder glossaries."""
    chain = linked_series_paths(project)
    if folder_glossaries_enabled(project):
        chain += [path for path in discovered_series_paths(project_dir) if path not in chain]
    return chain


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


def series_rows_for(
    text: str, chain: Iterable[Optional[GlossaryManager]], project: Optional[GlossaryManager]
) -> List[GlossaryEntry]:
    """Series entries found in ``text`` for terms the project glossary does not translate.

    ``chain`` is nearest first; a term translated by a nearer level is not
    listed again from a farther one.
    """
    if not text:
        return []
    rows: List[GlossaryEntry] = []
    seen = set()
    for series in chain:
        if not isinstance(series, GlossaryManager) or not series.get_entries():
            continue
        for entry in series.get_relevant_terms(text):
            key = GlossaryManager.canonical_key(entry.original)
            if key in seen or project_covers(project, entry):
                continue
            if (entry.translation or "").strip():
                seen.add(key)
            rows.append(entry)
    return rows


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
