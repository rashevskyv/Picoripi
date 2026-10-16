"""Messages of a Generation III ROM (FireRed, LeafGreen, Ruby, Sapphire, Emerald): read them from the ROM, write them back.

A message is the bytes from its label to the terminator 0xFF. The text the editor shows is the decompilation's own
form: a charmap character as itself, a control code as ``\\n`` ``\\l`` ``\\p``, a named code as ``{NAME}`` and a
named code with arguments as ``{NAME ARG}``. A byte with no name is ``{0xNN}``. ``encode(decode(bytes)) == bytes``
for every byte string, so a message that is not edited comes back byte for byte.

The facts (the charmap, the label addresses) live in ``rom_facts/``. They come from the decompilation and its link
map; ``tools/pokemon_fr_rom_facts.py`` writes them and checks each message against the ROM.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from core.i18n import tr
from plugins.common.gba_rom import Relocator, RomError, fix_header, pointer_index, write_in_place

TERMINATOR = 0xFF
FACTS_DIR = Path(__file__).with_name("rom_facts")
CHARMAP_FILE = "charmap_gen3.json"


class CodecError(ValueError):
    """A text cannot be written in this charmap (an unknown character, a bad code)."""


@dataclass(frozen=True)
class Unit:
    """One message: its label, its file offset and its size in bytes including the terminator.

    A ``fixed`` unit is an entry of a C-built table: it never moves, nothing points to it, and it is padded with
    the byte ``pad`` up to its size. A longer text is refused at build time.
    """

    label: str
    offset: int
    size: int
    fixed: bool = False
    pad: int = 0
    braille: bool = False     # a braille text: its bytes are braille character codes (the ``braille_chars`` facts)


class Charmap:
    """The byte codes of the game's text. Built from the facts file; ``args`` gives the argument count of a prefix."""

    def __init__(self, chars: Sequence[Tuple[str, int]], names: Sequence[Tuple[str, bytes]],
                 args: Dict[str, int], sounds: Sequence[Tuple[str, bytes]] = (),
                 sound_args: Sequence[str] = ()) -> None:
        self.char_of: Dict[int, str] = {}
        self.byte_of: Dict[str, int] = {}
        for key, code in chars:
            self.char_of.setdefault(code, key)
            self.byte_of.setdefault(key, code)
        self.byte_of.pop("$", None)          # the terminator is written by the codec, never by a character
        self.name_bytes: Dict[str, bytes] = {}
        self.single_name: Dict[int, str] = {}
        self.multi: Dict[bytes, str] = {}
        for name, code in names:
            self.name_bytes.setdefault(name, code)
            if len(code) == 1:
                self.single_name.setdefault(code[0], name)
            else:
                self.multi.setdefault(code, name)
        self.lengths = sorted({len(code) for code in self.multi}, reverse=True)
        self.args = dict(args)
        # Sound ids: the arguments of playse and playbgm. They are never text codes.
        self.sound_of: Dict[bytes, str] = {}
        self.sound_bytes: Dict[str, bytes] = {}
        for name, code in sounds:
            self.sound_bytes.setdefault(name, code)
            self.sound_of.setdefault(code, name)
        self.sound_args = set(sound_args)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Charmap":
        data = json.loads((path or FACTS_DIR / CHARMAP_FILE).read_text(encoding="utf-8"))
        chars = [(key, int(code, 16)) for key, code in data["chars"]]
        names = [(name, bytes.fromhex(code)) for name, code in data["names"]]
        sounds = [(name, bytes.fromhex(code)) for name, code in data["sounds"]]
        return cls(chars, names, data["args"], sounds, data["sound_args"])

    # ----- ROM bytes -> text -----

    def _named_at(self, data: bytes, at: int) -> Optional[Tuple[str, int]]:
        for length in self.lengths:
            code = data[at:at + length]
            if len(code) == length and code in self.multi:
                return self.multi[code], length
        return None

    def _arg_text(self, value: int) -> str:
        return self.single_name.get(value) or f"0x{value:02X}"

    def decode(self, data: bytes) -> str:
        """The editor text of a message. Reads up to the terminator; the terminator is not part of the text."""
        out: List[str] = []
        at = 0
        while at < len(data) and data[at] != TERMINATOR:
            named = self._named_at(data, at)
            if named is not None:
                name, length = named
                at += length
                args: List[str] = []
                if name in self.sound_args:
                    pair = data[at:at + 2]
                    if len(pair) == 2 and TERMINATOR not in pair:
                        args.append(self.sound_of.get(pair) or f"0x{pair[0]:02X} 0x{pair[1]:02X}")
                        at += 2
                else:
                    count = self.args.get(name, 0)
                    while count and at < len(data) and data[at] != TERMINATOR:
                        args.append(self._arg_text(data[at]))
                        at += 1
                        count -= 1
                out.append("{" + " ".join([name, *args]) + "}")
                continue
            code = data[at]
            at += 1
            key = self.char_of.get(code)
            if key is not None:
                out.append('\\"' if key == '"' else "\\\\" if key == "\\" else key)
            elif code in self.single_name:
                out.append("{" + self.single_name[code] + "}")
            else:
                out.append(f"{{0x{code:02X}}}")
        return "".join(out)

    # ----- text -> ROM bytes -----

    def _token(self, inner: str) -> bytes:
        parts = inner.split()
        if not parts:
            raise CodecError(tr("An empty code in braces."))
        head = parts[0]
        if head.lower().startswith("0x") and len(parts) == 1:
            return bytes([self._hex_byte(head)])
        if head not in self.name_bytes:
            raise CodecError(tr("Unknown code {0}.", "{" + head + "}"))
        out = bytearray(self.name_bytes[head])
        for arg in parts[1:]:
            if arg.lower().startswith("0x"):
                out.append(self._hex_byte(arg))
            elif arg in self.sound_bytes:
                out += self.sound_bytes[arg]
            elif arg in self.name_bytes and len(self.name_bytes[arg]) == 1:
                out += self.name_bytes[arg]
            else:
                raise CodecError(tr("Unknown argument {0} in {1}.", arg, "{" + inner + "}"))
        return bytes(out)

    @staticmethod
    def _hex_byte(text: str) -> int:
        try:
            value = int(text, 16)
        except ValueError as exc:
            raise CodecError(tr("Bad hex code {0}.", text)) from exc
        if not 0 <= value <= 0xFF:
            raise CodecError(tr("Code {0} is not one byte.", text))
        return value

    def encode(self, text: str) -> bytes:
        """The bytes of a message with its terminator. Raises ``CodecError`` on a character with no cell."""
        out = bytearray()
        at = 0
        while at < len(text):
            char = text[at]
            if char == "\\":
                if at + 1 >= len(text):
                    raise CodecError(tr("A backslash at the end of the text."))
                key = text[at:at + 2]
                if key in self.byte_of:
                    out.append(self.byte_of[key])
                elif text[at + 1] in '"\\\'' and text[at + 1] in self.byte_of:
                    out.append(self.byte_of[text[at + 1]])
                else:
                    raise CodecError(tr("Unknown escape {0}.", key))
                at += 2
                continue
            if char == "{":
                end = text.find("}", at)
                if end < 0:
                    raise CodecError(tr("An opening brace without a closing one."))
                out += self._token(text[at + 1:end])
                at = end + 1
                continue
            if char not in self.byte_of:
                raise CodecError(tr("No cell for {0} in this game's charmap.", repr(char)))
            out.append(self.byte_of[char])
            at += 1
        out.append(TERMINATOR)
        return bytes(out)


def load_units(path: Optional[Path] = None) -> Tuple[List[Unit], int, Dict[str, object]]:
    """The messages of a game's facts file, the first free file offset, and the facts header."""
    data = json.loads((path or FACTS_DIR / "firered_usa_rev0.json").read_text(encoding="utf-8"))
    units = [Unit(label, int(offset), int(size)) for label, offset, size in data["units"]]
    for item in data.get("braille_units", []):
        # A fourth item "fixed" marks a text a window format precedes: its pointer names the format, so it keeps its size.
        units.append(Unit(item[0], int(item[1]), int(item[2]), fixed=len(item) > 3, braille=True))
    header = {key: value for key, value in data.items() if key != "units"}
    return units, int(data["free_start"]), header


def braille_charmap(path: Optional[Path] = None) -> Optional[Charmap]:
    """The braille codes of a facts file (``braille_chars``: ``[char, hex code]``), or None when it has none."""
    data = json.loads((path or FACTS_DIR / "firered_usa_rev0.json").read_text(encoding="utf-8"))
    if "braille_chars" not in data:
        return None
    return Charmap([(char, int(code, 16)) for char, code in data["braille_chars"]], [], {})


def load_tables(path: Optional[Path] = None) -> List[Unit]:
    """The entries of the C-built tables of a facts file (``c_tables``): one fixed unit per entry."""
    data = json.loads((path or FACTS_DIR / "firered_usa_rev0.json").read_text(encoding="utf-8"))
    units: List[Unit] = []
    for table in data.get("c_tables", []):
        if table.get("kind") == "pointer":
            # a text a pointer table names: it may grow, so it is not a fixed field
            for index, offset, size in table["units"]:
                units.append(Unit(f"{table['label']}{index}", int(offset), int(size)))
            continue
        size = int(table.get("size", table["stride"]))
        for index in range(int(table["count"])):
            units.append(Unit(f"{table['label']}{index}", int(table["offset"]) + index * int(table["stride"]),
                              size, True, int(table.get("pad", 0))))
    units.extend(c_text_units(path))
    return units


def c_text_units(path: Optional[Path] = None) -> List[Unit]:
    """The texts the C code builds (``c_texts``): each a unit with its own label, relocatable like a message."""
    data = json.loads((path or FACTS_DIR / "firered_usa_rev0.json").read_text(encoding="utf-8"))
    return [Unit(str(label), int(offset), int(size)) for table in data.get("c_texts", [])
            for label, offset, size in table["units"]]


def table_files(path: Optional[Path] = None) -> Dict[str, List[str]]:
    """The source file of each C-built table, with the labels of its entries in order."""
    data = json.loads((path or FACTS_DIR / "firered_usa_rev0.json").read_text(encoding="utf-8"))
    files: Dict[str, List[str]] = {}
    for table in data.get("c_texts", []):
        files.setdefault(table["file"], []).extend(str(label) for label, _, _ in table["units"])
    for table in data.get("c_tables", []):
        if table.get("kind") == "pointer":
            files.setdefault(table["file"], []).extend(f"{table['label']}{index}" for index, _, _ in table["units"])
            continue
        files.setdefault(table["file"], []).extend(f"{table['label']}{i}" for i in range(int(table["count"])))
    return files


def _codec(unit: Unit, charmap: Charmap, braille: Optional[Charmap]) -> Charmap:
    """The character codes of one unit: the braille table for a braille text, else the game's charmap."""
    return braille if unit.braille and braille is not None else charmap


def read_all(rom: bytes, units: Sequence[Unit], charmap: Charmap,
             braille: Optional[Charmap] = None) -> Dict[str, str]:
    """The editor text of every message, keyed by label."""
    return {unit.label: _codec(unit, charmap, braille).decode(rom[unit.offset:unit.offset + unit.size])
            for unit in units}


def write_all(rom: bytes, units: Sequence[Unit], charmap: Charmap, floor: int,
              texts: Dict[str, str], braille: Optional[Charmap] = None) -> bytes:
    """A patched copy of the ROM with the given messages written. A message that does not fit moves to free space.

    The header complement is written as well. With ``texts`` equal to ``read_all`` the result equals the input.
    """
    by_label = {unit.label: unit for unit in units}
    index = pointer_index(rom)
    patched = bytearray(rom)
    relocator = Relocator(patched, index, floor)
    for label, text in texts.items():
        unit = by_label.get(label)
        if unit is None:
            raise RomError(tr("No message named {0} in this game.", label))
        codec = _codec(unit, charmap, braille)
        data = codec.encode(text)
        if unit.fixed:
            if codec.decode(rom[unit.offset:unit.offset + unit.size]) == text:
                continue          # the field keeps its own padding when its text is unchanged
            if len(data) > unit.size:
                raise RomError(tr("{0} is {1} bytes long; its table gives {2} bytes, the terminator included. "
                                  "Shorten it.", unit.label, str(len(data)), str(unit.size)))
            patched[unit.offset:unit.offset + unit.size] = data + bytes([unit.pad]) * (unit.size - len(data))
        elif len(data) <= unit.size:
            write_in_place(patched, unit.offset, unit.size, data)
        else:
            relocator.move(unit.offset, unit.size, data)
    fix_header(patched)
    return bytes(patched)
