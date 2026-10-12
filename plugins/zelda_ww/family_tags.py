"""Tag correspondence between Wind Waker GameCube (BMG) and HD (MSBT) editor texts, and the family match key.

GameCube text writes a control tag as ``{escape:TYPE:HEX}``; HD text writes it as ``[Name:arg]`` (``tags.py``).
Both name the same game control, so a message of one version matches the same message of the other once their
tags are read in one syntax. The table ``family_tag_map.json`` maps GameCube keys (``E<group>:<hex>``) to HD keys
(``T<group>:<type>:<hex>``). It is derived from the decoded game files (``derive``): messages with the same id in
both versions and the same text when tags are removed. A tag matches its partner when they sit at the same text
offset in those messages, scored by Jaccard similarity so that a tag found everywhere cannot claim a rare one.

Colour (escape 255, type 0) and scale (escape 255, type 1) are not derived: the zeldaret catalogue names them,
and the data confirm the rule (each colour N is HD colour N; each scale value is the HD size value). Colour 0 is
the box default: GameCube writes it as ``E255:000000``, HD as ``[/C]`` (0xFFFF), and as ``[White]`` (0x0000).

The match key drops colour: it is styling, and HD writes colour around every span, GameCube only once.
CLI (dev only, reads the real files): ``python -m plugins.zelda_ww.family_tags derive <bmg folder> <msbt folder>``
"""
from __future__ import annotations

import collections
import json
import re
import struct
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from plugins.common.msbt import EndTag, Tag

from .tags import from_editor, render_tag, to_editor

MAP_FILE = Path(__file__).resolve().parent / "family_tag_map.json"
GC_ESCAPE = re.compile(r"\{escape:(\d+):([0-9a-fA-F]*)\}")
COLOUR_GROUP, COLOUR_TYPE = 0, 3
SCALE_GROUP, SCALE_TYPE = 0, 2
DEFAULT_COLOUR = 0xFFFF
JACCARD_MIN = 0.5
_PUA = range(0xE000, 0xF900)
# The GameCube editor shows straight quotes as curly ones (translation_map.json); HD does not. Both sides fold to straight.
_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def _gc_key(group: int, hex_params: str) -> str:
    return f"E{group}:{hex_params.lower()}"


def _hd_key(tag: Tag) -> str:
    return f"T{tag.group}:{tag.type}:{tag.params.hex()}"


def _hd_tag(key: str) -> Tag:
    group, kind, params = key[1:].split(":", 2)
    return Tag(int(group), int(kind), bytes.fromhex(params))


def _colour_rule(group: int, hex_params: str) -> Optional[str]:
    """HD key of a GameCube colour or scale escape, or None when the escape is not one of them."""
    if group != 255:
        return None
    data = bytes.fromhex(hex_params)
    if len(data) == 3 and data[:2] == b"\x00\x00":
        index = data[2]
        if index == 0:
            return _hd_key(Tag(COLOUR_GROUP, COLOUR_TYPE, struct.pack(">H", DEFAULT_COLOUR)))
        return _hd_key(Tag(COLOUR_GROUP, COLOUR_TYPE, struct.pack(">H", index)))
    if len(data) == 4 and data[:2] == b"\x00\x01":
        return _hd_key(Tag(SCALE_GROUP, SCALE_TYPE, data[2:4]))
    return None


def load_map(path: Path = MAP_FILE) -> Dict[str, str]:
    """The derived GameCube -> HD tag table (empty when the file is missing)."""
    if not path.is_file():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")).get("gc_to_hd", {}))


class TagMap:
    """Both directions of the tag table, with the colour and scale rules."""

    def __init__(self, gc_to_hd: Dict[str, str]):
        self.gc_to_hd = dict(gc_to_hd)
        self.hd_to_gc: Dict[str, str] = {}
        for gc_key, hd_key in sorted(self.gc_to_hd.items()):
            self.hd_to_gc.setdefault(hd_key, gc_key)

    def gc_to_hd_key(self, group: int, hex_params: str) -> Optional[str]:
        return _colour_rule(group, hex_params) or self.gc_to_hd.get(_gc_key(group, hex_params))

    def hd_to_gc_key(self, hd_key: str) -> Optional[str]:
        """The GameCube key of an HD key. HD colour 0 (white) and the box default both read as GameCube colour 0."""
        colour = f"T{COLOUR_GROUP}:{COLOUR_TYPE}:"
        if hd_key == _hd_key(Tag(COLOUR_GROUP, COLOUR_TYPE, struct.pack(">H", DEFAULT_COLOUR))):
            return "E255:000000"
        if hd_key.startswith(colour) and len(hd_key) == len(colour) + 4:
            index = int(hd_key[len(colour):], 16)
            return f"E255:0000{index:02x}" if index < 256 else None
        if hd_key.startswith(f"T{SCALE_GROUP}:{SCALE_TYPE}:"):
            return f"E255:0001{hd_key.rsplit(':', 1)[1]}"
        return self.hd_to_gc.get(hd_key)


def gc_to_hd(text: str, tags: TagMap) -> Tuple[str, List[str]]:
    """GameCube editor text in HD editor syntax. The second value lists the GameCube tags it could not convert."""
    missing: List[str] = []

    def replace(match: "re.Match[str]") -> str:
        key = tags.gc_to_hd_key(int(match.group(1)), match.group(2))
        if key is None:
            missing.append(match.group(0))
            return match.group(0)
        return render_tag(_hd_tag(key))

    return GC_ESCAPE.sub(replace, text), missing


def hd_to_gc(text: str, tags: TagMap) -> Tuple[str, List[str]]:
    """HD editor text in GameCube editor syntax. The second value lists the HD tags it could not convert."""
    out: List[str] = []
    missing: List[str] = []
    for token in from_editor(text):
        if isinstance(token, str):
            out.append(token)
            continue
        if isinstance(token, EndTag):
            missing.append(f"[/Tag:{token.group}:{token.type}]")
            out.append(render_tag(token))
            continue
        key = _hd_key(token)
        gc_key = tags.hd_to_gc_key(key)
        if gc_key is None:
            missing.append(render_tag(token))
            out.append(render_tag(token))
            continue
        _, hex_params = gc_key[1:].split(":", 1)
        out.append(f"{{escape:{gc_key[1:].split(':')[0]}:{hex_params}}}")
    return "".join(out), missing


def match_key(text: str, side: str, tags: TagMap) -> str:
    """The family match key of one editor text. side: "gc" or "hd". Colour tags are left out."""
    hd_text = gc_to_hd(text, tags)[0] if side == "gc" else text
    kept = [t.translate(_QUOTES) if isinstance(t, str) else t for t in from_editor(hd_text) if not _is_colour(t)]
    return to_editor(kept)


def _is_colour(token: Any) -> bool:
    return isinstance(token, Tag) and (token.group, token.type) == (COLOUR_GROUP, COLOUR_TYPE)


# -- derivation (dev tool; deterministic) ----------------------------------------------------------

def _core_and_atoms(tokens: Sequence[Any]) -> Tuple[str, List[Tuple[int, str]]]:
    """Text without tags and icon characters, and the atoms (tag or icon key) at each core offset."""
    core: List[str] = []
    atoms: List[Tuple[int, str]] = []
    for token in tokens:
        if isinstance(token, str):
            for char in token.translate(_QUOTES):
                if ord(char) in _PUA:
                    atoms.append((len(core), f"P{ord(char):04X}"))
                else:
                    core.append(char)
        elif isinstance(token, EndTag):
            atoms.append((len(core), f"C{token.group}:{token.type}"))
        else:
            atoms.append((len(core), _hd_key(token)))
    return "".join(core), atoms


def _gc_tokens(text: str) -> List[Any]:
    tokens: List[Any] = []
    position = 0
    for match in GC_ESCAPE.finditer(text):
        tokens.append(text[position:match.start()])
        tokens.append(("gc", _gc_key(int(match.group(1)), match.group(2))))
        position = match.end()
    tokens.append(text[position:])
    return tokens


def _gc_core_and_atoms(text: str) -> Tuple[str, List[Tuple[int, str]]]:
    core: List[str] = []
    atoms: List[Tuple[int, str]] = []
    for token in _gc_tokens(text):
        if isinstance(token, tuple):
            atoms.append((len(core), token[1]))
        else:
            core.extend(token.translate(_QUOTES))
    return "".join(core), atoms


def derive(pairs: Iterable[Tuple[str, str]]) -> Dict[str, Any]:
    """The GameCube -> HD tag table from (gc text, hd text) pairs of the same message.

    Pairs whose texts differ once tags and icons are removed carry no evidence and are skipped.
    Colour and scale escapes are not derived (see the module docstring). Returns the table and the statistics.
    """
    co_occur: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    gc_uses: collections.Counter = collections.Counter()
    hd_uses: collections.Counter = collections.Counter()
    compared = 0
    for gc_text, hd_text in pairs:
        gc_core, gc_atoms = _gc_core_and_atoms(gc_text)
        hd_core, hd_atoms = _core_and_atoms(from_editor(hd_text))
        if gc_core != hd_core:
            continue
        compared += 1
        hd_at: Dict[int, set] = collections.defaultdict(set)
        for offset, key in hd_atoms:
            hd_at[offset].add(key)
            hd_uses[key] += 1
        for offset, key in gc_atoms:
            gc_uses[key] += 1
            for hd_key in hd_at.get(offset, ()):
                co_occur[key][hd_key] += 1
    candidates: List[Tuple[float, int, str, str]] = []
    for gc_key in sorted(gc_uses):
        if gc_key.startswith("E255:"):
            continue
        best: Optional[Tuple[float, int, str]] = None
        for hd_key, together in sorted(co_occur.get(gc_key, {}).items()):
            if hd_key.startswith("P"):
                continue
            jaccard = together / (gc_uses[gc_key] + hd_uses[hd_key] - together)
            if best is None or (jaccard, together) > (best[0], best[1]):
                best = (jaccard, together, hd_key)
        if best is not None and best[0] >= JACCARD_MIN:
            candidates.append((best[0], best[1], gc_key, best[2]))
    table: Dict[str, str] = {}
    conflicts: List[str] = []
    for jaccard, together, gc_key, hd_key in sorted(candidates, key=lambda c: (-c[0], -c[1], c[2])):
        if hd_key in table.values():
            conflicts.append(f"{gc_key} -> {hd_key} dropped (taken)")
            continue
        table[gc_key] = hd_key
    return {"gc_to_hd": dict(sorted(table.items())), "compared": compared, "conflicts": conflicts}


def id_pairs(gc_units: Sequence[Tuple[int, str]], hd_units: Sequence[Tuple[int, str]]) -> List[Tuple[str, str]]:
    """(gc text, hd text) for every message id both versions have (the first HD message of an id)."""
    hd_by_id: Dict[int, str] = {}
    for message_id, text in hd_units:
        hd_by_id.setdefault(message_id, text)
    return [(text, hd_by_id[message_id]) for message_id, text in gc_units if message_id in hd_by_id]


def _ids_from_folders(bmg_folder: Path, msbt_folder: Path):
    """Editor texts with their ids: GameCube (BMG INF1 id) and HD (numeric label). Dev tool only."""
    from core.containers.rarc_container import RarcContainer
    from plugins.common.msbt import Msbt
    from plugins.zelda_tww.rules import GameRules as Gc

    rules = Gc()
    gc_units: List[Tuple[int, str]] = []
    for archive in sorted(bmg_folder.glob("bmgres*.arc")):
        container = RarcContainer(archive.read_bytes())
        for path in container.list_files():
            if not path.endswith(".bmg"):
                continue
            data, _names = rules.load_data_from_json_obj(container.read_file(path))
            for index, text in enumerate(data[0] if data else []):
                info = rules.last_loaded_bmg.messages[index].info
                gc_units.append((int.from_bytes(info[0:2], "big"), text))
    hd_units: List[Tuple[int, str]] = []
    for path in sorted(msbt_folder.glob("*.msbt")):
        msbt = Msbt(path.read_bytes())
        for index, tokens in enumerate(msbt.messages):
            label = msbt.labels.get(index, "")
            if re.fullmatch(r"\d{5}", label or ""):
                hd_units.append((int(label), to_editor(tokens)))
    return gc_units, hd_units


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3 or args[0] != "derive":
        print("usage: python -m plugins.zelda_ww.family_tags derive <bmg folder> <msbt folder>")
        return 2
    gc_units, hd_units = _ids_from_folders(Path(args[1]), Path(args[2]))
    result = derive(id_pairs(gc_units, hd_units))
    MAP_FILE.write_text(json.dumps({"version": 1, "gc_to_hd": result["gc_to_hd"]}, indent=2, ensure_ascii=False)
                        + "\n", encoding="utf-8")
    print(f"compared {result['compared']} messages; {len(result['gc_to_hd'])} tags mapped; "
          f"{len(result['conflicts'])} conflicts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
