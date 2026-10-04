"""The Tingle Tuner message file of The Wind Waker (GameCube): ``res/Gba/msg_LZ*.bin``.

When Link uses the Tingle Tuner, the GameCube boots the GBA with ``res/Gba/client_*.bin`` (a multiboot
program) and then sends it this file over the link cable; the GBA program unpacks it with the BIOS
(LZ77UnCompWram) into EWRAM at 0x02000000 and draws every Tingle line from it (zeldaret/tww
``d_a_agb.cpp``; the GBA side from the client program's own code).

File: GBA LZ77 (type 0x10). Unpacked: ``u16 data_start``, then one ``u16`` offset per message
(``(data_start - 2) / 2`` messages), relative to ``data_start``; USA offsets count bytes, the European
files (``msg_LZ0``..``4``: English, German, French, Spanish, Italian) count halfwords and pad every message
to an even length with 0xFF. A message runs to its 0xFF.

Text bytes: 0x00-0xF1 are glyphs (tile numbers of the client's 8x8 font; 0x68-0x9F draw a base tile
plus an accent from small tables), 0xF2-0xFE control codes, 0xFF the end. Control codes with one
argument byte: F2 icon, F3 Tingle animation, F5 speed, F6 sound, F7/F8 three/two-way choice, F9 wait
(frames), FC colour. Without: FD space, FE new line, F4 (a space), FA, FB.

The GBA draws every glyph 6 px wide, breaks a line by itself before a glyph that would start past
x = 95 (16 glyphs) and shows 6 lines of 12 px per page (y = 8 .. 68).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from core.containers import lz10

END, NEWLINE, SPACE = 0xFF, 0xFE, 0xFD
ARG_TAGS = {0xF2: "icon", 0xF3: "anim", 0xF5: "speed", 0xF6: "sound", 0xF7: "choice3", 0xF8: "choice2",
            0xF9: "wait", 0xFC: "color"}
BARE_TAGS = {0xF4: "f4", 0xFA: "fa", 0xFB: "fb"}
TAG_RE = re.compile(r"\{(?:(" + "|".join(ARG_TAGS.values()) + r"):(\d{1,3})|(" + "|".join(BARE_TAGS.values())
                    + r")|x([0-9A-Fa-f]{2}))\}")

GLYPH_WIDTH = 6
# Width of each {icon:N} (8 px per tile: + A B START SELECT L R heart), from the client's icon table.
ICON_WIDTHS = (8, 8, 8, 24, 24, 16, 16, 8)
LINE_WIDTH = 96
SCREEN_WIDTH = 240
LINES_PER_PAGE = 6

# The client font's glyphs as characters (tile number -> character); the same in every version.
GAME_CHARS: Dict[int, str] = {
    **{0x01 + i: chr(0x41 + i) for i in range(26)},
    **{0x1B + i: chr(0x61 + i) for i in range(26)},
    **{0x35 + i: str(i) for i in range(10)},
    0x52: "«", 0x53: "»", 0x56: "!", 0x58: "-", 0x59: "?", 0x5F: ".", 0x60: ",", 0x63: "'", 0x64: '"',
    0x66: ":", 0x67: "&",
}
# Ukrainian letters of the USA client: the look-alikes use the Latin glyphs (А В Е І К М Н О Р С Т Х У /
# а е і о р с у х), the rest take glyph codes no English message uses. 0x40-0x65 are plain glyphs (0x4F
# stays: the + icon draws it); 0x88 and 0x8E-0x9D are accent codes whose table entries the font save
# points at free tiles (``SLOT_TILES``) with a blank accent.
UKRAINIAN_CODES: Dict[int, str] = {
    0x40: "б", 0x41: "в", 0x42: "г", 0x43: "ґ", 0x44: "д", 0x45: "є", 0x46: "ж", 0x47: "з", 0x48: "и",
    0x49: "ї", 0x4A: "й", 0x4B: "к", 0x4C: "л", 0x4D: "м", 0x4E: "н", 0x50: "т", 0x51: "ф",
    0x54: "ц", 0x55: "ч", 0x57: "ш", 0x5A: "щ", 0x5B: "ь", 0x5C: "ю", 0x5D: "я",
    0x5E: "п", 0x61: "П", 0x62: "Г", 0x65: "Я",
    0x88: "Д", 0x8E: "Б", 0x8F: "Ґ", 0x90: "Є", 0x91: "Ж", 0x92: "З", 0x93: "И", 0x94: "Ї", 0x95: "Й",
    0x96: "Л", 0x97: "Ф", 0x98: "Ц", 0x99: "Ч", 0x9A: "Ш", 0x9B: "Щ", 0x9C: "Ь", 0x9D: "Ю",
}
LOOKALIKES = dict(zip("АВЕІКМНОРСТХУаеіорсух", "ABEIKMHOPCTXYaeiopcyx"))
# Accent code -> free tile (placeholder "X" tiles of the USA font) that holds its letter.
SLOT_TILES: Dict[int, int] = {0x88: 0x8D, **dict(zip(range(0x8E, 0x9E), [*range(0x78, 0x83), *range(0xFB, 0x100)]))}
# Accent code ranges of the USA client program: (first, last, table address, accent tile).
SLOT_TABLES: Sequence[Tuple[int, int, int, int]] = (
    (0x88, 0x8D, 0x0202B014, 0x83), (0x8E, 0x99, 0x0202AFFC, 0x88), (0x9A, 0x9B, 0x0202AFF8, 0x8B), (0x9C, 0x9D, 0x0202AFF4, 0x84))

# Unpacked size the GBA leaves for the messages (0x02000000 up to its receive buffer) and room of the
# receive buffer for the packed file, per file name (from each client program's buffer table).
UNPACKED_ROOM = {"msg_LZ.bin": 0x10800, "msg_LZ0.bin": 0x10800, "msg_LZ1.bin": 0x11B00,
                 "msg_LZ2.bin": 0x11000, "msg_LZ3.bin": 0x10800, "msg_LZ4.bin": 0x10800}
PACKED_ROOM = 0xA000


class FormatError(ValueError):
    """Not a Tingle Tuner message file."""


@dataclass
class MessageFile:
    messages: List[bytes]          # each without its 0xFF
    halfword_offsets: bool         # European layout

    @property
    def usa(self) -> bool:
        return not self.halfword_offsets


def _starts_ok(data: bytes, start: int, offsets: Sequence[int], scale: int) -> bool:
    for offset in offsets:
        at = start + offset * scale
        if at >= len(data) or (offset and data[at - 1] != END):
            return False
    return True


def _read_message(data: bytes, at: int) -> bytes:
    end = at
    while True:
        if end >= len(data):
            raise FormatError("message runs past the end of the file")
        byte = data[end]
        if byte == END:
            return data[at:end]
        end += 2 if byte in ARG_TAGS else 1


def parse(packed: bytes) -> MessageFile:
    try:
        data, _end = lz10.decompress(packed)
    except ValueError as error:
        raise FormatError(str(error)) from None
    if len(data) < 4:
        raise FormatError("too short")
    start = int.from_bytes(data[0:2], "little")
    if start < 4 or start % 2 or start > len(data):
        raise FormatError("bad table size")
    offsets = [int.from_bytes(data[i:i + 2], "little") for i in range(2, start, 2)]
    for scale in (2, 1):
        if _starts_ok(data, start, offsets, scale):
            return MessageFile([_read_message(data, start + o * scale) for o in offsets], scale == 2)
    raise FormatError("message offsets do not point at messages")


def _layout(file: MessageFile) -> Tuple[List[int], bytes]:
    """Offsets (in the file's units) and the message bytes: every distinct message once."""
    body = bytearray()
    placed: Dict[bytes, int] = {}
    offsets = []
    for message in file.messages:
        if message not in placed:
            placed[message] = len(body)
            body += message + bytes([END])
            if file.halfword_offsets and len(body) % 2:
                body.append(END)
        offsets.append(placed[message] // (2 if file.halfword_offsets else 1))
    return offsets, bytes(body)


def build(file: MessageFile) -> bytes:
    """The unpacked file: the table, then every distinct message once (identical messages share)."""
    offsets, body = _layout(file)
    if offsets and max(offsets) > 0xFFFF:
        raise ValueError("Tingle Tuner text: the messages no longer fit the 16-bit offset table")
    out = bytearray((2 + 2 * len(offsets)).to_bytes(2, "little"))
    for offset in offsets:
        out += offset.to_bytes(2, "little")
    out += body
    out += bytes([END]) * (-len(out) % 4)
    return bytes(out)


def pack(file: MessageFile, name: str = "msg_LZ.bin") -> bytes:
    """The game file; ValueError when it is bigger than the GBA has room for."""
    size = 2 + 2 * len(file.messages) + len(_layout(file)[1])
    room = UNPACKED_ROOM.get(name, UNPACKED_ROOM["msg_LZ.bin"])
    if size > room:
        raise ValueError(f"Tingle Tuner text ({name}) is {size - room} bytes too long: the GBA keeps "
                         f"{room} bytes for it unpacked, the translation needs {size}. Shorten some lines.")
    packed = lz10.compress(build(file))
    if len(packed) > PACKED_ROOM:
        raise ValueError(f"Tingle Tuner text ({name}) packs into {len(packed)} bytes; the GBA receive buffer "
                         f"holds {PACKED_ROOM}. Shorten some lines.")
    return packed


# -- strings inside the USA client program ---------------------------------------------------------

# The unpacked program of client_u.bin (at 0x0201B000) draws two strings of its own: "Calling..." and
# the error screen shown when no GameCube answers. (Unpacked address, bytes it may take with its 0xFF;
# each is reached through one literal-pool pointer, so it changes only in place.)
PROGRAM_ADDRESS = 0x0201B000
PROGRAM_SIZE = 0x19A15
PROGRAM_STRINGS: Sequence[Tuple[int, int]] = ((0x0202AB40, 12), (0x0203336C, 80))


def program_strings(program: bytes) -> Optional[List[bytes]]:
    """The strings of the USA client program (without 0xFF), or None for another program."""
    if len(program) != PROGRAM_SIZE:
        return None
    out = []
    for address, room in PROGRAM_STRINGS:
        at = address - PROGRAM_ADDRESS
        end = program.find(bytes([END]), at, at + room)
        if end < 0:
            return None
        out.append(bytes(program[at:end]))
    return out


def write_program_strings(program: bytes, strings: Sequence[bytes]) -> bytes:
    """``program`` with its strings replaced in place; ValueError when one is longer than its room."""
    out = bytearray(program)
    for (address, room), text in zip(PROGRAM_STRINGS, strings):
        if len(text) + 1 > room:
            raise ValueError(f"Tingle Tuner program text: {len(text)} bytes, the program has room for {room - 1}")
        at = address - PROGRAM_ADDRESS
        end = program.index(bytes([END]), at)
        out[at:end + 1] = bytes(end + 1 - at)       # the old string's bytes become zero
        out[at:at + len(text) + 1] = bytes(text) + bytes([END])
    return bytes(out)


# -- text ------------------------------------------------------------------------------------------


def char_table(usa: bool = True) -> Dict[int, str]:
    return {**GAME_CHARS, **UKRAINIAN_CODES} if usa else dict(GAME_CHARS)


def decode(message: bytes, usa: bool = True) -> str:
    chars = char_table(usa)
    out: List[str] = []
    i = 0
    while i < len(message):
        byte = message[i]
        if byte in ARG_TAGS and i + 1 < len(message):
            out.append(f"{{{ARG_TAGS[byte]}:{message[i + 1]}}}")
            i += 2
            continue
        if byte == NEWLINE:
            out.append("\n")
        elif byte == SPACE:
            out.append(" ")
        elif byte in BARE_TAGS:
            out.append(f"{{{BARE_TAGS[byte]}}}")
        elif byte in chars:
            out.append(chars[byte])
        else:
            out.append(f"{{x{byte:02X}}}")
        i += 1
    text = "".join(out)
    return _cyrillic_lookalikes(text) if usa and any(c in _UKRAINIAN_ONLY for c in text) else text


_UKRAINIAN_ONLY = set(UKRAINIAN_CODES.values())
_TO_CYRILLIC = {latin: uk for uk, latin in LOOKALIKES.items()}
_WORD_RE = re.compile(r"[^\W\d_]+")


def _cyrillic_lookalikes(text: str) -> str:
    """In a Ukrainian message, a word written only with letters Cyrillic shares with Latin (and Cyrillic
    ones) reads as Cyrillic: the bytes are the same, the editor shows Ukrainian. Tags stay as they are."""
    def word(match: re.Match) -> str:
        letters = match.group(0)
        if all(c in _TO_CYRILLIC or c in _UKRAINIAN_ONLY for c in letters):
            return "".join(_TO_CYRILLIC.get(c, c) for c in letters)
        return letters

    parts, pos = [], 0
    for tag in TAG_RE.finditer(text):
        parts += [_WORD_RE.sub(word, text[pos:tag.start()]), tag.group(0)]
        pos = tag.end()
    return "".join(parts + [_WORD_RE.sub(word, text[pos:])])


def encoder(usa: bool = True) -> Dict[str, int]:
    """Character -> byte: the font's characters, then the Ukrainian look-alikes on Latin glyphs."""
    table = {char: code for code, char in char_table(usa).items()}
    table.update({uk: table[latin] for uk, latin in LOOKALIKES.items() if uk not in table})
    table.update({"’": 0x63, "ʼ": 0x63, "“": 0x64, "”": 0x64, "—": 0x58, "–": 0x58, " ": SPACE})
    return table


def encode(text: str, usa: bool = True, missing: Optional[set] = None) -> bytes:
    """Editor text -> message bytes; a character without a glyph becomes '?' (and goes into ``missing``)."""
    table = encoder(usa)
    names = {name: code for code, name in {**ARG_TAGS, **BARE_TAGS}.items()}
    out = bytearray()
    pos = 0
    for match in TAG_RE.finditer(text):
        _encode_plain(text[pos:match.start()], table, out, missing)
        name, value, bare, raw = match.groups()
        if name:
            out += bytes([names[name], int(value) & 0xFF])
        elif bare:
            out.append(names[bare])
        else:
            out.append(int(raw, 16))
        pos = match.end()
    _encode_plain(text[pos:], table, out, missing)
    return bytes(out)


def _encode_plain(text: str, table: Dict[str, int], out: bytearray, missing: Optional[set]) -> None:
    for char in text.replace("\r\n", "\n"):
        if char == "\n":
            out.append(NEWLINE)
        elif char == " ":
            out.append(SPACE)
        elif char in table:
            out.append(table[char])
        else:
            if missing is not None:
                missing.add(char)
            out.append(0x59)


def line_width(line: str) -> int:
    """Pixels of one editor line as the GBA draws it (tags other than icons take no room)."""
    width = 0
    pos = 0
    for match in TAG_RE.finditer(line):
        width += GLYPH_WIDTH * len(line[pos:match.start()])
        if match.group(1) == "icon":
            index = int(match.group(2))
            width += ICON_WIDTHS[index] if index < len(ICON_WIDTHS) else 8
        elif match.group(4):
            width += GLYPH_WIDTH
        pos = match.end()
    return width + GLYPH_WIDTH * len(line[pos:])
