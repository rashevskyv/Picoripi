"""CFF (the outlines of an OpenType ``OTTO`` font) parsed into its parts and written back, plus the OpenType
rebuild around a changed CFF: character map, metrics, table directory and checksums.

``Cff`` reads the INDEXes and DICTs of a name-keyed or CID-keyed CFF; ``outline`` resolves a glyph's
charstring (subroutines, hints) to absolute contours and ``charstring`` writes contours back as a Type 2
charstring. ``rebuild_font`` puts a rebuilt CFF into the font. Used by the scalable-font backend
(``core.font_formats.bfotf``) to save edited glyphs and by the TotK tool that adds Ukrainian letters.
"""
from __future__ import annotations

import math
import struct
from typing import Dict, List, Optional, Tuple

Point = Tuple[float, float]
Contour = List[tuple]    # [("M", p), ("L", p), ("C", p1, p2, p3), ...]

# ---------------------------------------------------------------- CFF structures

def read_index(data: bytes, at: int) -> Tuple[List[bytes], int]:
    """``(items, offset after the INDEX)``."""
    count = struct.unpack_from(">H", data, at)[0]
    if count == 0:
        return [], at + 2
    size = data[at + 2]
    offsets = [int.from_bytes(data[at + 3 + i * size:at + 3 + (i + 1) * size], "big") for i in range(count + 1)]
    base = at + 2 + (count + 1) * size
    return [data[base + offsets[i]:base + offsets[i + 1]] for i in range(count)], base + offsets[-1]


def write_index(items: List[bytes]) -> bytes:
    if not items:
        return b"\x00\x00"
    offsets = [1]
    for item in items:
        offsets.append(offsets[-1] + len(item))
    size = next(n for n in (1, 2, 3, 4) if offsets[-1] < 1 << (8 * n))
    return (struct.pack(">HB", len(items), size) + b"".join(o.to_bytes(size, "big") for o in offsets)
            + b"".join(items))


def read_dict(data: bytes) -> List[Tuple[int, list]]:
    """``[(operator, operands)]``; two-byte operators are ``1200 + b1``."""
    out, operands, i = [], [], 0
    while i < len(data):
        b0 = data[i]
        if b0 <= 21:
            op = 1200 + data[i + 1] if b0 == 12 else b0
            i += 2 if b0 == 12 else 1
            out.append((op, operands))
            operands = []
        elif b0 == 28:
            operands.append(struct.unpack_from(">h", data, i + 1)[0])
            i += 3
        elif b0 == 29:
            operands.append(struct.unpack_from(">i", data, i + 1)[0])
            i += 5
        elif b0 == 30:
            text, i = "", i + 1
            while True:
                byte = data[i]
                i += 1
                done = False
                for nibble in (byte >> 4, byte & 15):
                    if nibble == 15:
                        done = True
                        break
                    text += "0123456789.EE?-"[nibble] + ("-" if nibble == 12 else "")
                if done:
                    break
            operands.append(float(text.replace("E-", "e-").replace("E", "e")))
        elif b0 <= 246:
            operands.append(b0 - 139)
            i += 1
        elif b0 <= 250:
            operands.append((b0 - 247) * 256 + data[i + 1] + 108)
            i += 2
        else:
            operands.append(-(b0 - 251) * 256 - data[i + 1] - 108)
            i += 2
    return out


def _dict_number(value) -> bytes:
    if isinstance(value, float) and not value.is_integer():
        text = repr(value).replace("e-", "c").replace("e+", "b").replace("e", "b")
        nibbles = ["0123456789.bc?-".index(ch) if ch in "0123456789.-" else {"b": 11, "c": 12}[ch] for ch in text]
        nibbles.append(15)
        if len(nibbles) % 2:
            nibbles.append(15)
        return b"\x1e" + bytes(nibbles[i] << 4 | nibbles[i + 1] for i in range(0, len(nibbles), 2))
    return b"\x1d" + struct.pack(">i", int(value))      # always 5 bytes: offsets keep their size


def write_dict(entries: List[Tuple[int, list]]) -> bytes:
    out = bytearray()
    for op, operands in entries:
        for value in operands:
            out += _dict_number(value)
        out += bytes([12, op - 1200]) if op >= 1200 else bytes([op])
    return bytes(out)


def _get(entries, op, default=None):
    return next((operands for o, operands in entries if o == op), default)


def _set(entries, op, operands):
    for index, (o, _old) in enumerate(entries):
        if o == op:
            entries[index] = (op, operands)
            return
    entries.append((op, operands))


class Cff:
    """A CFF table (name-keyed or CID-keyed) parsed into its parts, rebuildable with appended glyphs."""

    def __init__(self, data: bytes):
        self.data = data
        at = data[2]
        self.names, at = read_index(data, at)
        tops, at = read_index(data, at)
        self.strings, at = read_index(data, at)
        self.gsubrs, at = read_index(data, at)
        self.top = read_dict(tops[0])
        self.charstrings, _ = read_index(data, _get(self.top, 17)[0])
        self.count = len(self.charstrings)
        self.cid = _get(self.top, 1230) is not None
        self.charset = self._read_charset(_get(self.top, 15, [0])[0])
        if self.cid:
            fd_dicts, _ = read_index(data, _get(self.top, 1236)[0])
            self.fds = [read_dict(raw) for raw in fd_dicts]
            self.fdselect = self._read_fdselect(_get(self.top, 1237)[0])
        else:
            self.fds = [self.top]
            self.fdselect = [0] * self.count
        self.privates = []
        for fd in self.fds:
            size, offset = _get(fd, 18)
            private = read_dict(data[offset:offset + size])
            subrs_at = _get(private, 19)
            subrs = read_index(data, offset + subrs_at[0])[0] if subrs_at else []
            self.privates.append((private, subrs))

    def _read_charset(self, at: int) -> List[int]:
        if at == 0:
            return list(range(self.count))      # ISOAdobe: SID = GID for the first glyphs
        kind, ids, i = self.data[at], [0], at + 1
        while len(ids) < self.count:
            if kind == 0:
                ids.append(struct.unpack_from(">H", self.data, i)[0])
                i += 2
            else:
                first = struct.unpack_from(">H", self.data, i)[0]
                left = self.data[i + 2] if kind == 1 else struct.unpack_from(">H", self.data, i + 2)[0]
                i += 3 if kind == 1 else 4
                ids.extend(range(first, first + left + 1))
        return ids[:self.count]

    def _read_fdselect(self, at: int) -> List[int]:
        kind = self.data[at]
        if kind == 0:
            return list(self.data[at + 1:at + 1 + self.count])
        ranges = struct.unpack_from(">H", self.data, at + 1)[0]
        out = [0] * self.count
        for r in range(ranges):
            first, fd = struct.unpack_from(">HB", self.data, at + 3 + 3 * r)
            end = struct.unpack_from(">H", self.data, at + 3 + 3 * (r + 1))[0]
            out[first:end] = [fd] * (end - first)
        return out

    def widths_x(self, glyph: int) -> Tuple[float, float]:
        """``(defaultWidthX, nominalWidthX)`` of a glyph's private dict."""
        private = self.privates[self.fdselect[glyph]][0]
        return _get(private, 20, [0])[0], _get(private, 21, [0])[0]

    def add_glyph(self, charstring: bytes, name: str, like: int) -> int:
        """Append a glyph that uses the private dict (and FD) of glyph ``like``; returns its id."""
        self.charstrings.append(charstring)
        self.fdselect.append(self.fdselect[like])
        if self.cid:
            self.charset.append(max(self.charset) + 1)
        else:
            self.strings.append(name.encode("ascii"))
            self.charset.append(391 + len(self.strings) - 1)     # SIDs after the 391 standard strings
        self.count += 1
        return self.count - 1

    def build(self) -> bytes:
        top = list(self.top)
        for op in (15, 17, 1236, 1237):
            if _get(top, op) is not None or (op == 15):
                _set(top, op, [0])
        if not self.cid:
            _set(top, 18, [0, 0])
        if self.cid:     # CIDCount must cover the new CIDs
            _set(top, 1234, [max(_get(top, 1234, [8720])[0], max(self.charset) + 1)])
        header = self.data[:self.data[2]]

        def layout(top_entries):
            head = header + write_index(self.names) + write_index([write_dict(top_entries)])
            head += write_index(self.strings) + write_index(self.gsubrs)
            return head

        charset = b"\x00" + b"".join(struct.pack(">H", sid) for sid in self.charset[1:])
        fdselect = self._fdselect_bytes() if self.cid else b""
        charstrings = write_index(self.charstrings)
        # Private dicts + local subrs, each private followed by its subrs.
        private_blobs = []
        for private, subrs in self.privates:
            entries = [e for e in private if e[0] != 19]
            body = write_dict(entries + ([(19, [0])] if subrs else []))
            if subrs:
                body = write_dict(entries + [(19, [len(body)])])
            private_blobs.append((body, write_index(subrs) if subrs else b""))
        base = len(layout(top))     # stable: every offset is a 5-byte number
        charset_at = base
        fdselect_at = charset_at + len(charset)
        charstrings_at = fdselect_at + len(fdselect)
        cursor = charstrings_at + len(charstrings)
        fdarray = b""
        if self.cid:
            fd_entries = [list(fd) for fd in self.fds]
            for fd in fd_entries:
                _set(fd, 18, [0, 0])
            fdarray_len = len(write_index([write_dict(fd) for fd in fd_entries]))
            private_at = cursor + fdarray_len
            for fd, (body, subrs) in zip(fd_entries, private_blobs):
                _set(fd, 18, [len(body), private_at])
                private_at += len(body) + len(subrs)
            fdarray = write_index([write_dict(fd) for fd in fd_entries])
            _set(top, 1236, [cursor])
            _set(top, 1237, [fdselect_at])
            cursor += len(fdarray)
        else:
            body, _subrs = private_blobs[0]
            _set(top, 18, [len(body), cursor])
        _set(top, 15, [charset_at])
        _set(top, 17, [charstrings_at])
        head = layout(top)
        if len(head) != base:
            raise ValueError("CFF header changed size while laying out")
        privates = b"".join(body + subrs for body, subrs in private_blobs)
        return head + charset + fdselect + charstrings + fdarray + privates

    def _fdselect_bytes(self) -> bytes:
        ranges = []
        for glyph, fd in enumerate(self.fdselect):
            if not ranges or ranges[-1][1] != fd:
                ranges.append((glyph, fd))
        return (b"\x03" + struct.pack(">H", len(ranges)) + b"".join(struct.pack(">HB", g, fd) for g, fd in ranges)
                + struct.pack(">H", self.count))


# ---------------------------------------------------------------- charstrings

def _bias(subrs: List[bytes]) -> int:
    return 107 if len(subrs) < 1240 else 1131 if len(subrs) < 33900 else 32768


def outline(cff: Cff, glyph: int) -> Tuple[float, List[Contour]]:
    """``(advance width, contours)`` of a glyph, with every subroutine and hint resolved."""
    default_w, nominal_w = cff.widths_x(glyph)
    local = cff.privates[cff.fdselect[glyph]][1]
    state = {"x": 0.0, "y": 0.0, "hints": 0, "width": None, "contours": []}
    stack: List[float] = []

    def take_width(expected_even: bool):
        if state["width"] is None:
            odd = len(stack) % 2 == 1
            state["width"] = nominal_w + stack.pop(0) if (odd if expected_even else not odd) and stack else default_w

    def move(dx, dy):
        state["x"] += dx
        state["y"] += dy
        state["contours"].append([("M", (state["x"], state["y"]))])

    def line(dx, dy):
        state["x"] += dx
        state["y"] += dy
        state["contours"][-1].append(("L", (state["x"], state["y"])))

    def curve(a, b, c, d, e, f):
        x, y = state["x"], state["y"]
        p1 = (x + a, y + b)
        p2 = (p1[0] + c, p1[1] + d)
        p3 = (p2[0] + e, p2[1] + f)
        state["x"], state["y"] = p3
        state["contours"][-1].append(("C", p1, p2, p3))

    def run(code: bytes) -> bool:
        i = 0
        while i < len(code):
            b0 = code[i]
            if b0 >= 32 or b0 == 28 or b0 == 255:
                if b0 == 28:
                    stack.append(struct.unpack_from(">h", code, i + 1)[0])
                    i += 3
                elif b0 == 255:
                    stack.append(struct.unpack_from(">i", code, i + 1)[0] / 65536)
                    i += 5
                elif b0 <= 246:
                    stack.append(b0 - 139)
                    i += 1
                elif b0 <= 250:
                    stack.append((b0 - 247) * 256 + code[i + 1] + 108)
                    i += 2
                else:
                    stack.append(-(b0 - 251) * 256 - code[i + 1] - 108)
                    i += 2
                continue
            i += 1
            if b0 in (1, 3, 18, 23):                     # stems
                take_width(True)
                state["hints"] += len(stack) // 2
                stack.clear()
            elif b0 in (19, 20):                         # hintmask / cntrmask
                take_width(True)
                state["hints"] += len(stack) // 2
                stack.clear()
                i += (state["hints"] + 7) // 8
            elif b0 == 21:
                take_width(True)
                move(stack[-2], stack[-1])
                stack.clear()
            elif b0 in (22, 4):
                take_width(False)
                move(stack[-1], 0) if b0 == 22 else move(0, stack[-1])
                stack.clear()
            elif b0 == 5:
                for k in range(0, len(stack) - 1, 2):
                    line(stack[k], stack[k + 1])
                stack.clear()
            elif b0 in (6, 7):
                horizontal = b0 == 6
                for value in stack:
                    line(value, 0) if horizontal else line(0, value)
                    horizontal = not horizontal
                stack.clear()
            elif b0 == 8:
                for k in range(0, len(stack) - 5, 6):
                    curve(*stack[k:k + 6])
                stack.clear()
            elif b0 == 24:                               # rcurveline
                k = 0
                while len(stack) - k > 2:
                    curve(*stack[k:k + 6])
                    k += 6
                line(stack[k], stack[k + 1])
                stack.clear()
            elif b0 == 25:                               # rlinecurve
                k = 0
                while len(stack) - k > 6:
                    line(stack[k], stack[k + 1])
                    k += 2
                curve(*stack[k:k + 6])
                stack.clear()
            elif b0 in (26, 27):                         # vvcurveto / hhcurveto
                k, first = 0, 0.0
                if len(stack) % 2:
                    first, k = stack[0], 1
                while k + 3 < len(stack):
                    a, b, c, d = stack[k:k + 4]
                    if b0 == 26:
                        curve(first, a, b, c, 0, d)
                    else:
                        curve(a, first, b, c, d, 0)
                    first, k = 0.0, k + 4
                stack.clear()
            elif b0 in (30, 31):                         # vhcurveto / hvcurveto
                horizontal = b0 == 31
                k = 0
                while k + 3 < len(stack):
                    a, b, c, d = stack[k:k + 4]
                    last = stack[k + 4] if len(stack) - k == 5 else 0
                    if horizontal:
                        curve(a, 0, b, c, last, d)
                    else:
                        curve(0, a, b, c, d, last)
                    horizontal = not horizontal
                    k += 4
                stack.clear()
            elif b0 in (10, 29):                         # callsubr / callgsubr
                subrs = local if b0 == 10 else cff.gsubrs
                index = int(stack.pop()) + _bias(subrs)
                if run(subrs[index]):
                    return True
            elif b0 == 11:
                return False
            elif b0 == 14:
                take_width(True)
                stack.clear()
                return True
            elif b0 == 12:
                op = code[i]
                i += 1
                s = stack
                if op == 35:
                    curve(*s[0:6])
                    curve(*s[6:12])
                elif op == 34:
                    curve(s[0], 0, s[1], s[2], s[3], 0)
                    curve(s[4], 0, s[5], -s[2], s[6], 0)
                elif op == 36:
                    curve(s[0], s[1], s[2], s[3], s[4], 0)
                    curve(s[5], 0, s[6], s[7], s[8], -(s[1] + s[3] + s[7]))
                elif op == 37:
                    dx = sum(s[0:10:2])
                    dy = sum(s[1:10:2])
                    curve(*s[0:6])
                    if abs(dx) > abs(dy):
                        curve(s[6], s[7], s[8], s[9], s[10], -dy)
                    else:
                        curve(s[6], s[7], s[8], s[9], -dx, s[10])
                else:
                    raise ValueError(f"charstring operator 12 {op} is not supported")
                stack.clear()
            else:
                raise ValueError(f"charstring operator {b0} is not supported")
        return False

    run(cff.charstrings[glyph])
    width = state["width"] if state["width"] is not None else default_w
    return width, state["contours"]


def _cs_number(value: float) -> bytes:
    if float(value).is_integer() and -1131 <= value <= 1131:
        value = int(value)
        if -107 <= value <= 107:
            return bytes([value + 139])
        if value > 0:
            value -= 108
            return bytes([247 + (value >> 8), value & 0xFF])
        value = -value - 108
        return bytes([251 + (value >> 8), value & 0xFF])
    if float(value).is_integer() and -32768 <= value <= 32767:
        return b"\x1c" + struct.pack(">h", int(value))
    return b"\xff" + struct.pack(">i", round(value * 65536))


def charstring(width: float, widths_x: Tuple[float, float], contours: List[Contour]) -> bytes:
    """A Type 2 charstring of absolute contours (rmoveto / rlineto / rrcurveto, no hints).

    ``widths_x`` is ``(defaultWidthX, nominalWidthX)`` of the glyph's private dict.
    """
    default_width, nominal_width = widths_x
    out = bytearray(_cs_number(width - nominal_width)) if width != default_width else bytearray()
    x = y = 0.0
    for contour in contours:
        for segment in contour:
            kind, points = segment[0], segment[1:]
            deltas = []
            for px, py in points:
                deltas += [px - x, py - y]
                x, y = px, py
            out += b"".join(_cs_number(round(d, 4)) for d in deltas)
            out += {"M": b"\x15", "L": b"\x05", "C": b"\x08"}[kind]
    return bytes(out) + b"\x0e"


# ---------------------------------------------------------------- OpenType

def _checksum(data: bytes) -> int:
    data += b"\x00" * (-len(data) % 4)
    return sum(struct.unpack(f">{len(data) // 4}I", data)) & 0xFFFFFFFF


def _cmap_format4(mapping: Dict[int, int]) -> bytes:
    codes = sorted(c for c in mapping if c < 0xFFFF)
    runs: List[List[int]] = []
    for code in codes:
        if runs and code == runs[-1][-1] + 1:
            runs[-1].append(code)
        else:
            runs.append([code])
    runs.append([0xFFFF])
    segments = len(runs)
    ends, starts, deltas, ranges, glyph_array = [], [], [], [], []
    for index, run in enumerate(runs):
        starts.append(run[0])
        ends.append(run[-1])
        if run == [0xFFFF]:
            deltas.append(1)
            ranges.append(0)
            continue
        delta = (mapping[run[0]] - run[0]) & 0xFFFF
        if all((mapping[c] - c) & 0xFFFF == delta for c in run):
            deltas.append(delta)
            ranges.append(0)
        else:
            deltas.append(0)
            ranges.append(2 * (segments - index) + 2 * len(glyph_array))
            glyph_array += [mapping[c] for c in run]
    search = 2 ** int(math.log2(segments)) * 2
    body = struct.pack(">HHHH", segments * 2, search, int(math.log2(search // 2)), segments * 2 - search)
    body += struct.pack(f">{segments}H", *ends) + b"\x00\x00" + struct.pack(f">{segments}H", *starts)
    body += struct.pack(f">{segments}H", *deltas) + struct.pack(f">{segments}H", *ranges)
    body += struct.pack(f">{len(glyph_array)}H", *glyph_array)
    if len(body) + 6 > 0xFFFF:
        raise ValueError("the character map does not fit a format 4 subtable")
    return struct.pack(">HHH", 4, len(body) + 6, 0) + body


def _new_cmap(old: bytes, mapping: Dict[int, int]) -> bytes:
    """The cmap with every Unicode subtable rebuilt as format 4 from ``mapping``; others kept as they are."""
    count = struct.unpack_from(">H", old, 2)[0]
    records = [struct.unpack_from(">HHI", old, 4 + 8 * i) for i in range(count)]
    unicode = _cmap_format4(mapping)
    out_records = []
    for platform, encoding, offset in records:
        if (platform, encoding) in ((0, 3), (3, 1)):
            body = unicode
        else:
            kind = struct.unpack_from(">H", old, offset)[0]
            if kind == 14:
                length = struct.unpack_from(">I", old, offset + 2)[0]
            elif kind >= 8:
                length = struct.unpack_from(">I", old, offset + 4)[0]
            else:
                length = struct.unpack_from(">H", old, offset + 2)[0]
            body = old[offset:offset + length]
        out_records.append((platform, encoding, body))
    at = 4 + 8 * len(out_records)
    head, data, placed = struct.pack(">HH", 0, len(out_records)), b"", {}
    for platform, encoding, body in out_records:
        if body not in placed:
            placed[body] = at + len(data)
            data += body + b"\x00" * (-len(body) % 2)
        head += struct.pack(">HHI", platform, encoding, placed[body])
    return head + data


def rebuild_font(font: bytes, cff: Cff, mapping: Dict[int, int], new_metrics: List[Tuple[int, int]],
                 metrics: Optional[Dict[int, Tuple[int, int]]] = None) -> bytes:
    """The OpenType file with a new CFF, character map and metrics for ``new_metrics`` appended glyphs.

    ``metrics`` gives existing glyphs a new ``(advance, left side bearing)``."""
    from core.font_formats.bfotf import OpenType
    ot = OpenType(font)
    tables = {tag: font[offset:offset + length] for tag, (offset, length) in ot.tables.items()}
    old_count = ot.glyph_count
    total = old_count + len(new_metrics)
    tables["CFF "] = cff.build()
    tables["cmap"] = _new_cmap(tables["cmap"], mapping)
    long_count = ot.long_metrics
    hmtx = tables["hmtx"]
    advances = [struct.unpack_from(">H", hmtx, 4 * min(g, long_count - 1))[0] for g in range(old_count)]
    lsbs = [struct.unpack_from(">h", hmtx, 4 * g + 2)[0] if g < long_count
            else struct.unpack_from(">h", hmtx, 4 * long_count + 2 * (g - long_count))[0] for g in range(old_count)]
    for glyph, (advance, lsb) in (metrics or {}).items():
        advances[glyph], lsbs[glyph] = advance, lsb
    advances += [advance for advance, _lsb in new_metrics]
    lsbs += [lsb for _advance, lsb in new_metrics]
    tables["hmtx"] = b"".join(struct.pack(">Hh", a, b) for a, b in zip(advances, lsbs))
    hhea = bytearray(tables["hhea"])
    struct.pack_into(">H", hhea, 34, total)
    struct.pack_into(">H", hhea, 10, max(struct.unpack_from(">H", hhea, 10)[0], max(advances)))
    tables["hhea"] = bytes(hhea)
    maxp = bytearray(tables["maxp"])
    struct.pack_into(">H", maxp, 4, total)
    tables["maxp"] = bytes(maxp)
    if "vmtx" in tables and "vhea" in tables:
        long_v = struct.unpack_from(">H", tables["vhea"], 34)[0]
        tables["vmtx"] = tables["vmtx"][:4 * long_v + 2 * (old_count - long_v)] + b"\x00\x00" * len(new_metrics)
    if "post" in tables and struct.unpack_from(">I", tables["post"], 0)[0] == 0x00020000:
        raise ValueError("post format 2 (glyph names) is not supported")
    head = bytearray(tables["head"])
    struct.pack_into(">I", head, 8, 0)
    tables["head"] = bytes(head)
    tags = sorted(tables)
    count = len(tags)
    search = 2 ** int(math.log2(count)) * 16
    out = bytearray(font[:4] + struct.pack(">HHHH", count, search, int(math.log2(search // 16)), count * 16 - search))
    offset = 12 + 16 * count
    directory, body = bytearray(), bytearray()
    for tag in tags:
        data = tables[tag]
        directory += struct.pack(">4sIII", tag.encode("latin-1"), _checksum(data), offset + len(body), len(data))
        body += data + b"\x00" * (-len(data) % 4)
    out += directory + body
    head_at = offset + sum(len(tables[t]) + (-len(tables[t]) % 4) for t in tags[:tags.index("head")])
    struct.pack_into(">I", out, head_at + 8, (0xB1B0AFBA - _checksum(bytes(out))) & 0xFFFFFFFF)
    return bytes(out)
