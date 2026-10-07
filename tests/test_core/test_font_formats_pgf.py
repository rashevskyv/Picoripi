"""PSP PGF fonts (core/font_formats/pgf.py): the pixel run-length code; whole fonts are checked on real data
(tests/test_plugins/test_lunar_ssh/test_real_data.py)."""
import random

from core import font_formats
from core.font_formats import pgf


def _unrle(nibbles, count):
    out, i = [], 0
    while len(out) < count:
        n = nibbles[i]
        i += 1
        if n < 8:
            out += [nibbles[i]] * (n + 1)
            i += 1
        else:
            out += nibbles[i:i + 16 - n]
            i += 16 - n
    assert i == len(nibbles)
    return out


def test_run_length_code_reads_back():
    rng = random.Random(7)
    for _ in range(200):
        values = [rng.choice([0, 0, 0, 15, 7, rng.randrange(16)]) for _ in range(rng.randrange(1, 120))]
        assert _unrle(pgf._rle(values), len(values)) == values


def test_detected_by_its_magic():
    assert font_formats.detect(b"\0\0\x88\x01PGF0" + bytes(8)) == "pgf"
