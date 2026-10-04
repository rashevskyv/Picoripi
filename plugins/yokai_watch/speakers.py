"""Who says a line, from the game's own tables (the workspace's ``meta`` folder next to ``source``).

  event text ``data/txt/ev/<event>_<m|f>_en.cfg.bin``
      -> ``<event>_map_<m|f>.cfg.bin``: ``TEXT_WASHA_MAP`` (text id, page, speaker id, -, -, name noun override)
  map NPC text ``data/res/map/<map>/<map>_npc_text_en.cfg.bin`` (and ``_npc_base_text_<chapter>...``)
      -> ``<map>_npc_talk_*.cfg.bin``: ``TALK_INFO`` (speaker id, first row, row count) + ``TALK_CONFIG``
         (-, text id, ...); ``<map>_npc_base_talk_<chapter>...``: ``BASE_TALK_INFO`` (NPC id, then first row and
         row count per time slot) + ``BASE_TALK_CONFIG`` (text id, ...)
  a speaker id is a character (``data/res/character/chara_base_*.cfg.bin``: ``CHARA_BASE_INFO`` /
  ``CHARA_BASE_YOKAI_INFO``, one parameter is the name noun) or a map NPC (``<map>_npc_set_*``:
  ``NPC_BASE`` npc id -> character), and the name is that noun in ``chara_text_en``.

``GAME`` holds what is particular to one game: the ids of the player and of the narrator.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from utils.logging_utils import log_debug

from .cfgbin import CfgBin, FormatError, u32

GAME = {
    "player": 3575866430,                  # TEXT_WASHA_MAP id of the hero: Nate in *_m files, Katie in *_f
    "player_nouns": {"m": 3851587295, "f": 2090590053},
    "narrator": 4108050209,                # system messages and narration: no name box
}
_EVENT = re.compile(r"^(?P<base>ev\d+_\d+[a-z]?)_(?:(?P<g>[mf])_)?en\.cfg\.bin$")
_NPC = re.compile(r"^(?P<map>[a-z0-9]+)_npc(?P<base>_base)?_text(?P<rest>_c\d+_[\d.]+)?_en\.cfg\.bin$")


def _table(path: Path) -> Optional[CfgBin]:
    try:
        return CfgBin(path.read_bytes())
    except (OSError, FormatError) as error:
        log_debug(f"yokai_watch: cannot read {path}: {error}")
        return None


class Speakers:
    """Speaker names per (text file, text id, page); everything is read once, on first use."""

    def __init__(self, source_root: Path, meta_root: Path, lang: str = "_en"):
        self.source_root, self.meta_root, self.lang = Path(source_root), Path(meta_root), lang
        self._nouns: Optional[Dict[int, str]] = None
        self._chara: Optional[Dict[int, int]] = None
        self._files: Dict[str, Dict[Tuple[int, int], int]] = {}
        self._npcs: Dict[str, Dict[int, int]] = {}

    # -- names -----------------------------------------------------------------------------

    def nouns(self) -> Dict[int, str]:
        """``{noun id: name}`` of characters and Yo-kai (and the system's ``???``)."""
        if self._nouns is None:
            self._nouns = {}
            for name in ("chara_text", "system_text"):
                table = _table(self.source_root / "data/res/text" / f"{name}{self.lang}.cfg.bin")
                for entry in table.entries if table else []:
                    if entry.name == "NOUN_INFO" and len(entry.values) > 5 and entry.values[1] == 0 \
                            and isinstance(entry.values[5], str):
                        self._nouns.setdefault(u32(entry.values[0]), entry.values[5])
        return self._nouns

    def characters(self) -> Dict[int, int]:
        """``{character id: name noun id}`` from every ``chara_base`` table."""
        if self._chara is None:
            self._chara = {}
            nouns = self.nouns()
            for path in sorted((self.meta_root / "data/res/character").glob("chara_base*.cfg.bin")):
                table = _table(path)
                for entry in table.entries if table else []:
                    if entry.name in ("CHARA_BASE_INFO", "CHARA_BASE_YOKAI_INFO") and entry.values:
                        noun = next((u32(v) for v in entry.values[1:7] if isinstance(v, int) and u32(v) in nouns), None)
                        if noun is not None:
                            self._chara[u32(entry.values[0])] = noun
        return self._chara

    def name_of(self, speaker: int, gender: str = "m", map_id: str = "") -> Optional[str]:
        nouns, chara = self.nouns(), self.characters()
        if speaker == GAME["player"]:
            return nouns.get(GAME["player_nouns"].get(gender, GAME["player_nouns"]["m"]))
        if speaker in chara:
            return nouns.get(chara[speaker])
        npc = self._npc_characters(map_id).get(speaker) if map_id else None
        if npc is not None and npc in chara:
            return nouns.get(chara[npc])
        return nouns.get(speaker)

    def _npc_characters(self, map_id: str) -> Dict[int, int]:
        if map_id not in self._npcs:
            found: Dict[int, int] = {}
            for path in sorted((self.meta_root / "data/res/map" / map_id).glob(f"{map_id}_npc_set_*.cfg.bin")):
                table = _table(path)
                for entry in table.entries if table else []:
                    if entry.name == "NPC_BASE" and len(entry.values) > 2 and isinstance(entry.values[2], int):
                        found[u32(entry.values[0])] = u32(entry.values[2])
            self._npcs[map_id] = found
        return self._npcs[map_id]

    # -- lines -----------------------------------------------------------------------------

    def speaker(self, rel_path: str, text_id: int, number: int) -> Optional[str]:
        """The name of who says text ``text_id`` page ``number`` of the file ``rel_path`` (``/`` separators)."""
        rel_path = rel_path.replace("\\", "/")
        ids = self._speaker_ids(rel_path)
        speaker = ids.get((text_id, number), ids.get((text_id, -1)))
        if speaker is None:
            return None
        if isinstance(speaker, tuple):                       # (speaker id, name noun override)
            speaker, override = speaker
            if override and override in self.nouns():
                return self.nouns()[override]
        if speaker == GAME["narrator"] or speaker == 0:
            return None
        name = Path(rel_path).name
        gender = "f" if re.search(r"_f_en\.cfg\.bin$", name) else "m"
        map_id = rel_path.split("/")[3] if rel_path.startswith("data/res/map/") else ""
        return self.name_of(speaker, gender, map_id)

    def _speaker_ids(self, rel_path: str) -> Dict[Tuple[int, int], object]:
        if rel_path not in self._files:
            try:
                self._files[rel_path] = self._read_ids(rel_path)
            except (OSError, FormatError, IndexError, TypeError) as error:
                log_debug(f"yokai_watch: no speakers for {rel_path}: {error}")
                self._files[rel_path] = {}
        return self._files[rel_path]

    def _read_ids(self, rel_path: str) -> Dict[Tuple[int, int], object]:
        folder, name = rel_path.rsplit("/", 1) if "/" in rel_path else ("", rel_path)
        out: Dict[Tuple[int, int], object] = {}
        event = _EVENT.match(name)
        if event and folder == "data/txt/ev":
            base, gender = event.group("base"), event.group("g")
            candidates = [f"{base}_map_{gender}.cfg.bin"] if gender else []
            for path in [self.meta_root / folder / c for c in candidates + [f"{base}_map.cfg.bin"]]:
                if path.is_file():
                    for entry in _entries(path, "TEXT_WASHA_MAP"):
                        v = entry.values
                        override = u32(v[5]) if len(v) > 5 and isinstance(v[5], int) and v[5] not in (0, -1) else 0
                        out[(u32(v[0]), v[1])] = (u32(v[2]), override)
                    break
            return out
        npc = _NPC.match(name)
        if npc and folder.startswith("data/res/map/"):
            map_id = npc.group("map")
            meta = self.meta_root / folder
            if npc.group("base"):
                rest = npc.group("rest") or ""
                chapter = rest.rsplit("_", 1)[0] if rest else ""
                paths = sorted(meta.glob(f"{map_id}_npc_base_talk{chapter}_*.cfg.bin"))
                for path in paths:
                    _base_talk(path, out)
            else:
                for path in sorted(meta.glob(f"{map_id}_npc_talk_*.cfg.bin")):
                    _talk(path, out)
        return out


def _entries(path: Path, name: str) -> Iterable:
    table = _table(path)
    return [e for e in table.entries if e.name == name] if table else []


def _talk(path: Path, out: Dict[Tuple[int, int], object]) -> None:
    table = _table(path)
    if not table:
        return
    rows: List = [e for e in table.entries if e.name == "TALK_CONFIG"]
    for info in (e for e in table.entries if e.name == "TALK_INFO"):
        speaker, first, count = (info.values + [0, 0, 0])[:3]
        for row in rows[first:first + count]:
            if len(row.values) > 1 and isinstance(row.values[1], int) and row.values[1]:
                out.setdefault((u32(row.values[1]), -1), u32(speaker))


def _base_talk(path: Path, out: Dict[Tuple[int, int], object]) -> None:
    table = _table(path)
    if not table:
        return
    rows: List = [e for e in table.entries if e.name == "BASE_TALK_CONFIG"]
    for info in (e for e in table.entries if e.name == "BASE_TALK_INFO"):
        npc = u32(info.values[0])
        pairs = info.values[1:]
        for first, count in zip(pairs[0::2], pairs[1::2]):
            for row in rows[first:first + count]:
                if row.values and isinstance(row.values[0], int) and row.values[0]:
                    out.setdefault((u32(row.values[0]), -1), npc)
