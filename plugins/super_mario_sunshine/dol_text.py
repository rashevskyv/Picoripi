"""The English text the Super Mario Sunshine executable (sys/main.dol) draws, as one editable member.

The game code keeps these strings in main.dol, not in the BMG files: the progressive-scan question, Yes and No, the
card title and the English save comment, and the six disc-error lines. Each string is NUL-terminated and sits right
after the next one, so its room is exactly its English length with the NUL. A translation must fit that room (in
single-byte characters, NUL included); a shorter text is padded with zeros inside the room. The executable keeps its
size and nothing outside the rooms changes.

The two progressive-scan confirmations (strSetProg, strSetInter) contain escape codes for colour and position. They
are not in this version.

``DolText`` is the container Picoripi opens for ``sys/main.dol``. Its one member, ``main_strings.dolstr``, is a JSON
document with the current text of each string. Writing it checks every room; ``pack`` writes the executable.
"""
import json
from typing import Dict, List, Tuple

from core.containers.base_container import BaseArchiveContainer

MEMBER = "main_strings.dolstr"
FORMAT = "picoripi-dol-strings"
PROBE = b"Would you like to display in\nprogressive scan mode?"

# (id, DOL offset, room in bytes including the NUL, English bytes as the retail executable holds them)
STRINGS: Tuple[Tuple[str, int, int, bytes], ...] = (
    ("progressive_question", 0x3BE148, 52, b"Would you like to display in\nprogressive scan mode?"),
    ("yes", 0x3E6BD8, 4, b"Yes"),
    ("no", 0x3E6BDC, 3, b"No"),
    ("card_title", 0x3A46C8, 21, b"Super Mario Sunshine"),
    ("card_comment_en", 0x3A46E0, 16, b"%d/%d Save Data"),
    ("disc_error_1", 0x3A103C, 121, b"An error has occurred. Turn the\npower OFF and check the\n"
                                    b"NINTENDO GAMECUBE\x99\nInstruction Booklet for further instructions."),
    ("disc_error_2", 0x3A10B8, 106, b"The Disc could not be read.\nPlease read the NINTENDO GAMECUBE\x99\n"
                                    b"Instruction Booklet for\nmore information.\n"),
    ("disc_error_3", 0x3A1124, 16, b"Reading Disc..."),
    ("disc_error_4", 0x3A1134, 74, b"The Disc Cover is open.\nTo continue playing,\nplease close the\nDisc Cover."),
    ("disc_error_5", 0x3A1180, 48, b"Please insert a Super Mario Sunshine\nGame Disc."),
    ("disc_error_6", 0x3A11B0, 87, b"This Disc is not\nSuper Mario Sunshine.\nPlease insert a Super\n"
                                   b"Mario Sunshine Game Disc."),
)


def _is_dol(data: bytes) -> bool:
    return len(data) > 0x100 and data[:4] == b"\x00\x00\x01\x00" and data[0xE0:0xE4] != b"\x00\x00\x00\x00"


def _room_of(offset: int, room: int, data: bytes) -> bytes:
    return data[offset:offset + room]


class DolText(BaseArchiveContainer):
    """``sys/main.dol`` of Super Mario Sunshine (GMSE01) with its English strings as the member ``main_strings.dolstr``."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return _is_dol(data) and PROBE in data

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        for ident, offset, room, english in STRINGS:
            if offset + room > len(self._data) or len(english) + 1 != room:
                raise ValueError(f"main.dol: the room of {ident} does not match the table")
            if _room_of(offset, room, self._data) != english + b"\0":
                raise ValueError(f"main.dol: the text at {offset:#x} is not the expected {ident}")
        self._changes: Dict[str, bytes] = {}

    def list_files(self) -> List[str]:
        return [MEMBER]

    def read_file(self, path: str) -> bytes:
        if path != MEMBER:
            raise KeyError(path)
        rows = []
        for ident, offset, room, _english in STRINGS:
            encoded = self._changes.get(ident)
            if encoded is None:
                encoded = _room_of(offset, room, self._data).split(b"\0", 1)[0]
            rows.append({"id": ident, "text": encoded.decode("cp1252"), "room": room})
        return json.dumps({"format": FORMAT, "strings": rows}, ensure_ascii=False, indent=1).encode("utf-8")

    def write_file(self, path: str, data: bytes) -> None:
        if path != MEMBER:
            raise KeyError(path)
        document = json.loads(bytes(data).decode("utf-8"))
        if document.get("format") != FORMAT:
            raise ValueError("main.dol: not a text document of the executable")
        rooms = {ident: (offset, room) for ident, offset, room, _english in STRINGS}
        changes: Dict[str, bytes] = {}
        for row in document.get("strings", []):
            ident = row.get("id")
            if ident not in rooms:
                raise ValueError(f"main.dol: unknown string {ident!r}")
            _offset, room = rooms[ident]
            try:
                encoded = str(row.get("text", "")).encode("cp1252")
            except UnicodeEncodeError as error:
                raise ValueError(f"main.dol/{ident}: a character cannot be written in one byte ({error.object[error.start]!r})")
            if len(encoded) + 1 > room:
                raise ValueError(f"main.dol/{ident}: {len(encoded)} bytes, the executable has room for {room - 1}")
            if b"\0" in encoded:
                raise ValueError(f"main.dol/{ident}: a text cannot hold a NUL byte")
            changes[ident] = encoded
        self._changes = changes

    def has_pending_changes(self) -> bool:
        return bool(self._changes)

    def pack(self) -> bytes:
        out = bytearray(self._data)
        for ident, offset, room, _english in STRINGS:
            if ident in self._changes:
                encoded = self._changes[ident]
                out[offset:offset + room] = encoded + bytes(room - len(encoded))
        return bytes(out)


def is_text_document(data: bytes) -> bool:
    """True when ``data`` is the member's JSON document (its format tag is in the first bytes)."""
    return FORMAT.encode("ascii") in bytes(data[:80])


def document_of(dol: bytes) -> bytes:
    """The current text of the executable's strings, as the member's JSON document."""
    return DolText(dol).read_file(MEMBER)


def apply_document(dol: bytes, document: bytes) -> bytes:
    """``dol`` with the strings of ``document`` written into their rooms. Raises ValueError for a string that does not fit."""
    container = DolText(dol)
    container.write_file(MEMBER, document)
    return container.pack()
