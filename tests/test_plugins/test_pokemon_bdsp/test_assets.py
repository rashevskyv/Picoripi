"""Brilliant Diamond / Shining Pearl: the fonts and pictures unpacked by Picoripi match the workspace source, and the word
widths of an edited label are measured with the English fonts. Real data; skips when the owner's packages are not there."""
import re
from pathlib import Path

import pytest
import romhacking_root
from PIL import Image

from core.containers import console_crypto
from plugins.pokemon_bdsp import unpack
from plugins.pokemon_bdsp.widths import Widths, edited_labels

ROOT = romhacking_root.under("Pokemon") / "Brilliant Diamond and Shining Pearl"
BASE = ROOT / "nsp" / "Pokemon Brilliant Diamond [0100000011D90000][v0].nsp"
UPDATE = ROOT / "nsp" / "Pokemon Brilliant Diamond [0100000011D90800][v393216].nsp"
KEY_INI = romhacking_root.root() / "_shared" / "scripts" / "zelda_env.ini" if romhacking_root.root() else None


def _switch_key_path():
    if KEY_INI is None or not KEY_INI.is_file():
        return None
    for line in KEY_INI.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^\s*switch_keys\s*=\s*(.+?)\s*$", line)
        if match and Path(match.group(1)).is_file():
            return match.group(1)
    return None


@pytest.fixture(scope="module")
def unpacked(tmp_path_factory):
    if not (BASE.is_file() and UPDATE.is_file()) or _switch_key_path() is None or not (ROOT / "source").is_dir():
        pytest.skip("the owner's Brilliant Diamond packages, the key path or the workspace source are not on disk")
    folder = tmp_path_factory.mktemp("bdsp")
    with console_crypto.key_source(lambda c: _switch_key_path() if c == "switch" else None):
        unpack.unpack({"base": str(BASE), "update": str(UPDATE)}, str(folder), lambda p, t: None, lambda: False)
    return folder / unpack.SOURCE_DIR


def test_fonts_and_pictures_match_the_workspace(unpacked):
    theirs = [p for p in (ROOT / "source").rglob("*")
              if p.is_file() and p.relative_to(ROOT / "source").parts[0] in ("font", "texture")]
    assert len(theirs) > 40
    mismatched = []
    for p in theirs:
        mine = unpacked / p.relative_to(ROOT / "source")
        if not mine.is_file():
            mismatched.append(("missing", p.name))
        elif p.suffix == ".png":
            a, b = Image.open(p), Image.open(mine)
            if a.size != b.size or a.convert("RGBA").tobytes() != b.convert("RGBA").tobytes():
                mismatched.append(("pixels", p.name))
        elif p.read_bytes() != mine.read_bytes():
            mismatched.append(("bytes", p.name))
    assert mismatched == []


def test_an_edited_label_gets_widths_from_the_english_fonts(unpacked):
    source = unpacked
    widths = Widths(lambda rel: source / rel if (source / rel).is_file() else None)
    value = {"labelDataArray": [{"labelName": "x", "wordDataArray": [
        {"patternID": 0, "eventID": 0, "tagIndex": -1, "tagValue": 0.0, "str": "Adventure", "strWidth": 0.0},
        {"patternID": 0, "eventID": 7, "tagIndex": -1, "tagValue": 0.0, "str": "", "strWidth": -1.0}]}]}
    old = {"labelDataArray": []}
    assert len(edited_labels(value, old)) == 1
    widths.label(value["labelDataArray"][0])
    word = value["labelDataArray"][0]["wordDataArray"]
    assert word[0]["strWidth"] == pytest.approx(sum(widths.char(c) for c in "Adventure"))
    assert word[0]["strWidth"] > 0 and word[1]["strWidth"] == -1.0
