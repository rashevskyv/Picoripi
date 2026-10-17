"""Grandia II MAP archives as editor blocks: one block per message, rebuilt into the same AFS archive.

``blocks(data)`` returns the message texts of one archive file in stream order, with a name per block (the
message ID and its entry). ``build(data, texts)`` writes the archive with the new texts. The archive keeps every
other byte: binary entries, headers, the table, and every message the editor did not change. A message the game
cannot store (a character with no glyph) is written with ``?`` and reported in ``missing``.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Set, Tuple

from core.containers import afs
from plugins.grandia import text


def _message_pieces(data: bytes) -> List[Tuple[int, List[bytes]]]:
    """(entry index, pieces) of every AFS entry that holds messages, in table order."""
    out = []
    for entry in afs.parse(data):
        if not entry.size:
            continue
        blob = data[entry.offset:entry.offset + entry.size]
        if text.MARK not in blob:
            continue
        out.append((entry.index, text.split(blob)))
    return out


def _text_pieces(data: bytes) -> List[Tuple[int, int, bytes, bytes]]:
    """(entry index, piece index, header, body) of every message record of the archive."""
    found = []
    for index, pieces in _message_pieces(data):
        for k, piece in enumerate(pieces):
            parts = text.message_parts(piece)
            if parts is not None:
                found.append((index, k, parts[0], parts[1]))
    return found


def blocks(data: bytes) -> Tuple[List[str], Dict[str, str]]:
    """The texts of the archive (editor text, one per message) and a name for each message."""
    texts, names = [], {}
    for index, _k, header, body in _text_pieces(data):
        names[str(len(texts))] = _name(index, header)
        texts.append(text.to_text(body))
    return texts, names


def build(data: bytes, texts: Sequence[str]) -> Tuple[bytes, Set[str]]:
    """The archive with ``texts`` as its messages (in the order of ``blocks``); (archive bytes, missing characters)."""
    pieces_by_entry = {index: pieces for index, pieces in _message_pieces(data)}
    missing: Set[str] = set()
    wanted = iter(texts)
    for index, k, header, _body in _text_pieces(data):
        new_text = next(wanted, None)
        if new_text is None:
            break
        body, bad = _encode(new_text)
        missing |= bad
        pieces_by_entry[index][k] = header + body
    replacements = {}
    for index, pieces in pieces_by_entry.items():
        replacements[index] = b"".join(pieces)
    entries = {entry.index: entry for entry in afs.parse(data)}
    changed = {index: blob for index, blob in replacements.items()
               if blob != data[entries[index].offset:entries[index].offset + entries[index].size]}
    return (afs.write(data, changed) if changed else bytes(data)), missing


def _encode(new_text: str) -> Tuple[bytes, Set[str]]:
    """Body bytes of editor text; a character with no glyph is written as ``?``."""
    try:
        return text.from_text(new_text), set()
    except ValueError:
        bad: Set[str] = set()
        out = []
        pos = 0
        for match in text.TAG_RE.finditer(new_text):
            out.append(_plain_or_question(new_text[pos:match.start()], bad))
            out.append(match.group(0))
            pos = match.end()
        out.append(_plain_or_question(new_text[pos:], bad))
        return text.from_text("".join(out)), bad


def _plain_or_question(chunk: str, bad: Set[str]) -> str:
    out = []
    for char in chunk:
        if 0x20 <= ord(char) < 0x7F and char not in "{}":
            out.append(char)
        else:
            bad.add(char)
            out.append("?")
    return "".join(out)


def _name(entry: int, header: bytes) -> str:
    """The name of a message: its entry and its ID (``08 <id>`` in the header, when the header has one)."""
    at = header.find(b"\x08", 3)
    if at >= 0 and at + 1 < len(header):
        return f"entry {entry} message {header[at + 1]:02X}"
    return f"entry {entry}"
