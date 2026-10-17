"""Fixed-field text in the battle, system and credit archives (BTL/*.AFS, WINDOW/END_DATA.AFS): names, descriptions, help.

These entries hold no message markers. Their text is printable ASCII in fixed fields padded with spaces, read
by the game at a fixed place. A text slot is one run of printable bytes with at least three letters in a row
(magic words such as ``PVRT`` are not text). Its *budget* is the run's length: the leading spaces stay where
they are, the text starts after them and may fill the rest of the budget, padded with spaces. A longer text
is refused, so no edit moves a byte of the table or runs into the next field. Bytes outside the runs stay as
they are, so an unchanged entry is byte-exact.
"""
from __future__ import annotations

import re
from typing import List, Sequence, Set, Tuple

RUN = re.compile(rb"[\x20-\x7e]{3,}")
WORD = re.compile(rb"[A-Za-z][A-Za-z'\-]*[.!?:,]?")     # a word: letters, an apostrophe or hyphen, closing punctuation
NUMBER = re.compile(rb"[+\-]?\d+%?")                    # a stat in a description: +50, 10%
VOWELS = frozenset(b"aeiouyAEIOUY")
LEAD = re.compile(rb"[A-Za-z0-9+]")                     # the first byte of a text (bytes before it are kept)


ABBREVIATION = re.compile(rb"[A-Z]{2,3}")   # HP, MP, SP: accepted inside a phrase only
FUNCTION_WORDS = frozenset(b"to of a an in on at by or and is it no up if be my me we so do go".split())


def _word_ok(core: bytes, phrase: bool) -> bool:
    """A word, judged by its letters: all capitals (five or more with a vowel; two or three in a phrase), capitalised
    (a lowercase vowel after the first letter), or all lowercase (four or more with a vowel); at least three distinct
    letters. Mixed capitals (``uCpt``, ``hAF``) fail."""
    if phrase and (core.lower() in FUNCTION_WORDS or ABBREVIATION.fullmatch(core)):
        return True
    if len(set(core.lower())) < 3 or len(core) > 20:
        return False
    if core.isupper():
        return len(core) >= 5 and any(c in VOWELS for c in core)
    if core[:1].isupper() and core[1:].islower():
        return any(c in VOWELS for c in core[1:])
    if core.islower():
        return len(core) >= 4 and any(c in VOWELS for c in core)
    return False


def _is_text(run: bytes) -> bool:
    """True when every space-separated token is a word or a number, and at least one token is a word. One word
    alone needs four letters (three-letter fragments are common in binary tables). Random bytes fail this:
    ``NJCM``, ``kqt``, ``AAAA``, ``fff?``, ``uCpt``, ``Acd``, ``AUE``."""
    tokens = run.split()
    if not tokens:
        return False
    phrase = len(tokens) > 1
    words = 0
    for token in tokens:
        if NUMBER.fullmatch(token):
            continue
        if not WORD.fullmatch(token):
            return False
        core = re.sub(rb"[^A-Za-z]", b"", token)
        if len(token) > 24 or not _word_ok(core, phrase):
            return False
        words += 1
    if phrase:
        return words > 0
    return words == 1 and len(re.sub(rb"[^A-Za-z]", b"", tokens[0])) >= 4


MAGIC_WORDS = {b"PVRT", b"GBIX", b"PVPL", b"PVMH", b"AFS", b"DSTH", b"BGDD", b"L62C", b"SFD"}


class Slot:
    """One text slot: its offset in the entry, its budget (bytes), and its text."""

    __slots__ = ("start", "budget", "lead", "text")

    def __init__(self, start: int, budget: int, lead: int, text: str) -> None:
        self.start = start
        self.budget = budget
        self.lead = lead
        self.text = text


def slots(blob: bytes) -> List[Slot]:
    """The text slots of one entry, in order."""
    out = []
    for match in RUN.finditer(blob):
        run = match.group(0)
        first = LEAD.search(run)              # bytes before the first letter or digit stay as they are
        if first is None:
            continue
        text = run[first.start():].rstrip(b" ")
        if text in MAGIC_WORDS or not _is_text(text):
            continue
        out.append(Slot(match.start(), len(run), first.start(), text.decode("ascii")))
    return out


def fit(slot: Slot, text: str) -> bytes:
    """The bytes that replace a slot's text (the room after its lead bytes): the text, padded with spaces.

    Raises ValueError when the text is longer than the slot's room or is not printable ASCII.
    """
    room = slot.budget - slot.lead
    if any(not (0x20 <= ord(c) < 0x7F) for c in text):
        raise ValueError(f"not printable ASCII: {text!r}")
    data = text.strip(" ").encode("ascii")
    if len(data) > room:
        raise ValueError(f"text of {len(data)} bytes does not fit the {room}-byte field: {text!r}")
    return data + b" " * (room - len(data))


def write(blob: bytes, texts: Sequence[str], slot_list: Sequence[Slot]) -> Tuple[bytes, Set[int]]:
    """The entry with each slot's text replaced by ``texts`` (same order as ``slot_list``).

    Returns the new entry and the indexes of slots whose text was refused (those keep their original bytes).
    """
    out = bytearray(blob)
    refused: Set[int] = set()
    for index, (slot, text) in enumerate(zip(slot_list, texts)):
        if text == slot.text:
            continue
        try:
            new = fit(slot, text)
        except ValueError:
            refused.add(index)
            continue
        if not _is_text(new.strip(b" ")):   # the editor would not find this slot again after the save: keep the original
            refused.add(index)
            continue
        out[slot.start + slot.lead:slot.start + slot.budget] = new
    return bytes(out), refused


def has_messages(data: bytes) -> bool:
    """True when an archive holds message records (MAP archives): those are read by ``archive``."""
    from core.containers import afs
    try:
        entries = afs.parse(data)
    except afs.AfsError:
        return False
    return any(e.size and text_marker(data[e.offset:e.offset + e.size]) for e in entries)


def text_marker(blob: bytes) -> bool:
    return b"\x17\x00\x02" in blob


def archive_blocks(data: bytes) -> Tuple[List[str], dict]:
    """The field texts of an AFS archive, entry by entry, with a name per text (its entry and its place there)."""
    from core.containers import afs
    texts: List[str] = []
    names = {}
    for entry in afs.parse(data):
        if not entry.size:
            continue
        for k, slot in enumerate(slots(data[entry.offset:entry.offset + entry.size])):
            names[str(len(texts))] = f"entry {entry.index} field {k}"
            texts.append(slot.text)
    return texts, names


def archive_build(data: bytes, texts: Sequence[str]) -> Tuple[bytes, Set[int], int]:
    """The archive with ``texts`` (in the order of ``archive_blocks``). Returns (bytes, refused text indexes, count)."""
    from core.containers import afs
    replacements = {}
    refused: Set[int] = set()
    wanted = 0
    for entry in afs.parse(data):
        if not entry.size:
            continue
        blob = data[entry.offset:entry.offset + entry.size]
        found = slots(blob)
        if not found:
            continue
        mine = list(texts[wanted:wanted + len(found)])
        new_blob, bad = write(blob, mine, found)
        refused |= {wanted + i for i in bad}
        if new_blob != blob:
            replacements[entry.index] = new_blob
        wanted += len(found)
    out = afs.write(data, replacements) if replacements else bytes(data)
    return out, refused, wanted
