"""Glossary seed from the game's own tables: Yo-kai, people, items, skills, abilities, tribes, places.

Yo-kai and people: the name nouns of ``chara_text_en`` that the character tables (``chara_base``, meta folder)
name in ``CHARA_BASE_YOKAI_INFO`` / ``CHARA_BASE_INFO``; a Yo-kai's description is its Medallium entry (the
``chara_text`` text the same record points at). Items, skills, abilities: the nouns of their text tables.
Tribes: the coloured ``<CR>X Tribes</C>`` of the help text. Places: the location names of ``system_text`` (the
runs of short title-case strings in it -- the area and building lists the save diary and the map use).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.logging_utils import log_debug

from .cfgbin import CfgBin, FormatError, u32
from .speakers import GAMES, game_of

_PLACE = re.compile(r"^[A-Z][\w'’.&é -]{1,38}$")


def _table(path: Path) -> Optional[CfgBin]:
    try:
        return CfgBin(path.read_bytes())
    except (OSError, FormatError) as error:
        log_debug(f"yokai_watch glossary: {path}: {error}")
        return None


def _nouns(table: Optional[CfgBin], param: int = 5) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for entry in table.entries if table else []:
        if entry.name == "NOUN_INFO" and len(entry.values) > param and entry.values[1] == 0 \
                and isinstance(entry.values[param], str):
            out.setdefault(u32(entry.values[0]), entry.values[param])
    return out


def _texts(table: Optional[CfgBin]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for entry in table.entries if table else []:
        if entry.name == "TEXT_INFO" and len(entry.values) > 2 and isinstance(entry.values[2], str):
            out.setdefault(u32(entry.values[0]), entry.values[2])
    return out


def _plain(text: str) -> str:
    return re.sub(r"<[^>]*>", "", text).replace("\\n", " ").strip()


def seed_entries(source_root: Path, meta_root: Path, lang: str = "_en") -> List[Dict[str, Any]]:
    text_dir = Path(source_root) / "data/res/text"
    entries: List[Dict[str, Any]] = []
    seen = set()

    def add(term: str, section: str, description: str, source: str) -> None:
        term = term.strip()
        if term and term not in seen and "<" not in term and not re.search(r"[぀-ヿ一-鿿]", term) and term != "dummy":
            seen.add(term)
            entries.append({"term": term, "section": section, "description": description, "source_ref": source})

    chara = _table(text_dir / f"chara_text{lang}.cfg.bin")
    renamed = GAMES[game_of(Path(source_root))]["names"]          # Yo-kai Watch 3: the heroes' nouns are name tags
    names = {noun: renamed.get(name, name) for noun, name in _nouns(chara).items()}
    medallium = _texts(chara)
    yokai, people = {}, set()
    for path in sorted((Path(meta_root) / "data/res/character").glob("chara_base*.cfg.bin")):
        table = _table(path)
        for entry in table.entries if table else []:
            ints = [u32(v) for v in entry.values if isinstance(v, int)]
            noun = next((v for v in ints if v in names), None)
            if noun is None:
                continue
            if entry.name == "CHARA_BASE_YOKAI_INFO":
                yokai[noun] = next((medallium[v] for v in ints if v in medallium), yokai.get(noun, ""))
            elif entry.name == "CHARA_BASE_INFO":
                people.add(noun)
    for noun, text in yokai.items():
        add(names[noun], "Yo-kai", f"Yo-kai (name is a pun). Medallium: {_plain(text)}" if text else "Yo-kai",
            f"chara_text{lang} noun {noun:08x}")
    for noun in sorted(people | set(names) - set(yokai), key=lambda n: names[n]):
        add(names[noun], "Characters", "Person or animal of the story", f"chara_text{lang} noun {noun:08x}")
    for file, section, what in (("item_text", "Items", "Item"), ("skill_text", "Skills", "Skill or technique"),
                                ("chara_ability_text", "Abilities", "Yo-kai ability")):
        for noun, name in _nouns(_table(text_dir / f"{file}{lang}.cfg.bin")).items():
            add(name, section, what, f"{file}{lang} noun {noun:08x}")
    for text in _texts(_table(text_dir / f"help_text{lang}.cfg.bin")).values():
        for tribe in re.findall(r"<CR>(\w+) Tribes</C>", text):
            add(f"{tribe} Tribe", "Tribes", "One of the eight Yo-kai tribes", f"help_text{lang}")
    for place in _places(_table(text_dir / f"system_text{lang}.cfg.bin")):
        add(place, "Places", "A place in Springdale (location names of the map and the save diary)",
            f"system_text{lang}")
    return entries


def _places(table: Optional[CfgBin]) -> List[str]:
    """Names from every run of 8 or more short title-case strings with "Area - Spot" pairs in it (the area and
    building lists); floors and room numbers left out."""
    texts = [e.values[2] for e in table.entries if e.name == "TEXT_INFO" and len(e.values) > 2
             and isinstance(e.values[2], str)] if table else []
    runs, start = [], None
    for index, text in enumerate(texts + [""]):
        ok = bool(_PLACE.match(text)) and not text.rstrip().endswith(("?", "!", "."))
        if ok and start is None:
            start = index
        elif not ok and start is not None:
            if index - start >= 8 and sum(" - " in t for t in texts[start:index]) >= 2:
                runs.append((start, index))
            start = None
    out: List[str] = []
    for first, end in runs:
        for text in texts[first:end]:
            for part in text.split(" - "):
                if part not in out and not re.search(r"\d", part) and len(part) > 2:
                    out.append(part)
    return out
