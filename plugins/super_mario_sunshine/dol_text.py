"""The English text the Super Mario Sunshine executable (sys/main.dol) draws, as one editable member.

The game code keeps these strings in main.dol, not in the BMG files: the progressive-scan question, Yes and No, the
card title and the English save comment, and the six disc-error lines. Each string is NUL-terminated and sits right
after the next one, so its room is exactly its English length with the NUL. A translation must fit that room (in
single-byte characters, NUL included); a shorter text is padded with zeros inside the room. The executable keeps its
size and nothing outside the rooms changes.

The two progressive-scan confirmations (strSetProg, strSetInter) contain escape codes for colour and position. They
are not in this version.

``DolText`` reads ``sys/main.dol`` for the build (``build.py``); it is not registered with ``ContainerManager``, so
Picoripi never opens the executable as a container. Its one member, ``main_strings.dolstr``, is a JSON document with the
current text of each string: the unpack writes it as ``sys/main_strings.dolstr`` (``document_of``), which is the file the
project edits, and the build writes it back into its rooms (``apply_document``). Writing it checks every room; ``pack``
writes the executable.
"""
import hashlib
import json
from typing import Dict, List, Tuple

from core.containers.base_container import BaseArchiveContainer

MEMBER = "main_strings.dolstr"
FORMAT = "picoripi-dol-strings"
# (id, DOL offset, room in bytes including the NUL, SHA-256 of the room as the retail executable holds it). Only the
# digests are kept, so no game text is in the repository; a room's English length is its size minus the NUL.
STRINGS: Tuple[Tuple[str, int, int, str], ...] = (
    ("progressive_question", 0x3BE148, 52, "89ef6bb29bd1e7e650ba33b6b3c5e97f839f399a4730476db0354b399bf6e000"),
    ("yes", 0x3E6BD8, 4, "03cb5fb3dd8f56aa60ba08fe532d55484ffaca42439a4ce03fd1db3bfe54a8aa"),
    ("no", 0x3E6BDC, 3, "511a5d61e579e32d7a0329f681e54c26440084a69a7ce1c3c3f837a96e06aa29"),
    ("card_title", 0x3A46C8, 21, "7d02516598a255915f148774e7b1bbff65e97be01274f0eb78274f547338838f"),
    ("card_comment_en", 0x3A46E0, 16, "4131441c87d9d3ad434885b06b76f428eec36e9d659221c333fbcd42f19943d2"),
    ("disc_error_1", 0x3A103C, 121, "091a19101bb59af63b8af2418d70ad5f199e3ee9e1c1de614def80257b5a5d43"),
    ("disc_error_2", 0x3A10B8, 106, "a062cb665202ed95354a22561338bea326a6392e9ee10eb828bac51ea2d4029f"),
    ("disc_error_3", 0x3A1124, 16, "621edbafa8e7db2785cc94ce5dbd73fac5dd4b5031972b227f8ca73ba4387a43"),
    ("disc_error_4", 0x3A1134, 74, "e4b8adcf610bf3aaf6804721f86d5293e4f59edcbf2f55c3904c4ceaae2e4799"),
    ("disc_error_5", 0x3A1180, 48, "70cee2bc2321167e2cc07e9e7ada886efb0f3857eea75c40a452f3917be56c27"),
    ("disc_error_6", 0x3A11B0, 87, "6fa879e82e8af20a43e3a5124fe2327d1653cc8e8e50b047373742075f1bccf6"),
)


def _is_dol(data: bytes) -> bool:
    return len(data) > 0x100 and data[:4] == b"\x00\x00\x01\x00" and data[0xE0:0xE4] != b"\x00\x00\x00\x00"


def _room_of(offset: int, room: int, data: bytes) -> bytes:
    return data[offset:offset + room]


def _room_matches(data: bytes, offset: int, room: int, digest: str) -> bool:
    """True when the room at ``offset`` holds the retail bytes (its digest), NUL included."""
    return offset + room <= len(data) and hashlib.sha256(_room_of(offset, room, data)).hexdigest() == digest


class DolText(BaseArchiveContainer):
    """``sys/main.dol`` of Super Mario Sunshine (GMSE01) with its English strings as the member ``main_strings.dolstr``."""

    @classmethod
    def can_handle(cls, data: bytes) -> bool:
        return _is_dol(data) and _room_matches(data, *STRINGS[0][1:])

    def __init__(self, data: bytes) -> None:
        self._data = bytes(data)
        for ident, offset, room, digest in STRINGS:
            if not _room_matches(self._data, offset, room, digest):
                raise ValueError(f"main.dol: the text at {offset:#x} is not the expected {ident}")
        self._changes: Dict[str, bytes] = {}

    def list_files(self) -> List[str]:
        return [MEMBER]

    def read_file(self, path: str) -> bytes:
        if path != MEMBER:
            raise KeyError(path)
        rows = []
        for ident, offset, room, _digest in STRINGS:
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
        rooms = {ident: (offset, room) for ident, offset, room, _digest in STRINGS}
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
        for ident, offset, room, _digest in STRINGS:
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
