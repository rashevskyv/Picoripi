"""Glossary material a marked-up script already carries.

Markup Studio is where a person says, line by line, which character is speaking.
That is a list of the game's cast written the way a reader recognises it -- and
it was going nowhere. The glossary was seeded from the game's own files only, so
a character the script names and the files spell differently (or do not name at
all) was simply missing from the glossary.

Only speakers are taken. Two other markup types look like glossary material and
are not:

* ``Structure`` marks are Acts, Chapters and Scenes -- narrative headings, not
  place names. Seeding "Scene 4" as a term would be noise.
* ``Item`` marks name the *window*, not the item: in a real marked-up script
  they read "SYSTEM", with the item's actual name buried in the description
  below. A plugin that can read the game's item windows already seeds those
  properly, so there is nothing here worth the junk.

Pure and Qt-free: takes the project object and returns seed dicts in exactly the
shape ``get_glossary_seed_entries()`` uses, so both sources travel the same path
into the glossary and gap-fill against each other.
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.script_markup.hierarchy_markup import HierarchyType, mark_text


CHARACTER_SECTION = "Characters"
SOURCE_REF = "script markup"


def seeds_from_markup(project: Any) -> List[Dict[str, Any]]:
    """One ``Characters`` seed per distinct speaker the script marks up.

    No description: the script says who spoke, never who they are. The describe
    pass writes that from the lines themselves, exactly as for any other seed.
    """
    if project is None:
        return []
    lines = (getattr(project, "raw_text", "") or "").splitlines()
    seeds: List[Dict[str, Any]] = []
    seen = set()
    for mark in getattr(project, "approved_marks", ()) or ():
        if getattr(mark, "type_id", "") != HierarchyType.SPEAKER:
            continue
        name = (mark_text(mark, lines) or "").strip()
        # Case-insensitively, because the glossary matches terms that way: a
        # script shouting MIDNA must not seed a second entry beside Midna.
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        seeds.append({
            "term": name,
            "section": CHARACTER_SECTION,
            "source_ref": SOURCE_REF,
        })
    return seeds
