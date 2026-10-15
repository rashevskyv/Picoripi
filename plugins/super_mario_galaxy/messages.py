"""Super Mario Galaxy 1 and 2 message archives, read and written by message label, on every version.

A message archive is a RARC (Wii) or CRAR (Switch: the same layout little-endian) in ``MessageData``. Two kinds:

* Super Mario Galaxy: ``message.bmg`` (JSystem BMG, UTF-16: INF1, DAT1, FLW1) and ``messageid.tbl`` (BCSV:
  ``MessageId``, ``Index``), which names each message; the game looks a message up by that name. An archive without
  the table (the Switch ``System.arc``) is labelled by number (``#0``...).
* Super Mario Galaxy 2: one archive per zone with ``<name>.msbt`` members (LMS ``MsgStdBn``: LBL1 labels, TXT2);
  a message's key is ``<member>/<label>``. ``.msbf`` flows are kept as they are.

The Switch writes the same files little-endian: the BMG and LMS section magics are byte-swapped words (``GSEM1gmb``,
``1FNI``, ``1LBL``), the text is UTF-16LE, and tag fields are swapped: a BMG tag's u16 number and the numbers of the
groups in ``SWAPPED_WIDTH``; every u16 of an LMS tag's parameters (measured on SMG2: all 1,600 tags of the English
files that line up). Editor text shows a tag with the bytes the Wii file has, on every version:
``{escape:<group>:<hex>}`` (BMG) or ``{tag:<group>:<type>:<hex>}`` and ``{/tag:<group>:<type>}`` (LMS). The button
pictures (group 3) are numbered differently on the Switch; ``picture_pairs`` reads the pairs from the English text
of both versions, message by message, so a build can swap them.
"""
from __future__ import annotations

import json
import re
import struct
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import Dict, Iterable, List, Optional, Tuple

from core.containers.rarc_container import RarcContainer
from plugins.common.msbt import EndTag, Msbt, Tag
from plugins.zelda_bmg.bmg_tool import BMGFile

from . import bcsv

BMG_NAME = "message.bmg"
TABLE_NAME = "messageid.tbl"
LE_MAGIC = b"GSEM1gmb"
LMS_SECTIONS = (b"LBL1", b"ATR1", b"TXT2", b"TSY1", b"NLI1")
DOC_FORMAT = "picoripi-smg-messages"
TAG_RE = re.compile(r"\{(?:escape:(\d+):([0-9a-fA-F]*)|tag:(\d+):(\d+):([0-9a-fA-F]*)|/tag:(\d+):(\d+))\}")
PICTURE = 3
# The width of the numbers after a BMG tag's u16 number, by tag group, where the Switch release swaps them. Measured by
# comparing every tag of the SMG1 Wii and Switch English files message by message: group 1 (wait frames) holds u16
# values, groups 6 and 7 (number and string arguments) u32 values. Every other group keeps its bytes (a colour or a
# name form is one byte and a pad; a sound name stays big-endian UTF-16).
SWAPPED_WIDTH = {1: 2, 6: 4, 7: 4}


def _swap(data: bytes, width: int) -> bytes:
    whole = len(data) // width * width
    return b"".join(data[i:i + width][::-1] for i in range(0, whole, width)) + data[whole:]


def archive_little(data: bytes) -> bool:
    """True for a Switch archive (CRAR)."""
    return RarcContainer(data).little_endian


# -- BMG (Super Mario Galaxy) -----------------------------------------------------------------------------------------

def _swap_magics(data: bytes) -> bytes:
    """``data`` with the file magic and each section magic reversed word by word (Switch BMG <-> Wii BMG). Sections
    are walked by their little-endian sizes, which the swap does not touch."""
    out = bytearray(data)
    out[0:4], out[4:8] = out[0:4][::-1], out[4:8][::-1]
    at = 0x20
    while at + 8 <= len(out):
        size = struct.unpack_from("<I", out, at + 4)[0]
        if size < 8 or at + size > len(out):
            break
        out[at:at + 4] = out[at:at + 4][::-1]
        at += size
    return bytes(out)


def load_bmg(data: bytes) -> BMGFile:
    """A BMG of either version; ``bmg.switch_magic`` marks the Switch form so ``save_bmg`` writes it back."""
    switch = data[:8] == LE_MAGIC
    bmg = BMGFile()
    bmg.load(_swap_magics(data) if switch else data)
    bmg.switch_magic = switch
    bmg.loaded_size = len(data)
    return bmg


def save_bmg(bmg: BMGFile) -> bytes:
    """The BMG bytes. The header's size field (on the disc it leaves out FLW1) moves by as much as the file grew."""
    data = bytearray(bmg.save())
    total = bmg.original_total_size + len(data) - bmg.loaded_size
    struct.pack_into(bmg.endianness + "I", data, 8, total)
    return _swap_magics(bytes(data)) if bmg.switch_magic else bytes(data)


def canonical_tag(group: int, data_hex: str, little: bool) -> str:
    """A BMG tag's bytes as the Wii file has them. For a Switch tag the u16 tag number and the numbers of the groups
    in ``SWAPPED_WIDTH`` are byte-swapped; the swap is its own inverse, so it also turns a Wii tag into a Switch one."""
    raw = bytes.fromhex(data_hex)
    if not little or len(raw) < 2:
        return data_hex.lower()
    width = SWAPPED_WIDTH.get(group)
    return (raw[1::-1] + (_swap(raw[2:], width) if width else raw[2:])).hex()


def labels(archive: RarcContainer, count: int) -> Dict[str, int]:
    """``{label: message index}`` from the archive's messageid.tbl (the empty first label is left out). An archive
    without the table (the Switch ``System.arc``: the game reads it by number) labels each message ``#<number>``."""
    if TABLE_NAME not in archive.list_files():
        return {f"#{index}": index for index in range(count)}
    rows = bcsv.read_rows(archive.read_file(TABLE_NAME), ["MessageId", "Index"])
    return {str(row["MessageId"]): int(row["Index"]) for row in rows if row.get("MessageId")}


def message_text(bmg: BMGFile, index: int) -> str:
    """One BMG message as editor text, tags in the Wii byte order."""
    little = bmg.endianness == "<"
    out = []
    for part in bmg.messages[index].parts:
        if isinstance(part, str):
            out.append(part)
        else:
            group = part["escape_type"]
            out.append(f"{{escape:{group}:{canonical_tag(group, part['data'], little)}}}")
    return "".join(out)


def parse_text(text: str, little: bool) -> list:
    """Editor text back to BMG parts; each tag is written in the byte order of the target file."""
    parts: list = []
    pos = 0
    for match in TAG_RE.finditer(text):
        if match.group(1) is None:
            continue   # an LMS tag has no meaning in a BMG: it stays text
        if match.start() > pos:
            parts.append(text[pos:match.start()])
        group = int(match.group(1))
        parts.append({"type": "escape", "escape_type": group, "data": canonical_tag(group, match.group(2), little)})
        pos = match.end()
    if pos < len(text):
        parts.append(text[pos:])
    return parts


def read_archive(data: bytes) -> Tuple[RarcContainer, BMGFile, Dict[str, int]]:
    archive = RarcContainer(data)
    bmg = load_bmg(archive.read_file(BMG_NAME))
    return archive, bmg, labels(archive, len(bmg.messages))


# -- LMS / MSBT (Super Mario Galaxy 2) --------------------------------------------------------------------------------

def _swap_lms_magics(data: bytes) -> bytes:
    """An MSBT with each section magic reversed (Switch <-> the form ``Msbt`` reads); sizes are little-endian."""
    out = bytearray(data)
    at = 0x20
    while at + 16 <= len(out):
        size = struct.unpack_from("<I", out, at + 4)[0]
        out[at:at + 4] = out[at:at + 4][::-1]
        at += 16 + size
        at += -at % 16
    return bytes(out)


def load_msbt(data: bytes) -> Tuple[Msbt, bool]:
    """``(Msbt, switch form)``: a Switch MSBT is read with its section magics turned the right way first."""
    switch = data[8:10] == b"\xff\xfe" and data[0x20:0x24][::-1] in LMS_SECTIONS
    return Msbt(_swap_lms_magics(data) if switch else data), switch


def lms_text(tokens: list, little: bool) -> str:
    out = []
    for token in tokens:
        if isinstance(token, str):
            out.append(token)
        elif isinstance(token, Tag):
            params = _swap(token.params, 2) if little else token.params
            out.append(f"{{tag:{token.group}:{token.type}:{params.hex()}}}")
        else:
            out.append(f"{{/tag:{token.group}:{token.type}}}")
    return "".join(out)


def lms_tokens(text: str, little: bool) -> list:
    tokens: list = []
    pos = 0
    for match in TAG_RE.finditer(text):
        if match.group(1) is not None:
            continue   # a BMG tag has no meaning in an MSBT: it stays text
        if match.start() > pos:
            tokens.append(text[pos:match.start()])
        if match.group(3) is not None:
            params = bytes.fromhex(match.group(5))
            tokens.append(Tag(int(match.group(3)), int(match.group(4)), _swap(params, 2) if little else params))
        else:
            tokens.append(EndTag(int(match.group(6)), int(match.group(7))))
        pos = match.end()
    if pos < len(text):
        tokens.append(text[pos:])
    return tokens


def _msbt_members(archive: RarcContainer) -> List[str]:
    return [name for name in archive.list_files() if name.lower().endswith(".msbt")]


# -- either kind ------------------------------------------------------------------------------------------------------

def texts_by_label(data: bytes) -> Dict[str, str]:
    """``{key: text}`` of a message archive (Yaz0 or plain, Wii or Switch), in message order. The key is the label
    (BMG) or ``<member>/<label>`` (MSBT)."""
    archive = RarcContainer(data)
    members = _msbt_members(archive)
    if not members and BMG_NAME not in archive.list_files():
        return {}   # an archive with no messages (only a flow, or empty)
    if not members:
        _archive, bmg, names = read_archive(data)
        ordered = sorted((index, label) for label, index in names.items() if index < len(bmg.messages))
        return {label: message_text(bmg, index) for index, label in ordered}
    out: Dict[str, str] = {}
    for member in members:
        msbt, _switch = load_msbt(archive.read_file(member))
        stem = PurePosixPath(member).stem
        for index, tokens in enumerate(msbt.messages):
            out[f"{stem}/{msbt.labels.get(index, f'#{index}')}"] = lms_text(tokens, msbt.little)
    return out


def apply_texts(data: bytes, texts: Dict[str, str]) -> bytes:
    """The archive ``data`` with each message whose key is in ``texts`` replaced (the archive keeps its Yaz0 wrapper
    and byte order). Keys this archive does not have are ignored."""
    archive = RarcContainer(data)
    members = _msbt_members(archive)
    if not members and BMG_NAME not in archive.list_files():
        return data
    if not members:
        archive, bmg, names = read_archive(data)
        little = bmg.endianness == "<"
        for label, text in texts.items():
            index = names.get(label)
            if index is not None and index < len(bmg.messages):
                bmg.messages[index].parts = parse_text(text, little)
                bmg.messages[index].is_null = False
        archive.write_file(BMG_NAME, save_bmg(bmg))
        return archive.pack()
    for member in members:
        msbt, switch = load_msbt(archive.read_file(member))
        stem = PurePosixPath(member).stem
        keys = [f"{stem}/{msbt.labels.get(index, f'#{index}')}" for index in range(len(msbt.messages))]
        if not any(key in texts for key in keys):
            continue
        new = [lms_tokens(texts[key], msbt.little) if key in texts else tokens
               for key, tokens in zip(keys, msbt.messages)]
        built = msbt.build(new)
        archive.write_file(member, _swap_lms_magics(built) if switch else built)
    return archive.pack()


# -- button pictures --------------------------------------------------------------------------------------------------

def _is_picture(match: re.Match) -> bool:
    group = match.group(1) or match.group(3)
    return group is not None and int(group) == PICTURE


def pictures(text: str) -> List[str]:
    return [match.group(0) for match in TAG_RE.finditer(text) if _is_picture(match)]


def picture_pairs(wii: Dict[str, str], switch: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    """``{label: {Wii picture tag: Switch picture tag}}`` from the English text of both versions, plus ``"*"``: the
    most common pair of each Wii tag, for a label whose English pictures do not line up one to one."""
    per_label: Dict[str, Dict[str, str]] = {}
    votes: Dict[str, Counter] = defaultdict(Counter)
    for label, wii_text in wii.items():
        a, b = pictures(wii_text), pictures(switch.get(label, ""))
        if not a or len(a) != len(b):
            continue
        pairs = dict(zip(a, b))
        per_label[label] = pairs
        for old, new in pairs.items():
            votes[old][new] += 1
    per_label["*"] = {old: counter.most_common(1)[0][0] for old, counter in votes.items()}
    return per_label


def swap_pictures(text: str, label: str, pairs: Dict[str, Dict[str, str]], reverse: bool = False) -> str:
    """``text`` with its picture tags moved to the other version (Wii -> Switch, or back with ``reverse``)."""
    table = dict(pairs.get("*", {}))
    table.update(pairs.get(label, {}))
    if reverse:
        table = {new: old for old, new in reversed(list(table.items()))}
    return TAG_RE.sub(lambda match: table.get(match.group(0), match.group(0)) if _is_picture(match)
                      else match.group(0), text)


# -- the project document (one row per label) -------------------------------------------------------------------------

def make_document(rows: Iterable[Dict[str, object]]) -> bytes:
    """The ``.smgmsg`` file: UTF-8 JSON, one row per label: ``{"label", "text", "in": [version ids]}``."""
    return json.dumps({"format": DOC_FORMAT, "version": 1, "messages": list(rows)},
                      ensure_ascii=False, indent=1).encode("utf-8")


def read_document(data: bytes) -> Optional[List[Dict[str, object]]]:
    """The rows of a ``.smgmsg`` file, or None when ``data`` is not one."""
    try:
        doc = json.loads(bytes(data).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("format") != DOC_FORMAT or not isinstance(doc.get("messages"), list):
        return None
    return [row for row in doc["messages"] if isinstance(row, dict) and isinstance(row.get("label"), str)]


def union_rows(versions: List[Tuple[str, Dict[str, str]]]) -> List[Dict[str, object]]:
    """One row per label over every version: the first version's order and text, then the labels only a later
    version has, in its order. ``in`` lists the versions that have the label."""
    rows: Dict[str, Dict[str, object]] = {}
    for version, texts in versions:
        for label, text in texts.items():
            row = rows.setdefault(label, {"label": label, "text": text, "in": []})
            row["in"].append(version)
    return list(rows.values())
