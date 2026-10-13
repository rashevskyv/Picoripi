"""The two title logos through the shared texture backend (real ROM; skipped where the ROM is missing)."""
import json
from pathlib import Path

from core import texture_formats

from .test_real_rom import _load

SOURCES = Path(__file__).resolve().parents[3] / "plugins" / "zelda_ladx" / "texture_sources.json"


def _entries():
    return json.loads(SOURCES.read_text(encoding="utf-8"))


def test_each_title_logo_writes_back_unchanged():
    raw = _load()
    for entry in _entries():
        params = entry["params"]
        textures = texture_formats.read(entry["format"], raw, params)
        assert len(textures) == 1
        image = textures[0].image
        out = texture_formats.write(entry["format"], raw, {0: image}, params)
        assert bytes(out) == raw, entry["label"]


def test_title_logos_do_not_overlap_each_other_or_the_font():
    spans = []
    for entry in _entries():
        params = entry["params"]
        start = int(params["offset"], 0)
        tiles = params["width"] // 8 * params["height"] // 8
        spans.append((start, start + tiles * 16))
    spans.append((0x3D000, 0x3D000 + 160 * 16))
    spans.sort()
    for (_s1, e1), (s2, _e2) in zip(spans, spans[1:]):
        assert e1 <= s2
