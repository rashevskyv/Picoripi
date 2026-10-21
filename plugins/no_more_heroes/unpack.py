"""Unpack No More Heroes (Wii, Europe RNHP99) into the English ``source`` tree Picoripi opens, and the index the build
needs (``nmh_index.json``, next to ``source``).

  source\\text\\<disc file>.nmt       the English lines of one game file (JSON: blocks of lines)
  source\\text\\main.dol.nmt          the English menu words the game keeps in its program
  source\\font\\<font>.tpl            every font the English text is drawn with, a grid of glyphs (I4)
  source\\ui\\<disc file>[\\<chunk>].tpl  every 2D picture with text: title logo, menus, loading screens, safety screens
  source\\hbm\\home.csv, hbm\\homeBtn_ENG.arc\\...  the Wii HOME Menu (messages, English pictures)
  source\\opening.bnr\\...            the disc channel banner pictures

A file the translation leaves alone is not touched later: the build writes only what differs from ``source``.
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Callable, Dict

from utils.atomic_io import atomic_write_bytes

from . import archives, gx, rmhg

GAME_ID = b"RNHP99"
HBM = "homebuttonData/HomeButton2"
INDEX = "nmh_index.json"
SOURCE = "source"

# Disc folders with English text or text pictures. STG and Demo hold the stage and cut-scene dialogue.
TEXT_DIRS = ("Card", "Demo", "Event", "Global/Global/HideGlobal", "HAYA", "Hide", "Hoshi", "LastLogo", "Loading",
             "Message", "STG", "Strap", "Title")
UI_DIRS = ("Card", "Global/Global/HideGlobal", "HAYA", "Hide", "LastLogo", "Loading", "Message", "Strap", "Title")
SKIP = re.compile(r"(?i)(^Demo/A\d|^Demo/TRV|^Demo/OBJ|US\.BIN$|_GI\.BIN$|TGS\.rsl$|^STG/STG\d+J/"
                  r"|^Strap/(?!.*English))")
JP = re.compile("[぀-ヿ一-鿿ｦ-ﾟ]")
STOP = {"en": "the you and is of it what that this your are with have for not can will",
        "de": "der die und ist das ich nicht du ein sie mit den zu auf",
        "fr": "le les et est vous je pas une des du pour avec ce", "es": "el los que una por para con del las es",
        "it": "il che di non una sono per gli della con hai"}
FONT_NAMES = {"GMYPメタルゴシックB": "gmyp_metal_gothic_b", "ヒラギノ角ゴ8等幅": "hiragino_kaku_gothic_mono",
              "ＤＦPOPミックスW5": "df_pop_mix_w5", "ＭＳ ゴシック": "ms_gothic"}


class DiscFiles:
    """The files of a Wii disc image (``files/`` paths without the prefix) read through core's reader."""

    def __init__(self, reader) -> None:
        self.reader = reader
        entries = reader.entries()
        self.files = {e.path[len("files/"):]: e for e in entries if e.path.startswith("files/")}
        self.main_dol = next(e for e in entries if e.path == "sys/main.dol")

    def read(self, rel: str) -> bytes:
        return self.reader.read(self.files[rel])

    def dol(self) -> bytes:
        return self.reader.read(self.main_dol)


def _wanted(rel: str) -> bool:
    return any(rel.startswith(d + "/") for d in TEXT_DIRS) and rel.upper().endswith((".RSL", ".BIN")) \
        and not SKIP.search(rel)


# ---------------------------------------------------------------- which files and boxes are English

def _lang(text: str) -> str:
    latin = len(re.findall(r"[A-Za-z]", text))
    if len(JP.findall(text)) * 3 > latin:                # mostly Japanese (an English box may keep a stray line)
        return "jp"
    words = re.findall(r"[a-z]+", text.lower())
    score = {k: sum(words.count(w) for w in v.split()) for k, v in STOP.items()}
    best = max(score, key=score.get)
    return best if score[best] >= 2 and score[best] > score["en"] else ("en" if score["en"] else "?")


def file_language(rel: str, names: set) -> str:
    """``en``, ``other`` or ``any`` (no language variants: the boxes inside decide)."""
    folder, name = rel.rsplit("/", 1) if "/" in rel else ("", rel)
    stem, ext = os.path.splitext(name)
    here = {n for n in names if n.startswith(folder + "/")} if folder else names
    join = (lambda n: f"{folder}/{n}") if folder else (lambda n: n)
    if re.match(r"[FGIS]_", stem) and join(stem[2:] + ext) in here:
        return "other"
    for i, ch in enumerate(stem):
        if ch in "EFGIS_" and sum(join(stem[:i] + c + stem[i + 1:] + ext) in here for c in "EFGIS_") >= 3:
            return "en" if ch == "E" else "other"
    if stem[-1:] in "FGIS" and join(stem[:-1] + ext) in here:
        return "other"
    if stem[-1:] == "E" and join(stem[:-1] + ext) in here:
        return "en"
    if any(join(stem + c + ext) in here for c in "EFGIS"):
        return "en" if join(stem + "E" + ext) not in here else "other"
    return "any"


def english_boxes(boxes: list, file_lang: str) -> list:
    """``boxes`` [(path, name, texts)] -> groups [[paths...]]: the English box(es) of each language set."""
    if file_lang == "en":
        return [[p] for p, _n, t in boxes if _lang(" ".join(t)) != "jp"]
    tuples = [tuple(p.strip("/").split("/")) for p, _n, _t in boxes]
    names = [n for _p, n, _t in boxes]
    keys = collections.Counter()
    for t, n in zip(tuples, names):
        for i in range(len(t)):
            keys[(len(t), i, t[:i] + ("*",) + t[i + 1:], n)] += 1
    groups: dict = collections.OrderedDict()
    for k, (t, n) in enumerate(zip(tuples, names)):
        best = max(range(len(t)), key=lambda i: (keys[(len(t), i, t[:i] + ("*",) + t[i + 1:], n)], i))
        groups.setdefault((len(t), best, t[:best] + ("*",) + t[best + 1:], n), []).append(k)
    out = []
    for members in groups.values():
        texts = [" ".join(boxes[k][2]) for k in members]
        langs = [_lang(t) for t in texts]
        # English is the first box that is not Japanese, unless it reads clearly as another language and another
        # box reads as English (some files order the languages differently)
        pick = next((k for k, lang in zip(members, langs) if lang != "jp"), None)
        if pick is None:
            continue
        if langs[members.index(pick)] in ("de", "fr", "es", "it"):
            pick = next((k for k, lang in zip(members, langs) if lang == "en"), None)
            if pick is None:
                continue
        same = [boxes[k][0] for k in members if boxes[k][2] == boxes[pick][2]]
        out.append(same)
    return out


# ---------------------------------------------------------------- fonts

def _slug(font: str, size: int, cluster: str = "") -> str:
    base = FONT_NAMES.get(font) or re.sub(r"[^a-z0-9]+", "_", font.lower()).strip("_") or "font"
    return f"{base}_{size}{cluster}"


def _jp_codes(codes) -> bool:
    """Mostly kana and kanji: the picture of a Japanese box."""
    codes = list(codes)
    return 3 * sum(0x829F <= c <= 0x82F1 or 0x8340 <= c <= 0x8396 or c >= 0x889F for c in codes) > len(codes)


def _sig(atlas: dict) -> dict:
    return {c: hashlib.md5(g[5] + bytes((g[2] & 255, g[3] & 255, g[4] & 255))).hexdigest()
            for c, g in atlas["glyphs"].items() if c != 0x20 and g[5]}


class Harvest:
    """Glyphs of every English atlas, per font. A named atlas belongs to its font name + size. An unnamed one joins
    the font of its size it shares the most identical glyphs with and draws no glyph differently, else the named
    font of its size it shares the most with, else a font of unnamed atlases of its own."""

    def __init__(self):
        self.items: list = []          # (rel, path, atlas)

    def collect(self, rel: str, path: str, atlas: dict) -> None:
        self.items.append((rel, path, atlas))

    def assign(self) -> tuple:
        """``(fonts {key: {code: glyph}}, keys {(rel, path): key}, labels {key: label})``."""
        fonts, sigs, keys, info = {}, {}, {}, {}
        named = [it for it in self.items if it[2]["font"]]
        unnamed = sorted((it for it in self.items if not it[2]["font"]), key=lambda it: -len(it[2]["glyphs"]))
        for rel, path, atlas in named + unnamed:
            sig, size = _sig(atlas), atlas["size"]
            if atlas["font"]:
                key = _slug(atlas["font"], size)
            else:
                clean, loose = [], []
                for other, osig in sigs.items():
                    if info[other][1] != size:
                        continue
                    same = sum(osig.get(c) == h for c, h in sig.items())
                    differ = sum(c in osig and osig[c] != h for c, h in sig.items())
                    if same and not differ:
                        clean.append((same, other))
                    elif info[other][0] != "Font":
                        loose.append((same, other))
                if clean or loose:
                    key = max(clean or loose)[1]
                else:
                    key = _slug("font", size, f"_{1 + sum(1 for v in info.values() if v == ('Font', size))}")
            info.setdefault(key, (atlas["font"] or "Font", size))
            font, osig = fonts.setdefault(key, {}), sigs.setdefault(key, {})
            for code, g in atlas["glyphs"].items():
                if (g[5] or code == 0x20) and code not in font:
                    font[code] = g
                    if code in sig:
                        osig[code] = sig[code]
            keys[(rel, path)] = key
        return fonts, keys, {k: f"{v[0]} {v[1]} px" for k, v in info.items()}


def _place(gw, gh, x, y, px, cw, ch) -> tuple:
    cell = bytearray(cw * ch)
    for r in range(min(gh, ch - y)):
        cell[(y + r) * cw + x:(y + r) * cw + x + min(gw, cw - x)] = px[r * gw:r * gw + min(gw, cw - x)]
    return (cw, ch, bytes(cell))


def write_fonts(source: Path, fonts: dict, meta: dict) -> dict:
    """``source\\font\\<key>.tpl`` per font; returns the index entry per font: cell, codes (cell order), and per
    harvested code ``[w, h, bx, by, adv, sx, sy]`` (the game's metrics and where the glyph sits in its cell)."""
    index = {}
    folder = source / "font"
    for key, glyphs in sorted(fonts.items()):
        codes = sorted(glyphs)
        slots = [rmhg.char_code(ch) for ch in rmhg.UKR_LETTERS if rmhg.char_code(ch) not in glyphs]
        letters = [g for c, g in glyphs.items() if 0x41 <= c <= 0x5A or 0x61 <= c <= 0x7A] or list(glyphs.values())
        lim_w = 2 * max(g[0] for g in letters) + 2
        lim_h = 2 * max(g[1] for g in letters) + 2
        place = {}
        for code in codes:
            gw, gh, bx, by = glyphs[code][:4]
            sx = bx if 0 <= bx and bx + gw <= lim_w else 0
            sy = by if 0 <= by and by + gh <= lim_h else max(0, min(by, lim_h - gh))
            place[code] = (sx, sy)
        cw = max([glyphs[c][0] + place[c][0] for c in codes] + [4])
        ch = max([glyphs[c][1] + place[c][1] for c in codes] + [4])
        cells = []
        for code in codes:
            gw, gh, _bx, _by, _adv, px = glyphs[code]
            cells.append(_place(gw, gh, *place[code], px, cw, ch) if gw and gh else None)
        cells += [None] * len(slots)
        atomic_write_bytes(folder / f"{key}.tpl", gx.grid_write(cells, (cw, ch), 16))
        index[key] = {"label": meta.get(key, key), "cell": [cw, ch], "columns": 16, "codes": codes + slots,
                      "metrics": {str(c): list(glyphs[c][:5]) + list(place[c]) for c in codes}}
    for stale in folder.glob("*.tpl") if folder.is_dir() else []:
        if stale.stem not in index:
            stale.unlink()
    return index


# ---------------------------------------------------------------- main.dol menu words

# Offsets in main.dol of the English strings the game draws from its program (title copyright, save screen, area
# names, map and shop key guides, job board, mission result, ranking). Written in place: a translation must fit
# the string's room (its bytes, its zero, the zero padding up to the next 4-byte boundary).
_SEL = (": Select", ": OK", ": Cancel")
DOL_BLOCKS = {
    "Title screen": [(0x42703A, "(c) Marvelous Entertainment Inc."), (0x42705B, "Licensed to and published by"),
                     (0x427078, "Rising Star Games Ltd."), (0x43680E, "Press Any Button")],
    "Save screen": [(0x42F19E, "(c) Marvelous Entertainment Inc."), (0x42F1BF, "Licensed to and published by"),
                    (0x42F1DC, "Rising Star Games Ltd."), (0x42F1F3, "LOAD OK?"), (0x42F1FC, "NO DATA"),
                    (0x42F204, "RANK -- PLAYTIME --:--"), (0x42F60B, "CLEAR DATA"),
                    (0x42F64B, "RANK %02d PLAYTIME %02d:%02d"), (0x42F38B, "(NO DATA)")],
    "Save screen: places": [(0x42F2C1, 'Motel "NO MORE HEROES"'), (0x42F2D8, "Townsend Residence"),
                            (0x42F2EB, "Destroy Stadium"), (0x42F2FB, "Santa Destroy H.S"),
                            (0x42F30D, "Bear Hug Studio"), (0x42F31D, "Body Slam Beach"),
                            (0x42F32D, "Senton Splash Tunnel"), (0x42F342, "Bow and Arrow Station"),
                            (0x42F358, "Speed City"), (0x42F363, "Stadium Basement"),
                            (0x42F374, "Forest of Bewilderment")],
    "Mission result": [(0x42CAA8, "SUCCESS"), (0x42CAB0, "FAILED")],
    "Map": [(0x430346, "MEDAL"), (0x430352, "TIME"), (0x430384, ": Move"), (0x43038B, ": Cancel"),
            (0x430394, ": Zoom In / Out"), (0x4303A4, ": Move Speed Up")],
    "Medals and missions": [(0x43082A, "NONE"), (0x43082F, "BRONZE"), (0x430836, "SILVER"), (0x43083D, "GOLD"),
                            (0x430881, "MISSION"), (0x4308A2, "YES"), (0x4308A6, "NO")]
                           + list(zip((0x4308C1, 0x4308CA, 0x4308CF), _SEL)),
    "Drawer and closet": list(zip((0x430A06, 0x430A0F, 0x430A14), _SEL))
                         + [(0x430B25, "EXIT"), (0x430B71, ": Select / Turn"), (0x430B81, ": OK"),
                            (0x430B86, ": Cancel"), (0x430B8F, ": View Reset")],
    "Shop": [(0x4310E4, ": Select / Turn"), (0x4310F4, ": Select"), (0x4310FD, ": OK"), (0x431102, ": Cancel"),
             (0x43110B, ": View Reset")] + list(zip((0x43174B, 0x431754, 0x431759), _SEL)),
    "Job board": [(0x4329FD, "Assassination Gig"), (0x432A0F, "MISSION"), (0x432A30, "EXIT"), (0x432A51, "NONE"),
                  (0x432A56, "BRONZE"), (0x432A5D, "SILVER"), (0x432A64, "GOLD"), (0x432AA8, "WORK PLACE"),
                  (0x432AB3, "REWARD"), (0x432B24, "YES"), (0x432B28, "NO")]
                 + list(zip((0x432B43, 0x432B4C, 0x432B51), _SEL)),
    "Ranking": [(0x435108, "PRESS"), (0x435128, "PRESS"), (0x4351C8, "BUTTON"), (0x4351E8, "BUTTON"),
                (0x435288, "*** RANKING LIST ***"), (0x4352A8, "*** RANKING LIST ***")],
}


def dol_strings(dol: bytes) -> list:
    """``(name, [(offset, room, text)])`` of ``DOL_BLOCKS`` that ``dol`` really has there."""
    out = []
    for name, items in DOL_BLOCKS.items():
        found = []
        for at, text in items:
            raw = text.encode("ascii") + b"\0"
            if dol[at:at + len(raw)] != raw:
                continue
            end = at + len(raw)
            while end % 4 and end < len(dol) and dol[end] == 0:
                end += 1
            found.append((at, end - at, text))
        if found:
            out.append((name, found))
    return out


def dol_text(dol: bytes) -> dict:
    return {"file": "sys/main.dol", "blocks": [{"name": name, "dol": [[a, r] for a, r, _t in found],
                                                "strings": [t for _a, _r, t in found]} for name, found in dol_strings(dol)]}


# ---------------------------------------------------------------- unpack

def _put(made: set, target: Path, blob: bytes) -> int:
    made.add(target)
    if not target.is_file() or target.read_bytes() != blob:
        atomic_write_bytes(target, blob)
    return 1


def _unpack_text_file(rel: str, lang: str, disc: DiscFiles, source: Path, harvest: Harvest, index: dict,
                      made: set) -> int:
    """One game file: its English text blocks (``text\\``), its atlases (harvested) and its pictures (``ui\\``)."""
    packed, tree, rest = rmhg.load_game_file(disc.read(rel))
    if tree is None:
        if rest[:4] == b"GCT0" and rel.startswith(UI_DIRS):
            picture = gx.gct_to_tpl(rest)
            return _put(made, source / "ui" / f"{rel}.tpl", picture) if picture else 0
        return 0
    written = 0
    chunks = dict(rmhg.leaves(tree))
    boxes = []
    for path, blob in chunks.items():
        if blob[:4] == b"GDLG":
            strings = rmhg.gdlg_strings(blob)
            shown = rmhg.gdlg_lines(blob)
            boxes.append((path, rmhg.decode_text(strings[0]) if strings else "",
                          [rmhg.decode_text(strings[i]) for i in shown]))
    blocks, used = [], set()
    for paths in english_boxes(boxes, lang):
        blob = chunks[paths[0]]
        strings = rmhg.gdlg_strings(blob)
        shown = rmhg.gdlg_lines(blob)
        if not shown:
            continue
        used.update(paths)
        blocks.append({"name": rmhg.decode_text(strings[0]) if strings else paths[0], "gdlg": paths,
                       "lines": shown, "strings": [rmhg.decode_text(strings[i]) for i in shown]})
    atlases = {}
    box_parents = {p.rsplit("/", 1)[0] for p, _n, _t in boxes}
    used_parents = {p.rsplit("/", 1)[0] for p in used}
    for path, blob in chunks.items():
        if blob[:8] not in (b"STRIMAGE", b"STRIMAG2"):
            continue
        parent = path.rsplit("/", 1)[0]
        if parent in box_parents and parent not in used_parents:
            continue                                   # the picture of another language's box
        atlas = rmhg.stri_parse(blob)
        if atlas is None or not atlas["size"] or _jp_codes(atlas["glyphs"]) \
                or not any(0x41 <= c <= 0x5A or 0x61 <= c <= 0x7A for c in atlas["glyphs"]):
            continue
        harvest.collect(rel, path, atlas)
        atlases[path] = {"font": None, "box": parent in used_parents}
    if blocks:
        body = {"file": rel, "blocks": blocks}
        written += _put(made, source / "text" / f"{rel}.nmt",
                        json.dumps(body, ensure_ascii=False, indent=1).encode("utf-8"))
    if blocks or atlases:
        index["files"][rel] = {"packed": packed, "atlases": atlases}
    if rel.startswith(UI_DIRS):
        for path, blob in chunks.items():
            if blob[:4] == b"GCT0":
                picture = gx.gct_to_tpl(blob)
                if picture:
                    written += _put(made, source / "ui" / rel / f"{path.strip('/')}.tpl", picture)
    return written


def _unpack_loose(disc: DiscFiles, source: Path, made: set) -> int:
    """The Wii HOME Menu messages and pictures, and the channel banner pictures."""
    loose: Dict[str, bytes] = {}
    for name in ("home.csv", "home_nosave.csv"):
        loose[f"hbm/{name}"] = disc.read(f"{HBM}/{name}")
    archives.explode(disc.read(f"{HBM}/homeBtn_ENG.arc"), "hbm/homeBtn_ENG.arc", loose.__setitem__)
    archives.explode(disc.read("opening.bnr"), "opening.bnr", loose.__setitem__)
    return sum(_put(made, source / rel, blob) for rel, blob in loose.items())


def unpack_disc(disc: DiscFiles, target: Path, progress: Callable[[int, str], None],
                is_cancelled: Callable[[], bool]) -> dict | None:
    """Write the ``source`` tree and ``INDEX`` into ``target``; None when cancelled."""
    source = target / SOURCE
    names = sorted(r for r in disc.files if _wanted(r))
    name_set = set(names)
    harvest = Harvest()
    index: dict = {"files": {}, "fonts": {}}
    written = 0
    made: set = set()
    for n, rel in enumerate(names):
        if is_cancelled():
            return None
        progress(int(100 * n / max(1, len(names))) // 2, rel)
        lang = file_language(rel, name_set)
        if lang != "other":
            written += _unpack_text_file(rel, lang, disc, source, harvest, index, made)
    fonts, keys, meta = harvest.assign()
    for (rel, path), key in keys.items():
        index["files"][rel]["atlases"][path]["font"] = key
    index["fonts"] = write_fonts(source, fonts, meta)
    written += len(index["fonts"])
    written += _put(made, source / "text" / "main.dol.nmt",
                    json.dumps(dol_text(disc.dol()), ensure_ascii=False, indent=1).encode("utf-8"))
    written += _unpack_loose(disc, source, made)
    for folder in ("text", "ui"):                       # what an older unpack left and this one did not make
        for stale in (source / folder).rglob("*") if (source / folder).is_dir() else []:
            if stale.is_file() and stale not in made:
                stale.unlink()
    atomic_write_bytes(target / INDEX, json.dumps(index, ensure_ascii=False).encode("utf-8"))
    progress(100, "")
    return {"files": written, "fonts": len(index["fonts"])}
