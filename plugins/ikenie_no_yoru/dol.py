r"""The text inside ``sys/main.dol`` of Ikenie no Yoru with the English patch: fixed string slots.

The executable keeps the save banner title, the disc and memory error messages, the Balance Board messages and
the default names of the five girls. The English patch wrote its strings into the Japanese slots, so every slot
keeps its address; a string may be as long as its slot (up to the next string, less the end mark). Slots are
Shift-JIS (``sjis``, the Japanese game's encoding; ``\r`` shows as ``{CR}``) or UTF-16 (``utf16``).
"""
from __future__ import annotations

from typing import List, Tuple

SIZE = 2372576
MARK = (0x1F85A8, b"NAND_RESULT_OK\0")       # a debug string the patch keeps: identifies this main.dol
# (offset, end, encoding, what): the string may use offset .. end minus its end mark
SLOTS: Tuple[Tuple[int, int, str, str], ...] = (
    (0x1F7608, 0x1F7618, "utf16", "Save banner title"),
    (0x1F7618, 0x1F763C, "utf16", "Save banner subtitle"),
    (0x1F8158, 0x1F8188, "sjis", "Disc: insert the disc"),
    (0x1F8188, 0x1F81D5, "sjis", "Disc: cannot be read"),
    (0x1F81D5, 0x1F8260, "sjis", "Disc: error, turn off"),
    (0x1F826D, 0x1F82C3, "sjis", "Save: data corrupted"),
    (0x1F82D0, 0x1F83B0, "sjis", "Save: not enough space"),
    (0x1F83B0, 0x1F8474, "sjis", "Save: not enough files"),
    (0x1F8474, 0x1F84E6, "sjis", "Save: error"),
    (0x1F84E6, 0x1F8552, "sjis", "Save: cannot read or write"),
    (0x1F8552, 0x1F85A8, "sjis", "Save: memory corrupted"),
    (0x1F8800, 0x1F881C, "utf16", "Balance Board: please wait"),
    (0x1F881C, 0x1F8850, "utf16", "Balance Board: power on"),
    (0x1F8850, 0x1F8880, "utf16", "Balance Board: replace batteries"),
    (0x1F8880, 0x1F88C4, "utf16", "Balance Board: get off"),
    (0x1F88C4, 0x1F8904, "utf16", "Balance Board: get on"),
    (0x1F8904, 0x1F895A, "utf16", "Balance Board: error, get off"),
    (0x1F8960, 0x1F89A8, "utf16", "Balance Board: maximum reached"),
    (0x1F89A8, 0x1F8A04, "utf16", "Balance Board: error"),
    (0x1F8A08, 0x1F8A40, "utf16", "Balance Board: set-up complete"),
    (0x1F8A80, 0x1F8AF0, "sjis", "Balance Board: replace the battery"),
    (0x1F8AF0, 0x1F8B5C, "sjis", "Balance Board: connection lost"),
    (0x1F8B5C, 0x1F8B90, "sjis", "Remote: disconnect extension"),
    (0x1F8B90, 0x1F8BB0, "sjis", "Remote: connection lost"),
) + tuple((table + 0x20 * n, table + 0x20 * n + 0x14, "utf16", f"Default name {n + 1}")
          for table in (0x207BAC, 0x20A25C) for n in range(5))


def is_main_dol(raw: bytes) -> bool:
    at, mark = MARK
    return len(raw) == SIZE and bytes(raw[at:at + len(mark)]) == mark


def _end_mark(kind: str) -> bytes:
    return b"\0\0" if kind == "utf16" else b"\0"


def strings(raw: bytes) -> List[str]:
    out = []
    for offset, end, kind, _what in SLOTS:
        data = bytes(raw[offset:end])
        if kind == "utf16":
            text = data.decode("utf-16-be").split("\0")[0]
        else:
            text = data.split(b"\0")[0].decode("cp932").replace("\r", "{CR}")
        out.append(text)
    return out


def build(raw: bytes, texts: List[str]) -> bytes:
    """``raw`` with the slots set to ``texts``; a slot's unused room is zero-filled."""
    if len(texts) != len(SLOTS):
        raise ValueError(f"main.dol has {len(SLOTS)} strings, not {len(texts)}")
    out = bytearray(raw)
    for (offset, end, kind, what), text, old in zip(SLOTS, texts, strings(raw)):
        if text == old:
            continue
        text = text.replace("\r\n", "\n")
        data = text.encode("utf-16-be") if kind == "utf16" else text.replace("{CR}", "\r").encode("cp932")
        data += _end_mark(kind)
        if len(data) > end - offset:
            raise ValueError(f"main.dol, {what}: {len(data)} bytes, the slot has {end - offset}")
        out[offset:end] = data + bytes(end - offset - len(data))
    return bytes(out)
