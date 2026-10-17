"""Glossary seeds from a game's name tables: one term per row, under the category of its table.

A plugin reads a table with its own codec and hands the rows to ``TermCollector.add_table``. A term is seeded once:
the first table that gives it wins, and two terms that differ only in letter case are one term. A row is a term only
when it starts with a letter and is at most ``MAX_TERM_CHARS`` long (placeholders such as "??????" and "-" are not terms).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from plugins.common import gfmsg
from utils.logging_utils import log_debug

MAX_TERM_CHARS = 40

# Name tables of the Switch games (file stem, a regular expression) -> (role, what the role is, glossary section).
# An empty section: the table is read for context only and not seeded.
TABLE_ROLES: Tuple[Tuple[str, str, str, str], ...] = (
    (r"monsname|ride_poke_name", "Pokémon name", "The name of a Pokémon species.", "Pokémon"),
    (r"g?wazaname", "Move name", "The name of a move.", "Moves"),
    (r"g?wazainfo", "Move description", "The description of a move.", ""),
    (r"itemname.*|nuts_name|dressup_item_name|kisekae_item_name", "Item name", "The name of an item.", "Items"),
    (r"iteminfo", "Item description", "The description of an item.", ""),
    (r"tokusei", "Ability name", "The name of an Ability.", "Abilities"),
    (r"tokuseiinfo", "Ability description", "The description of an Ability.", ""),
    (r"place_name.*", "Place name", "The name of a place.", "Places"),
    (r"trname|tower_trname", "Trainer name", "The name of a trainer.", "Characters"),
    (r"trtype", "Trainer class", "A trainer class (Youngster, Gym Leader...).", "Characters"),
    (r"typename", "Type name", "The name of a Pokémon type.", "Types"),
    (r"seikaku", "Nature", "The name of a Pokémon nature.", ""),
    (r"zukan_comment_.*", "Pokédex entry", "A Pokédex description of a Pokémon.", ""),
    (r"btl_.*", "Battle message", "A message of the battle screen.", ""),
    (r"staff_list", "Staff credits", "A line of the staff credits.", ""),
)


# A table of another grammatical form of a name (plural, accusative, classified, a place with its preposition...): the
# same terms again in other words, so it gives context but no glossary term.
INFLECTED_FORM = re.compile(r".*_(plural|acc|classified|indirect|out|per|spe|display|townmap)$")


def role_of(stem: str, roles: Sequence[Tuple[str, str, str, str]] = TABLE_ROLES) -> Optional[Tuple[str, str, str, str]]:
    """``(pattern, role, instruction, section)`` of the first role whose pattern matches the table's file stem."""
    for role in roles:
        if re.fullmatch(role[0], stem):
            return role
    return None


# Sections of a Switch name table in the order their terms are taken (a term keeps the first section that gives it).
SECTION_RANK = {"Pokémon": 0, "Moves": 1, "Abilities": 2, "Types": 3, "Items": 4, "Characters": 5, "Places": 6}


class TermCollector:
    """The terms seeded from the name tables of one project: each term once, the first table wins."""

    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []
        self._seen: Set[str] = set()

    def add_table(self, source_ref: str, texts: Sequence[Any], section: str, description: str) -> None:
        """Add the rows of one table (``texts`` in row order) under ``section``; ``source_ref`` names the table."""
        if not section:
            return
        for row, text in enumerate(texts):
            term = str(text or "").strip()
            if not term or len(term) > MAX_TERM_CHARS or "{" in term or not term[0].isalpha():
                continue
            key = term.casefold()
            if key in self._seen:
                continue
            self._seen.add(key)
            self.entries.append({"term": term, "section": section, "description": description,
                                 "source_ref": f"{source_ref} line {row}"})


def gfmsg_seed_entries(project_manager: Any, plugin: str) -> List[Dict[str, Any]]:
    """The terms of a Switch game's name tables: the gfmsg files under a ``common`` folder whose stem has a role."""
    try:
        blocks = list(project_manager.project.blocks)
    except (AttributeError, TypeError):
        return []
    tables = []
    for block in blocks:
        rel = str(block.source_file).replace("\\", "/")
        stem = Path(rel).stem
        role = role_of(stem)
        if role is None or not role[3] or "/common/" not in f"/{rel}" or INFLECTED_FORM.fullmatch(stem):
            continue
        try:
            texts = [gfmsg.to_editor(units) for units, _flags
                     in gfmsg.read(Path(project_manager.get_absolute_path(block.source_file)).read_bytes())]
        except (OSError, ValueError) as error:
            log_debug(f"{plugin}: no glossary terms from {rel}: {error}")
            continue
        tables.append((SECTION_RANK.get(role[3], len(SECTION_RANK)), rel, stem, role[3], texts))
    # the specific name tables first: a clothing item named after a type must not take the type's section
    collector = TermCollector()
    for _rank, rel, stem, section, texts in sorted(tables, key=lambda table: table[0]):
        collector.add_table(rel, texts, section, f"{stem} table")
    return collector.entries
