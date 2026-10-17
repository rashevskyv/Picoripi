"""Wind Waker HD: the Cemu graphic pack of a project (text and fonts repacked into the game's message pack).

The source root is the unpacked tree: ``Pack/permanent_2d_UsEnglish.pack`` (the base), ``Message/*.msbt``,
``Font/*.bffnt`` and ``Layout/*.szs``. A file X.msbt lives in the pack as ``X_msbt.szs`` (a Yaz0 SARC holding
X.msbt); X.bffnt as ``X_bffnt.szs``. The translation folder holds the files that changed; each replaces its
member. The output is ``graphicPacks/Picoripi_UA_WWHD/`` (``rules.txt`` and ``content/``), which Cemu loads.
"""
from pathlib import Path
from typing import Callable

from core.containers import yaz0
from core.containers.sarc import Sarc

TITLE_ID = "0005000010143500"
PACK_FILE = "permanent_2d_UsEnglish.pack"
PACK_REL = f"Common/Pack/{PACK_FILE}"
LAYOUT_REL = "Common/Layout"
GRAPHIC_PACK_NAME = "Picoripi_UA_WWHD"
CHANGEABLE_FOLDERS = ("Message", "Font")
RULES_TXT = f"""[Definition]
titleIds = {TITLE_ID}
name = Picoripi UA
path = "The Legend of Zelda: The Wind Waker HD/Mods/Picoripi UA"
description = Ukrainian translation (text, fonts and textures) built by Picoripi from the project's files.
version = 7
"""


def member_of(rel: str) -> tuple:
    """``Message/message.msbt`` -> (``message_msbt.szs``, ``message.msbt``)."""
    name = Path(rel).name
    stem, ext = name.rsplit(".", 1)
    return f"{stem}_{ext}.szs", name


def repack_member(original: bytes, name: str, data: bytes) -> bytes:
    """The Yaz0 SARC ``original`` with its one file replaced, compressed again (its header fields kept)."""
    inner = Sarc(yaz0.decompress(original))
    inner.files[name] = data
    packed = bytearray(yaz0.compress(inner.build()))
    packed[8:16] = original[8:16]
    return bytes(packed)


def build(source: Path, translation: Path, out: Path, progress: Callable[[int, str], None],
          is_cancelled: Callable[[], bool]) -> Path:
    """Write the graphic pack into ``out``; return its folder. Stops early (partial result) when cancelled."""
    base = translation / "Pack" / PACK_FILE
    if not base.is_file():
        base = source / "Pack" / PACK_FILE
    if not base.is_file():
        raise ValueError(f"The project has no Pack\\{PACK_FILE}: unpack the game first.")
    pack = Sarc(base.read_bytes())
    changed = []
    for folder in CHANGEABLE_FOLDERS:
        for path in sorted((translation / folder).glob("*.*") if (translation / folder).is_dir() else []):
            rel = f"{folder}/{path.name}"
            source_copy = source / rel
            if source_copy.is_file() and source_copy.read_bytes() == path.read_bytes():
                continue
            changed.append((rel, path))
    gp = out / "graphicPacks" / GRAPHIC_PACK_NAME
    for index, (rel, path) in enumerate(changed, start=1):
        if is_cancelled():
            return gp
        member, name = member_of(rel)
        if member not in pack.files:
            raise ValueError(f"{rel}: the pack has no {member}")
        pack.files[member] = repack_member(pack.files[member], name, path.read_bytes())
        progress(100 * index // max(1, len(changed)), rel)
    pack_out = gp / "content" / "Common" / "Pack"
    pack_out.mkdir(parents=True, exist_ok=True)
    (pack_out / PACK_FILE).write_bytes(pack.build())
    layouts = sorted((translation / "Layout").glob("*.szs")) if (translation / "Layout").is_dir() else []
    if layouts:
        layout_out = gp / "content" / LAYOUT_REL
        layout_out.mkdir(parents=True, exist_ok=True)
        for path in layouts:
            (layout_out / path.name).write_bytes(path.read_bytes())
    (gp / "rules.txt").write_text(RULES_TXT, encoding="utf-8")
    return gp
