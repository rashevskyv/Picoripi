"""Super Mario Galaxy 1 and 2 builds: one translation (``Message.smgmsg``, by label) written into each version.

* ``wii_riivolution``: a Riivolution patch (``riivolution/<mod>.xml`` and the files) for the USA Wii disc, plus a
  Dolphin game-mod descriptor (``<mod>.json``) that boots the disc with the patch.
* ``nebula`` (Super Mario Galaxy only): a disc-mod manifest for the Nebula recompilation
  (``GALAXY_DISC_MOD_MANIFEST``): byte ranges of its ``game.pak``, the plain data partition of RMGE01. A file that
  grew moves into free space before the first file of the disc, and the file system table is overridden to point at
  it. Nebula loads its own loose ``content\\sys\\fst.bin`` at boot, so the build's ``sys/fst.bin`` replaces that copy
  too (``README.txt`` of the build; measured: the manifest alone left the English text).
* ``switch_layeredfs``: ``atmosphere/contents/<title id>/romfs`` with every English slot.

A file the translation folder holds under ``versions/<version>/`` (a font saved by the font editor, or one imported
from a mod) replaces that version's file. A message archive there is the base the text goes into: a mod made for a
game update brings the update's archive (labels the base game lacks), which Picoripi cannot read from the update
itself. Each version gets the labels it has; the button pictures (tag group 3) move to the Switch numbers for the
messages that came from the Wii text.
"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from core.i18n import tr
from utils.atomic_io import atomic_write_bytes

from . import messages
from .unpack import (DOCUMENT_DIR, DOCUMENT_SUFFIX, GAMES, MESSAGE_DIR, SWITCH, VERSIONS, WII, document_rel,
                     english_slots, english_versions, game_of)

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]

NEBULA_MAIN_DOL_SHA1 = "9a71008ae1ee9010e267fa67d1f0b0d4f0e895dd"   # RMGE01 rev 0, the only main.dol Nebula accepts
APPLOADER_AT = 0x2440
FST_ENTRY = 12
PLACE_ALIGN = 0x8000


def _game(source_dir: str) -> Dict[str, object]:
    game = game_of(Path(source_dir))
    if game is None:
        raise ValueError(tr("The project's source has no Super Mario Galaxy version."))
    return GAMES[game]


def mod_name(source_dir: str) -> str:
    return str(_game(source_dir)["name"]).replace(" ", "") + "UA"


def documents(source_dir: str, translation_dir: str) -> Dict[str, List[Dict[str, object]]]:
    """``{archive stem: rows}`` of every message document: the translated copy, or the source one when there is none."""
    found = {}
    for path in sorted((Path(source_dir) / DOCUMENT_DIR).glob(f"*{DOCUMENT_SUFFIX}")):
        stem = path.name[:-len(DOCUMENT_SUFFIX)]
        translated = Path(translation_dir) / document_rel(stem) if translation_dir else None
        for candidate in (translated, path):
            rows = messages.read_document(candidate.read_bytes()) if candidate and candidate.is_file() else None
            if rows is not None:
                found[stem] = rows
                break
    if not found:
        raise ValueError(tr("The project has no message documents ({0}).", f"{DOCUMENT_DIR}/*{DOCUMENT_SUFFIX}"))
    return found


def texts_for(version: str, stem: str, rows: List[Dict[str, object]], source_dir: str) -> Dict[str, str]:
    """``{label: text}`` of one archive for one version: the rows it has, with the Wii button pictures moved to the
    Switch numbers."""
    pairs = {}
    if version == SWITCH:
        english = dict(english_versions(Path(source_dir), stem))
        if WII in english and SWITCH in english:
            pairs = messages.picture_pairs(english[WII], english[SWITCH])
    out = {}
    for row in rows:
        present = row.get("in") or []
        if version not in present:
            continue
        text, label = str(row.get("text", "")), str(row["label"])
        if pairs and WII in present:
            text = messages.swap_pictures(text, label, pairs)
        out[label] = text
    return out


def overrides(translation_dir: str, version: str) -> Dict[str, Path]:
    """The files of ``translation_dir/versions/<version>`` by their path inside the version."""
    root = Path(translation_dir) / VERSIONS / version
    if not translation_dir or not root.is_dir():
        return {}
    return {path.relative_to(root).as_posix(): path for path in root.rglob("*") if path.is_file()}


def version_files(version: str, source_dir: str, translation_dir: str, progress: Progress) -> Dict[str, bytes]:
    """``{path inside the version: bytes}``: every message archive of each English slot, translated, then the
    overrides."""
    base = Path(source_dir) / VERSIONS / version
    slots = english_slots(Path(source_dir), version)
    if not slots:
        raise ValueError(tr("The project has no {0} version: add its game file and unpack again.", version))
    docs = documents(source_dir, translation_dir)
    english = {stem: {row["label"]: row.get("text") for row in rows} for stem, rows in documents(source_dir, "").items()}
    # only the translated rows: an untouched row keeps each version's own English (the Switch rewords some messages)
    docs = {stem: [row for row in rows if row.get("text") != english.get(stem, {}).get(row["label"])]
            for stem, rows in docs.items()}
    texts = {stem: texts_for(version, stem, rows, source_dir) for stem, rows in docs.items()}
    replaced = overrides(translation_dir, version)
    jobs = [f"{slot}/{MESSAGE_DIR}/{stem}.arc" for slot in slots for stem in docs]
    jobs = [rel for rel in jobs if rel in replaced or (base / rel).is_file()]
    out: Dict[str, bytes] = {}
    for number, rel in enumerate(jobs):
        progress(5 + 90 * number // len(jobs), rel)
        original = replaced.get(rel, base / rel)   # an archive of a newer game update, from the import, wins
        data, wanted = original.read_bytes(), texts[Path(rel).stem]
        if rel not in replaced:
            current = messages.texts_by_label(data)
            if all(current.get(key) == text for key, text in wanted.items()):
                continue   # nothing translated in this archive: the game's own file stays
        out[rel] = messages.apply_texts(data, wanted)
    for rel, path in replaced.items():
        if rel not in out and rel != "source.json":
            out[rel] = path.read_bytes()
    return out


def disc_files(source_dir: str, translation_dir: str, progress: Progress) -> Dict[str, bytes]:
    """The Wii version's translated files by their path on the disc (under ``files/``)."""
    return {rel[len("files/"):]: data for rel, data in version_files(WII, source_dir, translation_dir, progress).items()
            if rel.startswith("files/")}


def _write(folder: Path, files: Dict[str, bytes]) -> None:
    for rel, data in files.items():
        atomic_write_bytes(folder.joinpath(*rel.split("/")), data)


# -- Wii: Riivolution ---------------------------------------------------------------------------------------------

def riivolution_xml(name: str, game: str, disc_paths: List[str]) -> str:
    """A Riivolution patch for the USA disc of ``game`` (its three-letter id) that replaces ``disc_paths``."""
    lines = "\n".join(f'\t\t<file disc="/{path}" external="{path}" />' for path in disc_paths)
    return (
        '<wiidisc version="1">\n'
        f'\t<id game="{game}">\n\t\t<region type="E" />\n\t</id>\n'
        f'\t<options>\n\t\t<section name="{name}">\n'
        '\t\t\t<option name="Ukrainian translation" default="1">\n'
        f'\t\t\t\t<choice name="On"><patch id="{name}" /></choice>\n'
        '\t\t\t</option>\n\t\t</section>\n\t</options>\n'
        f'\t<patch id="{name}" root="/{name}">\n{lines}\n\t</patch>\n'
        '</wiidisc>\n')


def build_wii_riivolution(source_dir: str, translation_dir: str, output_dir: str, progress: Progress,
                          is_cancelled: Cancelled) -> str:
    game, name = _game(source_dir), mod_name(source_dir)
    disc = disc_files(source_dir, translation_dir, progress)
    out = Path(output_dir)
    _write(out / name, disc)
    xml = out / "riivolution" / f"{name}.xml"
    atomic_write_bytes(xml, riivolution_xml(name, str(game["wii_prefix"]), sorted(disc)).encode("utf-8"))
    image = json.loads((Path(source_dir) / VERSIONS / WII / "source.json").read_text(encoding="utf-8"))["image"]
    descriptor = {"type": "dolphin-game-mod-descriptor", "version": 1, "base-file": image,
                  "display-name": f"{game['name']} (UA)",
                  "riivolution": {"patches": [{
                      # relative to this file: Dolphin resolves them from its folder, so the build can move
                      "xml": f"riivolution/{name}.xml", "root": ".",
                      "options": [{"section-name": name, "option-name": "Ukrainian translation", "choice": 1}]}]}}
    atomic_write_bytes(out / f"{name}.json", json.dumps(descriptor, indent=1).encode("utf-8"))
    progress(100, "")
    return str(out)


# -- Nebula: byte ranges of the plain data partition ---------------------------------------------------------------

def fst_files(fst: bytes) -> Dict[str, Tuple[int, int, int]]:
    """``{path: (entry index, partition offset, size)}`` of a Wii FST (file offsets stored divided by 4)."""
    count = struct.unpack_from(">I", fst, 8)[0]
    names = count * FST_ENTRY
    found: Dict[str, Tuple[int, int, int]] = {}
    folders: List[Tuple[int, str]] = []   # (index after the folder's last entry, the folder's path)
    for index in range(1, count):
        while folders and index >= folders[-1][0]:
            folders.pop()
        prefix = folders[-1][1] if folders else ""
        word, offset, size = struct.unpack_from(">III", fst, index * FST_ENTRY)
        at = names + (word & 0xFFFFFF)
        name = fst[at:fst.index(b"\0", at)].decode("shift_jis", "replace")
        if word >> 24:
            folders.append((size, f"{prefix}{name}/"))
        else:
            found[prefix + name] = (index, offset << 2, size)
    return found


def place(fst: bytes, used: List[Tuple[int, int]], changed: Dict[str, int]) -> Tuple[bytes, Dict[str, int]]:
    """The FST with each changed file's size set, and ``{path: partition offset}``. A file that still fits stays;
    a grown one goes into the first free gap (``PLACE_ALIGN``) between ``used`` areas and the files."""
    files = fst_files(fst)
    out = bytearray(fst)
    taken = sorted(used + [(offset, offset + size) for _index, offset, size in files.values()])
    placed: Dict[str, int] = {}
    for path, size in sorted(changed.items()):
        if path not in files:
            raise ValueError(tr("The disc has no file {0}.", path))
        index, offset, old = files[path]
        if size > old:
            offset = _gap(taken, size)
            taken = sorted(taken + [(offset, offset + size)])
        struct.pack_into(">II", out, index * FST_ENTRY + 4, offset >> 2, size)
        placed[path] = offset
    return bytes(out), placed


def _gap(taken: List[Tuple[int, int]], size: int) -> int:
    end = 0
    for start, stop in taken:
        candidate = -(-end // PLACE_ALIGN) * PLACE_ALIGN
        if start - candidate >= size:
            return candidate
        end = max(end, stop)
    raise ValueError(tr("No free space in the disc for a file of {0} bytes.", str(size)))


def build_nebula(source_dir: str, translation_dir: str, output_dir: str, progress: Progress,
                 is_cancelled: Cancelled) -> str:
    if not _game(source_dir)["nebula"]:
        raise ValueError(tr("Nebula runs only Super Mario Galaxy."))
    wii = Path(source_dir) / VERSIONS / WII
    dol = (wii / "sys/main.dol").read_bytes()
    if hashlib.sha1(dol).hexdigest() != NEBULA_MAIN_DOL_SHA1:
        raise ValueError(tr("Nebula runs only the USA disc revision 0 (its main.dol): this project has another."))
    boot = (wii / "sys/boot.bin").read_bytes()
    dol_at, fst_at = (struct.unpack_from(">I", boot, at)[0] << 2 for at in (0x420, 0x424))
    fst = (wii / "sys/fst.bin").read_bytes()
    files = disc_files(source_dir, translation_dir, progress)
    used = [(0, APPLOADER_AT + (wii / "sys/apploader.img").stat().st_size), (dol_at, dol_at + len(dol)),
            (fst_at, fst_at + len(fst))]
    new_fst, placed = place(fst, used, {path: len(data) for path, data in files.items()})
    out = Path(output_dir)
    lines = ["version 1", "game RMGE01", f"main_dol_sha1 {NEBULA_MAIN_DOL_SHA1}",
             f"0x{fst_at:x} {len(new_fst)} sys/fst.bin"]
    _write(out, {"sys/fst.bin": new_fst})
    for path, data in sorted(files.items()):
        _write(out, {f"files/{path}": data})
        lines.append(f"0x{placed[path]:x} {len(data)} files/{path}")
    atomic_write_bytes(out / "manifest.txt", ("\n".join(lines) + "\n").encode("ascii"))
    atomic_write_bytes(out / "README.txt", NEBULA_README.encode("utf-8"))
    progress(100, "")
    return str(out / "manifest.txt")


NEBULA_README = """Super Mario Galaxy (UA) for Nebula

1. Keep a copy of <Nebula>\\content\\sys\\fst.bin, then copy sys\\fst.bin of this folder over it. Nebula reads that
   file when the game starts; it points the translated files at their new place on the disc.
2. Start NebulaRuntime.exe with GALAXY_DISC_MOD_MANIFEST set to manifest.txt of this folder (or add that variable to
   Nebula's runtime-env.json).
To go back to English, put the saved fst.bin back and remove the variable.
"""


# -- Switch: LayeredFS ---------------------------------------------------------------------------------------------

def build_switch(source_dir: str, translation_dir: str, output_dir: str, progress: Progress,
                 is_cancelled: Cancelled) -> str:
    files = version_files(SWITCH, source_dir, translation_dir, progress)
    _write(Path(output_dir) / "atmosphere" / "contents" / str(_game(source_dir)["switch"]), files)
    progress(100, "")
    return str(Path(output_dir) / "atmosphere")
