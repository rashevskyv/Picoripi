"""MadWorld build: the translation written into a copy of the Wii disc (ISO), in place in its DATA partition.

The build reads the original disc (the path the unpack recorded) and the source and translation folders:
  text/*.mwt        changed messages: the lines are rebuilt into their table, new letters come from the font grids
  font/font_*.tpl   edited glyph cells are drawn into the glyph atlases
  ui/*.tpl          pictures with English text (same size as the original)
  font/system.tpl, hbm/*, opening.bnr/*    copied back as they are
An unchanged translation gives the original disc byte for byte.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, List, Set, Tuple

from core.containers import wia, wii_disc
from core.i18n import tr
from core.project_library import console_keys
from core.project_library.build import Cancel
from plugins.common.disc_source import disc_of_source
from utils.logging_utils import log_warning

from . import archives, fonts, gx, messages, unpack, wii_patch

ISO_NAME = "MadWorld (Europe) (UA).iso"
COPY_CHUNK = 8 << 20
HBM = unpack.HBM


def _common_key() -> bytes:
    path = console_keys.path_for("wii")
    if not path:
        raise ValueError(tr("Building needs the Wii key file: set its path in the console keys."))
    return wii_disc.load_common_key(path)


def _changed_texts(source: Path, translation: Path) -> Dict[str, Tuple[dict, List[str]]]:
    """``{unit file: (source block, new strings)}`` of the text files the translation changes."""
    out = {}
    trans = translation / "text"
    for path in sorted(trans.rglob("*.mwt")) if trans.is_dir() else []:
        rel = path.relative_to(trans).as_posix()[:-4]
        src = source / "text" / f"{rel}.mwt"
        if not src.is_file():
            raise ValueError(tr("text/{0}.mwt: no such file in the source", rel))
        old = json.loads(src.read_text(encoding="utf-8"))["blocks"][0]
        new = json.loads(path.read_text(encoding="utf-8")).get("blocks", [{}])[0].get("strings", [])
        if new != old["strings"]:
            if len(new) != len(old["strings"]):
                raise ValueError(tr("text/{0}.mwt: the number of messages changed", rel))
            out[rel] = (old, new)
    return out


def rebuild_unit(grids: fonts.Grids, unit: unpack.Unit, change, edits: Dict[str, Set[str]],
                 missing: Set[str]) -> Tuple[bytes, bytes]:
    """``(msd, mtd)`` of a unit with the translation's lines and the edited font glyphs."""
    flag, msgs = messages.msd_parse(unit.msd)
    atlas = unit.atlas_data
    chars = unit.chars
    first = atlas["first"]
    palette = atlas["pages"][0][3]
    glyphs = {}
    for idx, g in atlas["glyphs"].items():
        pal = atlas["pages"][g[5]][3]
        cell = g[2] if g[5] == 0 else messages.quantize(messages.alpha_of(g, pal), messages.inten_of(g, pal), palette)
        glyphs[idx] = (g[0], g[1], cell, g[3], g[4])
    for idx, (ch, style) in chars.items():                       # glyphs the translation's font changes
        if ch in edits.get(style, ()):
            new = grids.glyph(style, ch)
            if new:
                glyphs[idx] = (new[0], new[1], messages.quantize(new[2], new[3], palette), new[4], glyphs[idx][4])
    msd = unit.msd
    if change:
        old, strings = change
        by_char: Dict[tuple, int] = {}
        for idx, key in sorted(chars.items()):
            by_char.setdefault(key, idx)
        out_msgs = []
        for (ident, words), text, old_text, end in zip(msgs, strings, old["strings"], old["ends"]):
            if text == old_text:
                out_msgs.append((ident, words))
                continue
            styles = Counter(chars[w - first][1] for w in words if w - first in chars)
            style = styles.most_common(1)[0][0] if styles else "subtitle"

            def glyph_of(ch: str, style: str = style) -> int:
                idx = by_char.get((ch, style))
                if idx is None:
                    other = next((i for (c, _s), i in by_char.items() if c == ch), None)
                    new = grids.glyph(style, ch)
                    if new is None and other is not None:
                        return first + other
                    if new is None:
                        missing.add(ch)
                        return messages.SPACE
                    idx = max(glyphs) + 1 if glyphs else 0
                    glyphs[idx] = (new[0], new[1], messages.quantize(new[2], new[3], palette), new[4], float(new[5]))
                    by_char[(ch, style)] = idx
                return first + idx

            out_msgs.append((ident, messages.text_to_words(text, end, glyph_of)))
        msd = messages.msd_build(flag, out_msgs, len(msd))
        msd += bytes(-len(msd) % 0x20)
    return msd, messages.mtd_build(atlas, glyphs)


def _asset_changes(source: Path, translation: Path, read: Callable[[str], bytes],
                   out: Dict[str, bytes]) -> None:
    """Add to ``out`` (disc path -> bytes) the pictures, fonts-as-system, HOME Menu and banner files that changed."""
    for path in sorted(translation.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        rel = path.relative_to(translation).as_posix()
        if rel.startswith("text/") or rel.startswith("font/font_"):
            continue
        src = source / rel
        if not src.is_file():
            raise ValueError(tr("{0}: no such file in the source (new files are not written)", rel))
        new = path.read_bytes()
        if src.read_bytes() == new:
            continue
        if rel == "font/system.tpl":
            out["etc/font.tpl"] = new
        elif rel.startswith("ui/"):
            game, _sep, offset = rel[3:-4].partition("@")
            at = int(offset, 16) if offset else 0
            base = bytearray(out.get(game) or read(game))
            old_size = gx.tpl_size(bytes(base), at)
            if old_size != len(new):
                raise ValueError(tr("{0}: the picture changed size ({1} -> {2} bytes); it does not fit back", rel,
                                    str(old_size), str(len(new))))
            base[at:at + len(new)] = new
            out[game] = bytes(base)
        elif rel.startswith("hbm/") and rel.count("/") == 1 and rel.endswith(".csv"):
            out[f"{HBM}/{rel[len('hbm/'):]}"] = new
        elif rel.startswith("hbm/homeBtn_ENG.arc/"):
            key = f"{HBM}/homeBtn_ENG.arc"
            out[key] = archives.replace(out.get(key) or read(key), rel[len("hbm/homeBtn_ENG.arc/"):], new)
        elif rel.startswith("opening.bnr/"):
            out["opening.bnr"] = archives.replace(out.get("opening.bnr") or read("opening.bnr"),
                                                  rel[len("opening.bnr/"):], new)
        else:
            raise ValueError(tr("{0}: no such file in the game (new files are not written)", rel))


def pack(source: Path, translation: Path, read: Callable[[str], bytes], units: List[unpack.Unit],
         progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Tuple[Dict[str, bytes], List[str]]:
    """``({disc path: new bytes}, warnings)`` of the translation."""
    font_map = fonts.harvest_fonts([(u.atlas_data, u.chars) for u in units])
    index = fonts.font_index(font_map)
    grids = fonts.Grids(index, source, translation)
    edits = {style: grids.edited(style) for style in index}
    texts = _changed_texts(source, translation)
    out: Dict[str, bytes] = {}
    missing: Set[str] = set()
    for n, unit in enumerate(units):
        if is_cancelled():
            raise Cancel()
        touched = any(ch in edits.get(style, ()) for ch, style in unit.chars.values())
        if unit.rel not in texts and not touched:
            continue
        progress(40 + 30 * n // max(1, len(units)), unit.rel)
        msd, mtd = rebuild_unit(grids, unit, texts.get(unit.rel), edits, missing)
        for which, blob in messages.save_unit(unit.kind, unit.raw, msd, mtd):
            out[unit.rel if which == 0 else unit.atlas] = blob
    _asset_changes(source, translation, read, out)
    warnings = []
    if missing:
        warnings.append(tr("letters with no picture in the font (not shown in the game; draw them in the Font Editor): {0}",
                           "".join(sorted(missing))))
    return out, warnings


def _copy(src: Path, dst: Path, progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> None:
    total = os.path.getsize(src) or 1
    done = 0
    with open(src, "rb") as a, open(dst, "wb") as b:
        while True:
            if is_cancelled():
                raise Cancel()
            chunk = a.read(COPY_CHUNK)
            if not chunk:
                break
            b.write(chunk)
            done += len(chunk)
            progress(70 * done // total, "copy")


def build_iso(source_dir: str, translation_dir: str, output_dir: str,
              progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    """Write the translated disc into ``output_dir`` and return its path. The original disc is never changed."""
    image = disc_of_source(source_dir)
    with open(image, "rb") as stream:
        head = stream.read(0x20)
    if wia.is_wia_or_rvz(head):
        raise ValueError(tr("The build writes an .iso copy of the disc. Convert {0} to ISO first.", image.name))
    common = _common_key()
    source, translation = Path(source_dir), Path(translation_dir)
    with open(image, "rb") as stream:
        key = wii_patch.title_key(stream, common)
        reader = wii_disc.WiiImage(stream, common)
        entries = {e.path[len("files/"):]: e for e in reader.entries() if e.path.startswith("files/")}

        def read(rel: str) -> bytes:
            return reader.read(entries[rel])

        units = unpack.scan_units(read, set(entries), messages.labels(), progress, is_cancelled)
        if units is None:
            raise Cancel()
        changes, warnings = pack(source, translation, read, units, progress, is_cancelled)
    for line in warnings:
        log_warning(line, "madworld")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / ISO_NAME
    tmp = target.with_name(target.name + ".tmp")
    try:
        _copy(image, tmp, progress, is_cancelled)
        progress(80, "write")
        wii_patch.patch_iso(str(tmp), key, changes)
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    progress(100, "done")
    return str(target)
