"""Seed a series glossary file from the game data of one project of the series (no window, no AI).

A plugin's ``get_glossary_seed_entries()`` reads the game's own name tables (species, moves, items and so on)
through ``self.mw.project_manager``. This module loads the project in memory, hands the plugin a holder with that
project manager, and writes each term the file does not have yet. Seeded terms have an empty translation: the
series file records what the game calls a thing, not what a translator decided. Existing entries are never changed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List

from core.glossary.manager import GlossaryManager
from core.glossary.models import STATUS_FRAGMENTS, STATUS_SEEDED
from core.project.manager import ProjectManager
from core.project_library import plugin_facts

LoadRules = Callable[..., Any]  # (plugin name, main window holder) -> GameRules


class _ProjectHolder:
    """What a plugin's seed hook reads from the main window: the project manager, nothing else."""

    def __init__(self, project_manager: ProjectManager):
        self.project_manager = project_manager


def game_seed_entries(project_file: Path, load_rules: LoadRules = plugin_facts.default_load_rules) -> List[Dict[str, Any]]:
    """The plugin's seed entries for the project at ``project_file`` (empty when the plugin has no seed hook)."""
    manager = ProjectManager()
    if not manager.load(str(project_file)):
        raise ValueError(f"cannot load the project {project_file}")
    rules = load_rules(str(manager.project.plugin_name or ""), _ProjectHolder(manager))
    hook = getattr(rules, "get_glossary_seed_entries", None)
    if not callable(hook):
        return []
    return [entry for entry in (hook() or []) if isinstance(entry, dict)]


def seed_series_file(project_file: Path, series_file: Path,
                     load_rules: LoadRules = plugin_facts.default_load_rules) -> Dict[str, int]:
    """Add the game's terms missing from ``series_file`` (created when absent). Returns counts for the report.

    ``{"offered": n, "added": n, "present": n}``: terms the plugin gave, terms written, and terms the file already had.
    """
    seeds = game_seed_entries(project_file, load_rules)
    series_file = Path(series_file)
    text = series_file.read_text(encoding="utf-8-sig") if series_file.is_file() else "[]"
    glossary = GlossaryManager()
    glossary.load_from_text(plugin_name=None, glossary_path=series_file, raw_text=text)
    added = present = 0
    for seed in seeds:
        term = str(seed.get("term") or "").strip()
        if not term:
            continue
        if glossary.find_entry(term) is not None:
            present += 1
            continue
        description = str(seed.get("description") or "").strip()
        glossary.seed_entry(
            term,
            section=seed.get("section") or None,
            status=STATUS_FRAGMENTS if description else STATUS_SEEDED,
            description=description,
            icon=str(seed.get("icon") or ""),
        )
        added += 1
    if added:
        glossary.save_to_disk()
    return {"offered": len(seeds), "added": added, "present": present}
