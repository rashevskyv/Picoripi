"""GCX scripts of The Twin Snakes: the string table, which strings are English, who says them.

A GCX file (``scenerio.gcx`` of a stage in stage.dat; each of the 234 sections of codec.dat is
one too) starts with a u32 build stamp, then ``(hash, offset)`` pairs up to ``(0, 0)``, then the
resource table, then the script. The resource table is little-endian::

    u32 size, u32 0x10, u32 table_end, u32 data_end, u32 entry[(table_end - 0x10) / 4], data...

``entry`` is ``0x80000000 | offset`` for a string (NUL-terminated, at ``table_end + offset``) and
a plain offset for a binary resource. Strings come first, packed and in table order; binary
resources follow. The script refers to a string only by its index (``6D 0E <u32 index>``), so
strings can be rewritten freely inside the string area as long as the area keeps its size.

Every table holds the same text in six languages, one run per language in the order English,
French, German, Italian, Spanish, Japanese; a table may repeat that cycle per conversation. Only
the English strings are shown in the US game. They are found by language detection
(``segment``); a save may take room from the French-to-Spanish strings when the English text
grows (``TextTable.build``) -- never from English or Japanese.

A codec line is ``talk`` (``13 EB 91 3B``) with the speaker as the 24-bit name hash of the
character (``09 06 <hash>``) and the string index after it.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

STRING_FLAG = 0x80000000
LANGS = "EFGISJ"
ENGLISH = 0

_STOPWORDS = {
    "E": set("the you to and is of it that what this be your for are have on with can".split()),
    "F": set("le la les de des tu vous est et un une que pas il je ce en du qui au".split()),
    "G": set("der die das und ist du sie nicht ein eine ich es zu den mit auf wir was".split()),
    "I": set("il la che di e non un una per sono ti hai del le si mi ci".split()),
    "S": set("el la que de y no es un una se por lo los las usted ha me con".split()),
}
_WORD_RE = re.compile(r"[a-z']+")
# talk: speaker hash, then (after the face) the 24-bit string index
_TALK_RE = re.compile(rb"\x13\xeb\x91\x3b\x09\x06(...)\x06...(?:.{0,6}?)\x6d\x0e(...)", re.S)
# the voice clip a run of talk lines plays; the same clip id is used by every language's copy
_VOICE_RE = re.compile(rb"\x0a(..)\x00\x00\x01(.).\x8d", re.S)


class FormatError(ValueError):
    """Not a GCX resource table this plugin understands."""


def strcode24(name: str) -> int:
    """The engine's 24-bit name hash (MGS2 ``StrCode``): speakers, file names."""
    value = 0
    for byte in name.encode("ascii"):
        value = ((value << 5) | (value >> 19)) & 0xFFFFFF
        value = (value + byte) & 0xFFFFFF
    return value or 1


# -- language of a string ----------------------------------------------------------------


def language_of(raw: bytes) -> str:
    """``E``/``F``/``G``/``I``/``S``/``J`` or ``?`` (too short to tell)."""
    high = sum(1 for b in raw if b >= 0x80)
    if high * 4 > len(raw):      # two-byte codes; an accent escape is 1F + a byte below 0x81
        return "J"
    words = _WORD_RE.findall(raw.decode("latin-1").lower())
    best, score = "?", 0
    for lang, stop in _STOPWORDS.items():
        hits = sum(1 for word in words if word in stop)
        if hits > score:
            best, score = lang, hits
    if best == "E" and b"\x1f" in raw:      # English never needs an accent
        return "?"
    return best


def segment(strings: Sequence[Optional[bytes]]) -> List[int]:
    """Language index (0 English .. 4 Spanish, 5 Japanese) of every entry; -1 for binary ones.

    Japanese strings are certain (two-byte codes). Between Japanese runs lie the five European
    copies of the same lines. Their runs usually have equal length, which settles the split
    when the votes of the strings do not contradict it; otherwise the split with the best votes
    wins (each string votes for its language by stopwords). Voice clips correct both later
    (``apply_clips``).
    """
    labels = [language_of(raw) if raw is not None else "B" for raw in strings]
    result = [-1 if label == "B" else 5 for label in labels]
    chunks: List[List[int]] = []
    chunk: List[int] = []
    for index, label in enumerate(labels):
        if label == "B":
            continue
        if label != "J":
            chunk.append(index)
        elif chunk:
            chunks.append(chunk)
            chunk = []
    if chunk:
        chunks.append(chunk)
    for number, chunk in enumerate(chunks):
        inside_japanese = chunk[0] > 0 and labels[chunk[0] - 1] == "J" and chunk[-1] + 1 < len(labels) \
            and labels[chunk[-1] + 1] == "J"
        if inside_japanese and len(chunk) < 5 and not any(labels[i] in "EFGIS" for i in chunk):
            continue            # "..." inside a Japanese run is Japanese
        owner = _split_european([labels[i] for i in chunk], [_plain(strings[i]) for i in chunk])
        for index, lang in zip(chunk, owner):
            result[index] = lang
    return result


def _split_european(labels: List[str], plain: List[bool]) -> List[int]:
    """The European language (0..4) of each string of one stretch between Japanese runs.

    Five equal runs in the usual order win when the votes allow it. Otherwise the runs follow
    the votes (a change of language costs a penalty, so one misread string does not make a
    run); the order then does not matter -- some menus list English, Japanese, German, French...
    Unreadable plain strings ("Snake!") next to an English run join it: a foreign line shown to
    the translator costs nothing, an English line hidden from him stays English in the game.
    """
    count = len(labels)

    def score(owner: List[int]) -> int:
        return sum(1 if label == LANGS[lang] else (-1 if label in LANGS else 0)
                   for label, lang in zip(labels, owner))

    votes = [label for label in labels if label in LANGS]
    if votes and votes.count("E") * 5 >= len(votes) * 4:
        return [0] * count          # an English-only stretch (some menus have one per language)
    ordered = _ordered_runs(labels)
    if count % 5 == 0:
        equal = [i * 5 // count for i in range(count)]
        if score(equal) >= score(ordered) - 1:
            return equal
    voted = _vote_runs(labels)
    owner = ordered if score(ordered) >= score(voted) - 2 else list(voted)
    for i in range(count):
        if owner[i] != 0 and labels[i] == "?" and plain[i]:
            left = next((owner[j] for j in range(i - 1, -1, -1) if labels[j] != "?"), None)
            right = next((owner[j] for j in range(i + 1, count) if labels[j] != "?"), None)
            if 0 in (left, right):
                owner[i] = 0
    return owner


def _ordered_runs(labels: List[str]) -> List[int]:
    """Best language per string when the runs come in the usual order English .. Spanish."""
    count = len(labels)
    neg = float("-inf")
    best = [0.0] + [neg] * 4
    back: List[List[int]] = []
    for label in labels:
        row, new = [], []
        for state in range(5):
            prev = max(range(state + 1), key=lambda s: best[s])
            row.append(prev)
            vote = 1.0 if label == LANGS[state] else (-1.0 if label in LANGS else 0.0)
            new.append(best[prev] - 0.25 * (state - prev) + vote)    # unread strings stay early
        back.append(row)
        best = new
    state = max(range(5), key=lambda s: best[s])
    owner = [0] * count
    for i in range(count - 1, -1, -1):
        owner[i] = state
        state = back[i][state]
    return owner


def _vote_runs(labels: List[str], switch: float = 2.5) -> List[int]:
    """Most likely language per string when languages come in runs (a 5-state Viterbi path)."""
    count = len(labels)
    if not count:
        return []
    states = range(5)

    def vote(label: str, state: int) -> float:
        return 1.0 if label == LANGS[state] else (-1.0 if label in LANGS else 0.0)

    best = [vote(labels[0], s) - (0.0 if s == 0 else 0.5) for s in states]
    back: List[List[int]] = []
    for label in labels[1:]:
        top = max(states, key=lambda s: best[s])
        row, new = [], []
        for state in states:
            stay, move = best[state], best[top] - switch
            if move > stay:
                row.append(top)
                new.append(move + vote(label, state))
            else:
                row.append(state)
                new.append(stay + vote(label, state))
        back.append(row)
        best = new
    state = max(states, key=lambda s: best[s])
    owner = [0] * count
    for i in range(count - 1, -1, -1):
        owner[i] = state
        if i:
            state = back[i - 1][state]
    return owner


def _plain(raw: Optional[bytes]) -> bool:
    return raw is not None and all(b == 0x0A or 0x20 <= b < 0x7F for b in raw)


# -- the resource table --------------------------------------------------------------


@dataclass
class TextTable:
    """One resource table, read from ``data[offset:]``."""

    offset: int
    size: int
    table_end: int
    data_end: int
    entries: List[int]
    strings: List[Optional[bytes]]
    raw: bytes                       # the whole table, ``size`` bytes
    langs: List[int] = field(default_factory=list)

    @classmethod
    def read(cls, data: bytes, offset: int) -> "TextTable":
        if offset + 16 > len(data):
            raise FormatError("resource table outside the file")
        size, header, table_end, data_end = struct.unpack_from("<4I", data, offset)
        if header != 0x10 or table_end < 0x10 or (table_end - 0x10) % 4 or not table_end <= data_end <= size \
                or offset + size > len(data):
            raise FormatError(f"no resource table at {offset:#x}")
        count = (table_end - 0x10) // 4
        entries = list(struct.unpack_from(f"<{count}I", data, offset + 0x10))
        area = data[offset + table_end: offset + data_end]
        strings: List[Optional[bytes]] = []
        for entry in entries:
            if entry & STRING_FLAG:
                start = entry & ~STRING_FLAG
                end = area.find(b"\0", start)
                if end < 0:
                    raise FormatError(f"string {len(strings)} has no end")
                strings.append(bytes(area[start:end]))
            else:
                strings.append(None)
        return cls(offset, size, table_end, data_end, entries, strings, bytes(data[offset:offset + size]))

    @property
    def english(self) -> List[int]:
        """Indices of the English strings, in table order."""
        return [i for i, lang in enumerate(self.langs) if lang == ENGLISH]

    @property
    def string_capacity(self) -> int:
        """Bytes the strings may use: up to the first binary resource, else the whole data area."""
        binary = [entry for entry in self.entries if not entry & STRING_FLAG]
        return min(binary) if binary else self.data_end - self.table_end

    def build(self, changes: Dict[int, bytes]) -> bytes:
        """The table with ``changes`` (index -> new string bytes); same size as before.

        When the strings no longer fit, French-to-Spanish strings (most certainly foreign
        first) are pointed at one shared empty string until they do.
        """
        strings = list(self.strings)
        for index, value in changes.items():
            strings[index] = bytes(value)
        if strings == self.strings:
            return self.raw
        capacity = self.string_capacity
        shared_empty: set = set()
        order = self._reclaim_order()
        while True:
            body, offsets = self._pack(strings, shared_empty)
            if len(body) <= capacity:
                break
            if not order:
                raise FormatError(f"strings are {len(body) - capacity} bytes too long for this table")
            # free the biggest still-used foreign strings first: fewer lines lost
            take = order.pop(0)
            shared_empty.add(take)
        out = bytearray(self.raw)
        entries = list(self.entries)
        for index, offset in offsets.items():
            entries[index] = STRING_FLAG | offset
        struct.pack_into(f"<{len(entries)}I", out, 0x10, *entries)
        start = self.table_end
        out[start:start + capacity] = body + bytes(capacity - len(body))
        return bytes(out)

    def _reclaim_order(self) -> List[int]:
        foreign = [i for i, lang in enumerate(self.langs) if 1 <= lang <= 4 and self.strings[i]]
        sure = [i for i in foreign if language_of(self.strings[i]) == LANGS[self.langs[i]]]
        rest = [i for i in foreign if i not in set(sure)]
        size = lambda i: -len(self.strings[i] or b"")  # noqa: E731
        return sorted(sure, key=size) + sorted(rest, key=size)

    def _pack(self, strings: List[Optional[bytes]], shared_empty: set) -> Tuple[bytes, Dict[int, int]]:
        body = bytearray()
        offsets: Dict[int, int] = {}
        empty_at = None
        for index, value in enumerate(strings):
            if value is None:
                continue
            if index in shared_empty:
                if empty_at is None:
                    empty_at = len(body)
                    body += b"\0"
                offsets[index] = empty_at
                continue
            offsets[index] = len(body)
            body += value + b"\0"
        return bytes(body), offsets


# -- a whole GCX file or codec section --------------------------------------------------


def table_offset(data: bytes, start: int = 0) -> int:
    """Offset of the resource table of the GCX that starts at ``start`` (after its hash pairs)."""
    pos = start + 4
    while pos + 8 <= len(data):
        a, b = struct.unpack_from(">II", data, pos)
        pos += 8
        if a == 0 and b == 0:
            return pos
    raise FormatError("GCX hash table has no end")


@dataclass
class ScriptLines:
    """What the script says about the strings: speaker hashes, and lines of one voice clip."""

    speakers: Dict[int, int]
    clips: List[List[int]]          # string indices of one (clip, line number) across languages


def script_lines(script: bytes, count: int) -> ScriptLines:
    """Speakers and voice-clip groups of the ``talk`` commands of a script."""
    found: Dict[int, int] = {}
    voices = [(match.start(), match.group(1) + match.group(2)) for match in _VOICE_RE.finditer(script)]
    groups: Dict[Tuple[bytes, int], List[int]] = {}
    voice, line, next_voice = None, 0, 0
    for match in _TALK_RE.finditer(script):
        index = int.from_bytes(match.group(2), "little")
        if index >= count:
            continue
        found.setdefault(index, int.from_bytes(match.group(1), "little"))
        while next_voice < len(voices) and voices[next_voice][0] < match.start():
            voice, line, next_voice = voices[next_voice][1], 0, next_voice + 1
        if voice is not None:
            groups.setdefault((voice, line), []).append(index)
            line += 1
    return ScriptLines(found, [sorted(set(group)) for group in groups.values()])


def apply_clips(langs: List[int], strings: Sequence[Optional[bytes]], clips: Iterable[List[int]]) -> None:
    """Correct the detected languages with the voice clips: every language's copy of a voiced
    line plays the same clip, in the order English .. Japanese (the English copy may use a clip
    of its own, then five copies remain and the one before the first is English)."""
    for group in clips:
        if len(group) == 6:
            for lang, index in enumerate(group):
                langs[index] = lang
        elif len(group) == 5:
            steps = {b - a for a, b in zip(group, group[1:-1])}
            if language_of(strings[group[-1]] or b"") == "J":
                for lang, index in enumerate(group, start=1):
                    langs[index] = lang
                first = group[0] - (steps.pop() if len(steps) == 1 else 0)
                if first != group[0] and 0 <= first < len(langs) and strings[first] is not None:
                    langs[first] = 0
            else:
                for lang, index in enumerate(group):
                    langs[index] = lang


@dataclass
class Section:
    """One GCX inside a bigger file: where it starts and ends, its table and its speakers."""

    start: int
    end: int
    table: TextTable
    speakers: Dict[int, int]


def read_section(data: bytes, start: int, end: int, detect: bool = True) -> Section:
    """The GCX at ``data[start:end]`` with its speakers and (``detect``) its languages."""
    table = TextTable.read(data, table_offset(data, start))
    lines = script_lines(data[table.offset + table.size:end], len(table.strings))
    if detect:
        table.langs = segment(table.strings)
        apply_clips(table.langs, table.strings, lines.clips)
    return Section(start, end, table, lines.speakers)


def read_sections(data: bytes, segment: bool = True) -> List[Section]:
    """Every GCX in ``data`` (a codec.dat or a single scenerio.gcx), in file order; ``segment``
    detects the languages of the strings too."""
    starts = section_starts(data)
    return [read_section(data, start, starts[i + 1] if i + 1 < len(starts) else len(data), segment)
            for i, start in enumerate(starts)]


def read_sections_layout(data: bytes) -> List[Tuple[int, int, int]]:
    """``(start, table offset, string count)`` of every section: equal for a file and its translation."""
    out = []
    for start in section_starts(data):
        table = TextTable.read(data, table_offset(data, start))
        out.append((start, table.offset, len(table.strings)))
    return out


def section_starts(data: bytes) -> List[int]:
    """Where the GCX sections of ``data`` start.

    Sections are found by the build stamp the file starts with (the same in every section of
    one build) and must parse.
    """
    if len(data) < 8:
        raise FormatError("file too short for a GCX")
    stamp = bytes(data[:4])
    starts = [0]
    pos = 4
    while True:
        pos = data.find(stamp, pos)
        if pos < 0:
            break
        try:
            TextTable.read(data, table_offset(data, pos))
        except FormatError:
            pos += 1
            continue
        if pos > starts[-1]:
            starts.append(pos)
        pos += 4
    return starts


def rebuild(data: bytes, sections: Iterable[Section], changes: Dict[int, Dict[int, bytes]]) -> bytes:
    """``data`` with the string changes of each section (section number -> index -> bytes)."""
    out = bytearray(data)
    for number, section in enumerate(sections):
        if number in changes:
            table = section.table
            out[table.offset:table.offset + table.size] = table.build(changes[number])
    return bytes(out)
