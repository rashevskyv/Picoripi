"""Build No More Heroes (Wii, Europe): write the translation into a copy of the disc image as a playable ISO.

The build reads the original disc (its path is in the source mark), packs every changed file of ``translation``
back into its game format, and writes the disc files into a copy of the ISO in place (``wii_write``). An unchanged
translation gives the original ISO byte for byte. A plain ISO source is needed: a WIA or RVZ image keeps its
partition decrypted, so it cannot be written back as an ISO here.

  translation\\text\\<disc file>.nmt     blocks of English lines (edited); a block's line count must not change
  translation\\font\\<font>.tpl          glyph grids (edited in the Font Editor): new glyphs go into the boxes
  translation\\ui\\<disc file>[\\<chunk>].tpl  pictures with text: the same format and size as the original
  translation\\hbm\\..., opening.bnr\\...  HOME Menu and channel banner members
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from core.containers import wia, wii_disc
from core.containers.console_crypto import key_source
from core.i18n import tr
from core.project_library import console_keys, images
from core.project_library.build import Cancel
from plugins.common.disc_source import disc_of_source, find_disc_root
from utils.logging_utils import log_warning

from . import archives, gx, rmhg
from .unpack import HBM, INDEX, DiscFiles
from .wii_write import write_changes

ISO_NAME = "No More Heroes (Europe) (UA).iso"
TARGET_ISO = "wii_iso"
GLOBAL_BIN = "Global/Global.bin"
SKIP_NAMES = (".tmp", ".bak")
Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def changed_files(translation: Path, source: Path) -> List[str]:
    """Files under ``translation`` that are new or differ from the same path in ``source``."""
    out = []
    for path in sorted(translation.rglob("*")):
        if not path.is_file() or path.name.lower() in ("desktop.ini", "thumbs.db") or path.name.endswith(SKIP_NAMES):
            continue
        rel = path.relative_to(translation).as_posix()
        original = source / rel
        if not original.is_file() or original.read_bytes() != path.read_bytes():
            out.append(rel)
    return out


# ---------------------------------------------------------------- text, glyphs and pictures

def _text_changes(translation: Path, source: Path) -> dict:
    """``{disc file: [(block, new strings)]}`` of every block whose lines the translation changes."""
    out = {}
    trans = translation / "text"
    for path in sorted(trans.rglob("*.nmt")) if trans.is_dir() else []:
        rel = path.relative_to(trans).as_posix()[:-4]
        if rel == "main.dol":
            continue
        src = source / "text" / f"{rel}.nmt"
        if not src.is_file():
            raise ValueError(tr("text\\{0}.nmt is not a file of the source", rel))
        old = json.loads(src.read_text(encoding="utf-8"))
        new = json.loads(path.read_text(encoding="utf-8"))
        changes = [(b_old, b_new.get("strings", [])) for b_old, b_new in zip(old["blocks"], new.get("blocks", []))
                   if b_new.get("strings") != b_old["strings"]]
        if changes:
            out[rel] = changes
    return out


def font_glyphs(translation: Path, source: Path, index: dict) -> dict:
    """``{font key: {code: glyph}}`` of the glyphs the translation's fonts change (drawn or edited cells)."""
    out = {}
    for key, info in index["fonts"].items():
        rel = f"font/{key}.tpl"
        new, old = translation / rel, source / rel
        if not new.is_file() or not old.is_file() or new.read_bytes() == old.read_bytes():
            continue
        cell, cols, codes = tuple(info["cell"]), info["columns"], info["codes"]
        a = gx.grid_read(new.read_bytes(), cell, cols, len(codes))
        b = gx.grid_read(old.read_bytes(), cell, cols, len(codes))
        # a drawn letter sits in its cell the way the font's own letters do
        shift_y = _common_shift(info["metrics"])
        changed = {}
        for code, (cw, ch, px), (_w, _h, opx) in zip(codes, a, b):
            if px == opx:
                continue
            m = info["metrics"].get(str(code))
            dx, dy = (m[2] - m[5], m[3] - m[6]) if m else (0, shift_y)
            right, bottom = gx.ink_box(px, cw, ch)
            if not right:
                changed[code] = (1, 1, dx, dy, m[4] if m else max(1, cw // 3), b"\0")
                continue
            top = next(y for y in range(ch) if any(px[y * cw:(y + 1) * cw]))
            w, h = right, bottom - top
            glyph = b"".join(px[(top + r) * cw:(top + r) * cw + w] for r in range(h))
            adv = m[4] if m and right <= m[0] + m[5] else right + 1 + max(dx, 0)
            changed[code] = (w, h, dx, top + dy, adv, glyph)
        if changed:
            out[key] = changed
    return out


def _common_shift(metrics: dict) -> int:
    if not metrics:
        return 0
    counts: Dict[int, int] = {}
    for m in metrics.values():
        counts[m[3] - m[6]] = counts.get(m[3] - m[6], 0) + 1
    return max(counts, key=lambda k: (counts[k], -k))


def _glyph_for(code: int, atlas: dict, edits: dict, font: dict):
    if code in edits:
        return edits[code]
    if code in atlas["glyphs"]:
        return atlas["glyphs"][code]
    return font.get(code)


def _font_source(source: Path, index: dict, key: str, cache: dict) -> dict:
    """All glyphs of a font as the source has them (metrics from the index)."""
    if key not in cache:
        info = index["fonts"][key]
        cells = gx.grid_read((source / "font" / f"{key}.tpl").read_bytes(), tuple(info["cell"]),
                             info["columns"], len(info["codes"]))
        glyphs = {}
        for code, (cw, _ch, px) in zip(info["codes"], cells):
            m = info["metrics"].get(str(code))
            if not m:
                continue
            gw, gh, bx, by, adv, x, y = m
            glyphs[code] = (gw, gh, bx, by, adv,
                            b"".join(px[(y + r) * cw + x:(y + r) * cw + x + gw] for r in range(gh)))
        cache[key] = glyphs
    return cache[key]


def _split_ui(inner: str, files: dict) -> tuple:
    """``ui\\<disc file>[\\<chunk>]`` -> ``(disc file, chunk path or "")``."""
    parts = inner.split("/")
    for cut in range(len(parts), 0, -1):
        rel = "/".join(parts[:cut])
        if rel in files:
            return rel, "/" + "/".join(parts[cut:]) if cut < len(parts) else ""
    raise ValueError(tr("ui\\{0} is not a file of the disc", inner))


# ---------------------------------------------------------------- main.dol menu words

def dol_apply(dol: bytes, body: dict, missing: set) -> bytes:
    out = bytearray(dol)
    for block in body["blocks"]:
        for (at, room), text in zip(block["dol"], block["strings"]):
            raw = rmhg.encode_text(text, missing) + b"\0"
            if len(raw) > room:
                raise ValueError(tr("main.dol: «{0}» is longer than its room ({1} > {2} bytes)", text, len(raw), room))
            out[at:at + room] = raw + bytes(room - len(raw))
    return bytes(out)


def _dol_body(translation: Path, source: Path) -> dict | None:
    dol_new = translation / "text" / "main.dol.nmt"
    if not dol_new.is_file():
        return None
    body = json.loads(dol_new.read_text(encoding="utf-8"))
    old = json.loads((source / "text" / "main.dol.nmt").read_text(encoding="utf-8"))
    if [b.get("strings") for b in body["blocks"]] == [b["strings"] for b in old["blocks"]]:
        return None
    for b_new, b_old in zip(body["blocks"], old["blocks"]):
        b_new["dol"] = b_old["dol"]
    return body


def _dol_codes(body: dict | None) -> set:
    codes: set = set()
    if body:
        for block in body["blocks"]:
            for text in block["strings"]:
                codes.update(rmhg.codes_of(rmhg.encode_text(text)))
    return {c for c in codes if c >= 0x80}


# ---------------------------------------------------------------- the pack

def _repack_text(tree: list, texts: dict, rel: str, info: dict, edits: dict, source: Path,
                 index: dict, cache: dict, missing: set, no_glyph: set) -> None:
    """The boxes of ``rel`` (text blocks and their atlases) set in ``tree``."""
    boxes = {}
    for block, strings in texts.get(rel, []):
        if len(strings) != len(block["strings"]):
            raise ValueError(tr("text\\{0}.nmt: the number of lines changed in block «{1}»", rel, block["name"]))
        encoded = [rmhg.encode_text(s, missing) for s in strings]
        for path in block["gdlg"]:
            table = rmhg.gdlg_strings(boxes.get(path) or rmhg.get(tree, path))
            for idx, raw in zip(block["lines"], encoded):
                table[idx] = raw
            boxes[path] = rmhg.gdlg_with(boxes.get(path) or rmhg.get(tree, path), table)
    for path, blob in boxes.items():
        rmhg.put(tree, path, blob)
    new_codes: dict = {}
    for path, blob in boxes.items():
        table = rmhg.gdlg_strings(blob)
        parent = path.rsplit("/", 1)[0]
        for idx in rmhg.gdlg_lines(blob):
            new_codes.setdefault(parent, set()).update(rmhg.codes_of(table[idx]))
    _repack_atlases(tree, info, edits, new_codes, source, index, cache, missing, no_glyph)


def _repack_atlases(tree: list, info: dict, edits: dict, new_codes: dict, source: Path, index: dict,
                    cache: dict, missing: set, no_glyph: set) -> None:
    for path, a in info["atlases"].items():
        font_edits = edits.get(a["font"], {})
        blob = rmhg.get(tree, path)
        atlas = rmhg.stri_parse(blob)
        need = set(atlas["glyphs"]) | new_codes.get(path.rsplit("/", 1)[0], set())
        if not a["box"]:
            need |= info.get("dol_codes", set())
        if need == set(atlas["glyphs"]) and not set(font_edits) & need:
            continue
        font = _font_source(source, index, a["font"], cache)
        glyphs = {}
        for code in list(atlas["glyphs"]) + sorted(need - set(atlas["glyphs"])):
            g = _glyph_for(code, atlas, font_edits, font)
            if g is None:
                no_glyph.add(rmhg.code_char(code))
                continue
            glyphs[code] = g
        rmhg.put(tree, path, rmhg.stri_build(blob, glyphs))


def _repack_file(rel: str, texts: dict, pictures: dict, disc: DiscFiles, index: dict, edits: dict, source: Path,
                 cache: dict, missing: set, no_glyph: set, dol_codes: set) -> bytes:
    """The new disc bytes of the game file ``rel`` (packed again when it was packed)."""
    packed, tree, rest = rmhg.load_game_file(disc.read(rel))
    if tree is None:                                     # a picture file (GCT0)
        new = gx.tpl_to_gct(pictures[rel][""], rest)
        return rmhg.lz_encode(new) if packed else new
    info = dict(index["files"].get(rel, {"atlases": {}}))
    info["dol_codes"] = dol_codes
    _repack_text(tree, texts, rel, info, edits, source, index, cache, missing, no_glyph)
    for chunk, picture in pictures.get(rel, {}).items():
        rmhg.put(tree, chunk, gx.tpl_to_gct(picture, rmhg.get(tree, chunk)))
    data = rmhg.rmhg_save(tree, rest)
    return rmhg.lz_encode(data) if packed else data


def pack(translation: Path, source: Path, index: dict, disc: DiscFiles, progress: Progress,
         is_cancelled: Cancelled) -> Tuple[Dict[str, bytes], List[str]]:
    """``({'files/<disc path>' or 'sys/main.dol': bytes}, warnings)`` of every disc file the translation changes."""
    edits = font_glyphs(translation, source, index)
    texts = _text_changes(translation, source)
    missing: set = set()
    no_glyph: set = set()
    out: dict = {}
    pictures: dict = {}          # disc file -> {chunk path: new TPL}
    loose: List[str] = []
    for rel in changed_files(translation, source):
        parts = rel.split("/")
        if parts[0] in ("text", "font"):
            continue
        if parts[0] == "ui":
            game, chunk = _split_ui(rel[3:-4], disc.files)
            pictures.setdefault(game, {})[chunk] = (translation / rel).read_bytes()
        else:
            loose.append(rel)
    body = _dol_body(translation, source)
    dol_codes = _dol_codes(body)
    work = set(texts) | set(pictures)
    for rel, info in index["files"].items():
        if any(a["font"] in edits or (dol_codes and not a["box"]) for a in info["atlases"].values()):
            work.add(rel)
    cache: dict = {}
    for n, rel in enumerate(sorted(work)):
        if is_cancelled():
            raise Cancel()
        progress(int(100 * n / max(1, len(work))) // 2, rel)
        out[f"files/{rel}"] = _repack_file(rel, texts, pictures, disc, index, edits, source, cache, missing,
                                           no_glyph, dol_codes)
    swaps = [(disc.read(rel[len("files/"):]), blob) for rel, blob in out.items() if rel.startswith("files/Global/Global/")]
    if swaps:                       # the game also keeps every Global\Global file inside Global.bin (a DX archive)
        out[f"files/{GLOBAL_BIN}"] = rmhg.lz_encode(rmhg.dxa_replace(rmhg.lz_decode(disc.read(GLOBAL_BIN)), swaps))
    if body:
        out["sys/main.dol"] = dol_apply(disc.dol(), body, missing)
    for rel in loose:
        out.update(_loose_change(translation, rel, disc, out))
    warnings = []
    if missing:
        warnings.append(tr("characters with no code in the game (written as '?'): {0}", "".join(sorted(missing))))
    if no_glyph:
        warnings.append(tr("letters with no picture in the font (not seen in the game; draw them in the Font Editor): "
                           "{0}", "".join(sorted(no_glyph))))
    return out, warnings


def _loose_change(translation: Path, rel: str, disc: DiscFiles, out: dict) -> dict:
    parts = rel.split("/")
    new = (translation / rel).read_bytes()
    if parts[0] == "hbm" and parts[1].endswith(".csv"):
        return {f"files/{HBM}/{parts[1]}": new}
    if parts[0] == "hbm" and parts[1] == "homeBtn_ENG.arc":
        key = f"files/{HBM}/homeBtn_ENG.arc"
        return {key: archives.replace(out.get(key) or disc.read(f"{HBM}/homeBtn_ENG.arc"), "/".join(parts[2:]), new)}
    if parts[0] == "opening.bnr":
        key = "files/opening.bnr"
        return {key: archives.replace(out.get(key) or disc.read("opening.bnr"), "/".join(parts[1:]), new)}
    raise ValueError(tr("{0} is not a file of the disc (new files are not supported)", rel))


# ---------------------------------------------------------------- the build

def _is_rvz(image: Path) -> bool:
    with open(image, "rb") as stream:
        return wia.is_wia_or_rvz(stream.read(4))


def _copy(source: Path, tmp: Path, progress: Progress, is_cancelled: Cancelled) -> bool:
    total = os.path.getsize(source)
    done = 0
    with open(source, "rb") as src, open(tmp, "wb") as dst:
        while True:
            if is_cancelled():
                return False
            chunk = src.read(1 << 22)
            if not chunk:
                return True
            dst.write(chunk)
            done += len(chunk)
            progress(min(99, 100 * done // max(1, total)), tr("Copying the disc image"))


def build_iso(source_dir: str, translation_dir: str, output_dir: str, progress: Progress,
              is_cancelled: Cancelled) -> str:
    """Write ``ISO_NAME`` into ``output_dir`` and return its path."""
    root = find_disc_root(source_dir)
    image = disc_of_source(root)
    if _is_rvz(image):
        raise ValueError(tr("The build needs the game as a plain ISO. Convert the {0} image to ISO first.",
                            image.name))
    key_file = console_keys.path_for("wii")
    if key_file is None:
        raise ValueError(tr("Set the Wii key file in the console keys first."))
    index = json.loads((root / INDEX).read_text(encoding="utf-8"))
    translation, source = Path(translation_dir), Path(source_dir)
    with key_source(console_keys.path_for), images.open_image(image) as reader:
        disc = DiscFiles(reader)
        changes, warnings = pack(translation, source, index, disc, progress, is_cancelled)
    common_key = wii_disc.load_common_key(key_file)
    out = Path(output_dir) / ISO_NAME
    tmp = out.with_name(out.name + ".tmp")
    if not _copy(image, tmp, progress, is_cancelled):
        tmp.unlink(missing_ok=True)
        raise Cancel()
    if changes:
        with open(tmp, "r+b") as stream:
            write_changes(stream, common_key, changes)
    os.replace(tmp, out)
    for line in warnings:
        log_warning(line, "nmh")
    return str(out)
