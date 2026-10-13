"""Eternal Darkness (GameCube) ``*SK_ASC*`` files: the decoder.

The game reads ``*SK_ASC*`` and then one arithmetic-coded stream (16-bit range coder, Witten-Neal-Cleary
renormalisation, bits MSB first) of LZ77 tokens over a 31200-byte window:

  token kind   3-way adaptive choice per state (last two kinds): literal, match, end (freq 1)
  literal      adaptive tree of seen bytes + escape; escape -> tree of unseen bytes
               (removing a byte from it raises its neighbours +-8)
  match        distance class k (adaptive, 16 symbols, class k allowed once the window holds more than
               2^(k-1) bytes), distance 2^(k-1) + uniform; length code like the literal (64 symbols,
               neighbours +-4), codes >= 16 take 4 more uniform bits; copy length = code + 3

Decoded data starts with a big-endian u32: the size of the rest. Only the decoder is here; the models are
updated exactly as the encoder of the game's tools updates them.
"""
from __future__ import annotations

from typing import Callable, Optional

MAGIC = b"*SK_ASC*"
WIN = 31200
_CANCEL_EVERY = 1 << 16


class _Tree:
    """Binary-indexed frequency tree: node i = node 2i + node 2i+1, leaves n..2n-1."""

    def __init__(self, n: int, leaf: int) -> None:
        self.n = n
        self.t = [0] * n + [leaf] * n
        for i in range(n - 1, 0, -1):
            self.t[i] = self.t[2 * i] + self.t[2 * i + 1]

    def inc(self, sym: int, limit: int, by: int) -> None:
        t = self.t
        i = sym + self.n
        while i:
            t[i] += by
            i >>= 1
        if t[1] < limit:
            return
        n = self.n
        for i in range(n, 2 * n):
            if t[i] > 1:
                t[i] >>= 1
        for i in range(n - 1, 0, -1):
            t[i] = t[2 * i] + t[2 * i + 1]

    def remove(self, sym: int) -> None:
        t = self.t
        i = sym + self.n
        v = t[i]
        while i:
            t[i] -= v
            i >>= 1

    def find(self, target: int):
        """``(symbol, cumulative frequency below it)`` of the symbol that holds ``target``."""
        t, n = self.t, self.n
        node, acc = 2, 0
        while True:
            if acc + t[node] <= target:
                acc += t[node]
                node += 1
            if node >= n:
                return node - n, acc
            node <<= 1


class _Models:
    """Every adaptive model of the codec, updated the same way as the game's encoder."""

    def __init__(self) -> None:
        self.len_seen, self.len_new = _Tree(64, 0), _Tree(64, 1)
        self.lit_seen, self.lit_new = _Tree(256, 0), _Tree(256, 1)
        self.dist = _Tree(16, 0)
        self.dist.inc(0, 6000, 24)
        self.kind = [[40, 40] for _ in range(4)]
        self.esc_lit, self.esc_len = 1, 8
        self.next_limit, self.next_class = 1, 1
        self.state = 0
        self.fill = 0

    def kind_update(self, which: int) -> None:
        m = self.kind[self.state]
        total = m[0] + m[1]
        m[which] += 40
        if total >= 6000:
            m[0] = max(m[0] >> 1, 1)
            m[1] = max(m[1] >> 1, 1)
        self.state = ((self.state << 1) | which) & 3 if which else (self.state << 1) & 2

    def lit_escaped(self, sym: int) -> None:
        new = self.lit_new
        new.remove(sym)
        self.esc_lit = self.esc_lit + 1 if new.t[1] else 0
        for j in range(max(sym - 8, 0), min(sym + 8, 255)):
            if new.t[256 + j]:
                new.inc(j, 1000, 1)

    def lit_done(self, sym: int) -> None:
        self.lit_seen.inc(sym, 1000, 1)
        if self.lit_seen.t[256 + sym] == 3:
            self.esc_lit = self.esc_lit - 1 if self.esc_lit > 1 else 1
        if self.fill < WIN:
            self.fill += 1

    def open_classes(self) -> None:
        while self.fill > self.next_limit:
            self.dist.inc(self.next_class, 6000, 24)
            self.next_class += 1
            self.next_limit <<= 1

    def len_escaped(self, s: int) -> None:
        new = self.len_new
        new.remove(s)
        self.esc_len = self.esc_len + 8 if new.t[1] else 0
        for j in range(max(s - 4, 0), min(s + 4, 63)):
            if new.t[64 + j]:
                new.inc(j, 6000, 1)

    def len_done(self, s: int, code: int) -> None:
        self.len_seen.inc(s, 6000, 8)
        if self.len_seen.t[64 + s] == 24:
            self.esc_len = self.esc_len - 8 if self.esc_len > 8 else 1
        if self.fill < WIN:
            self.fill = min(self.fill + code + 3, WIN)


class _RangeDecoder:
    """The 16-bit range decoder over the packed bytes, from byte 8 (the first two bytes are the start value)."""

    def __init__(self, src: bytes) -> None:
        self.src = src
        self.pos = 10
        self.value = (src[8] << 8 | src[9]) if len(src) >= 10 else 0xFFFF
        self.low, self.high = 0, 0xFFFF
        self.bitbuf = 0

    def code(self, lo: int, hi: int, tot: int) -> None:
        """Narrow the interval to ``[lo, hi)`` of ``tot`` and shift out the settled bits."""
        rng = self.high - self.low + 1
        self.high = self.low + rng * hi // tot - 1
        self.low = self.low + rng * lo // tot
        while True:
            if not ((self.high ^ self.low) & 0x8000):
                self.high = ((self.high << 1) | 1) & 0xFFFF
                self.low = (self.low << 1) & 0xFFFF
                flip = 0
            elif (self.low & 0x4000) and not (self.high & 0x4000):
                self.high = ((self.high << 1) | 0x8001) & 0xFFFF
                self.low = (self.low << 1) & 0x7FFF
                flip = 0x8000
            else:
                return
            b = (self.bitbuf << 1) & 0x1FF
            if not (b & 0xFF):
                if self.pos < len(self.src):
                    b = (self.src[self.pos] << 1) | 1
                    self.pos += 1
                else:
                    b = 256
            self.bitbuf = b
            self.value = (((self.value << 1) ^ flip) | (b >> 8)) & 0xFFFF

    def target(self, tot: int) -> int:
        return ((self.value - self.low + 1) * tot - 1) // (self.high - self.low + 1)


def decompress(data: bytes, is_cancelled: Optional[Callable[[], bool]] = None) -> Optional[bytes]:
    """The whole decoded file (u32 size + payload), or None when ``is_cancelled`` returns true first."""
    if data[:8] != MAGIC:
        raise ValueError("not an *SK_ASC* file")
    rc = _RangeDecoder(data)
    code, target = rc.code, rc.target
    M = _Models()
    win = bytearray(WIN)
    wpos = 0
    out = bytearray()
    next_check = _CANCEL_EVERY

    while True:
        if is_cancelled is not None and len(out) >= next_check:
            next_check += _CANCEL_EVERY
            if is_cancelled():
                return None
        c0, c1 = M.kind[M.state]
        tot = c0 + c1 + 1
        t = target(tot)
        if c0 > t:
            code(0, c0, tot)
            M.kind_update(0)
            seen, new = M.lit_seen, M.lit_new
            total = seen.t[1] + M.esc_lit
            t = target(total)
            if t >= seen.t[1]:
                code(seen.t[1], total, total)
                sym, lo = new.find(target(new.t[1]))
                code(lo, lo + new.t[256 + sym], new.t[1])
                M.lit_escaped(sym)
            else:
                sym, lo = seen.find(t)
                code(lo, lo + seen.t[256 + sym], total)
            M.lit_done(sym)
            win[wpos] = sym
            out.append(sym)
            wpos = (wpos + 1) % WIN
        elif c0 + c1 > t:
            code(c0, c0 + c1, tot)
            M.kind_update(1)
            M.open_classes()
            dist = M.dist
            k, lo = dist.find(target(dist.t[1]))
            code(lo, lo + dist.t[16 + k], dist.t[1])
            dist.inc(k, 6000, 24)
            if k <= 1:
                d = k
            else:
                base = 1 << (k - 1)
                cnt = M.fill - base if base == M.next_limit >> 1 else base
                u = target(cnt)
                code(u, u + 1, cnt)
                d = base + u
            seen, new = M.len_seen, M.len_new
            total = seen.t[1] + M.esc_len
            t = target(total)
            if t >= seen.t[1]:
                code(seen.t[1], total, total)
                s, lo = new.find(target(new.t[1]))
                code(lo, lo + new.t[64 + s], new.t[1])
                M.len_escaped(s)
            else:
                s, lo = seen.find(t)
                code(lo, lo + seen.t[64 + s], total)
            if s == 15:
                ln = 783
            elif s >= 16:
                u = target(16)
                code(u, u + 1, 16)
                ln = (s - 16) * 16 + u + 15
            else:
                ln = s
            M.len_done(s, ln)
            sp = (wpos - 1 - d) % WIN
            for _ in range(ln + 3):
                c = win[sp]
                win[wpos] = c
                out.append(c)
                wpos = (wpos + 1) % WIN
                sp = (sp + 1) % WIN
        else:
            return bytes(out)
