"""Who says a line, from the game's own tables (the workspace's ``meta`` folder next to ``source``).

  event text ``data/txt/ev/<event>_<m|f>_en.cfg.bin`` (Yo-kai Watch 3: ``data/txt/ev/en/<event>_en.cfg.bin``)
      -> ``data/txt/ev/<event>_map[_<m|f>].cfg.bin``: ``TEXT_WASHA_MAP`` (text id, page, speaker id, -, -, name
         noun override)
  map NPC text ``data/res/map/<map>/<map>_npc_text[_a]_en.cfg.bin`` (and ``_npc_base_text_<chapter>...``)
      -> ``<map>_npc_talk_*.cfg.bin``: ``TALK_INFO`` (speaker id, first row, row count) + ``TALK_CONFIG``
         (-, text id, ...); ``<map>_npc_base_talk_<chapter>...``: ``BASE_TALK_INFO`` (NPC id, then first row and
         row count per time slot) + ``BASE_TALK_CONFIG`` (text id, ...)
  a speaker id is a character (``data/res/character/chara_base_*.cfg.bin``: ``CHARA_BASE_INFO`` /
  ``CHARA_BASE_YOKAI_INFO``, one parameter is the name noun) or a map NPC (``<map>_npc_set_*``:
  ``NPC_BASE`` npc id -> character), and the name is that noun in ``chara_text_en``.

A line that names no one in the tables but plays a voice clip (``<PV#pv_c001000_23>``, ``<V#y327000>``,
Yo-kai Watch 3) is said by that model: in Yo-kai Watch 3 a character id is the CRC32 of its model name.

``GAMES`` holds what is particular to one game (the ids of the hero and the narrator; how the hero is told
apart; the language suffix of its text files); ``game_of`` tells the games apart by the layout of the source
folder. Yo-kai Watch 1 on Switch (``ywnx``) keeps the 3DS ids; its files end in ``_ja`` (the English fan mod
writes English into the Japanese files).
"""
from __future__ import annotations

import re
import zlib
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from utils.logging_utils import log_debug

from .cfgbin import CfgBin, FormatError, u32

GAMES = {
    "yw1": {
        "player": 3575866430,              # TEXT_WASHA_MAP id of the hero: Nate in *_m files, Katie in *_f
        "player_nouns": {"m": 3851587295, "f": 2090590053},
        "narrator": 4108050209,            # system messages and narration: no name box
        "names": {},
        "lang": "_en",
    },
    "yw3": {
        "player": 2947951939,              # CRC32 of "c000000": whichever hero plays; the voice clip tells who
        "player_nouns": {},
        "narrator": 4108050209,
        "names": {"<PNAMEM>": "Nate", "<PNAMEF>": "Hailey"},   # the heroes' nouns are the name tags
        "lang": "_en",
    },
}
GAMES["ywnx"] = dict(GAMES["yw1"], lang="_ja")
# Yo-kai Watch 2: Psychic Specters (3DS, EUR): the British English files (*_engb), event text in data/txt/ev/engb.
# The hero is the CRC32 of "c000000" (as in Yo-kai Watch 3); the _m / _f file tells Nate from Katie.
GAMES["yw2"] = dict(GAMES["yw1"], lang="_engb", player=2947951939, player_nouns={"m": 526454680, "f": 232038518})
# Yo-kai Watch 4++ and Yo-kai Academy Y (Switch): text in data/common/text/ja, no speaker tables read yet.
GAMES["yw4"] = dict(GAMES["yw1"], lang="_ja")
GAMES["yay"] = dict(GAMES["yw1"], lang="_ja")
GAME = GAMES["yw1"]
_EVENT = r"^(?P<base>ev\d+_\d+[a-z]?)_(?:(?P<g>[mf])_)?{lang}\.cfg\.bin$"
_NPC = r"^(?P<map>[a-z0-9]+)_npc(?P<base>_base)?_text(?P<rest>_[a-z0-9_.]+?)?_{lang}\.cfg\.bin$"
_VOICE = re.compile(r"<(?:PV#(?:g_)?(?:pv|voice)_|V#)([a-z]+\d{6})")


def game_of(source_root: Path) -> str:
    """``yw3`` when the English event text sits in a language folder (``data/txt/ev/en``), ``ywnx`` when the
    text files are the Japanese ones (Switch), ``yw4`` / ``yay`` for Yo-kai Watch 4++ / Yo-kai Academy Y
    (``data/common/text/ja``; Academy Y has a second Japanese font, ``font_ja2``), ``yw2`` when it sits in
    ``data/txt/ev/engb``, else ``yw1``."""
    root = Path(source_root)
    if (root / "data/common/text/ja").is_dir():
        return "yay" if (root / "data/common/font/font/font_ja2").is_dir() else "yw4"
    if (root / "data/txt/ev/en").is_dir():
        return "yw3"
    if (root / "data/txt/ev/engb").is_dir():
        return "yw2"
    return "ywnx" if (root / "data/res/text/system_text_ja.cfg.bin").is_file() else "yw1"


def _table(path: Path) -> Optional[CfgBin]:
    try:
        return CfgBin(path.read_bytes())
    except (OSError, FormatError) as error:
        log_debug(f"yokai_watch: cannot read {path}: {error}")
        return None


class Speakers:
    """Speaker names per (text file, text id, page); everything is read once, on first use."""

    def __init__(self, source_root: Path, meta_root: Path, lang: str = ""):
        self.source_root, self.meta_root = Path(source_root), Path(meta_root)
        self.game = GAMES[game_of(self.source_root)]
        self.lang = lang or self.game["lang"]
        code = self.lang.strip("_")
        self._event, self._npc = (re.compile(p.replace("{lang}", code)) for p in (_EVENT, _NPC))
        self._nouns: Optional[Dict[int, str]] = None
        self._chara: Optional[Dict[int, int]] = None
        self._files: Dict[str, Dict[Tuple[int, int], object]] = {}
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
                        noun = entry.values[5]
                        self._nouns.setdefault(u32(entry.values[0]), self.game["names"].get(noun, noun))
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
        if speaker == self.game["player"] and self.game["player_nouns"]:
            return nouns.get(self.game["player_nouns"].get(gender, self.game["player_nouns"]["m"]))
        if speaker in chara:
            return nouns.get(chara[speaker])
        npc = self._npc_characters(map_id).get(speaker) if map_id else None
        if npc is not None and npc in chara:
            return nouns.get(chara[npc])
        return nouns.get(speaker)

    def voice_of(self, text: str) -> Optional[str]:
        """The character whose voice clip the line plays (``<PV#pv_c001000_23>`` -> model c001000), or None."""
        match = _VOICE.search(text or "")
        if not match:
            return None
        noun = self.characters().get(zlib.crc32(match.group(1).encode()))
        return self.nouns().get(noun) if noun is not None else None

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

    def speaker(self, rel_path: str, text_id: int, number: int, text: str = "") -> Optional[str]:
        """The name of who says text ``text_id`` page ``number`` of the file ``rel_path`` (``/`` separators);
        ``text`` (the line as stored) for its voice clip."""
        rel_path = rel_path.replace("\\", "/")
        ids = self._speaker_ids(rel_path)
        speaker = ids.get((text_id, number), ids.get((text_id, -1)))
        if isinstance(speaker, tuple):                       # (speaker id, name noun override)
            speaker, override = speaker
            if override and override in self.nouns():
                return self.nouns()[override]
        if speaker == self.game["narrator"] or speaker == 0:
            return None
        name = None
        if speaker is not None:
            gender = "f" if rel_path.endswith(f"_f{self.lang}.cfg.bin") else "m"
            map_id = rel_path.split("/")[3] if rel_path.startswith("data/res/map/") else ""
            name = self.name_of(speaker, gender, map_id)
        return name or self.voice_of(text)

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
        language_folder = "/" + self.lang.strip("_")
        if folder.endswith(language_folder):
            folder = folder[:-len(language_folder)]           # Yo-kai Watch 3: data/txt/ev/en, the maps in data/txt/ev
        out: Dict[Tuple[int, int], object] = {}
        event = self._event.match(name)
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
        npc = self._npc.match(name)
        if npc and folder.startswith("data/res/map/"):
            map_id = npc.group("map")
            meta = self.meta_root / folder
            if npc.group("base"):
                rest = npc.group("rest") or ""
                chapter = rest.rsplit("_", 1)[0] if rest else ""
                for path in sorted(meta.glob(f"{map_id}_npc_base_talk{chapter}_*.cfg.bin")):
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
