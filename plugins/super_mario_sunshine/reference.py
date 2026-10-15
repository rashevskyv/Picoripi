"""Super Mario Sunshine: the European disc (GMSP01) as five reference languages beside each US message.

The European disc keeps each message file once per language (``en``, ``fr``, ``ge``, ``sp``, ``it``). Measured on the
retail disc, a US file ``<archive>.szs/<member>`` has its language ``L`` copy at:

* ``scene/<x>.szs/map/message.bmg`` -> ``scene/<x>.szs/map/message_L.bmg`` (and ``option.szs/loadmessage_L.bmg``);
* ``scene/test11.szs/map/<name>.bmg`` -> ``scene/test11.szs/map/_L/<name>.bmg``;
* ``guide.szs``, ``subtitle.szs`` -> ``guide_L.szs``, ``subtitle_L.szs`` (same member);
* ``common.szs/2d/<name>.bmg`` -> ``cmn2d_L.szs/<name>.bmg``.

The four Japanese ``pinnaBeach*/map/dolpic1.bmg`` and ``title.szs/marisun_stage.bmg`` (the same file on both discs)
have no language copies. The European files add an STR1 section (message names), so only INF1 and DAT1 are read.
Messages match by number; a file whose count differs (``loadmessage``: 35 US, 36 European) is matched by its English
text, and that pairing serves every language. ``unpack`` writes only the disc's BMG files into the project
(``reference_eu``, the folder layout of the US unpack); the editor only reads that folder.
"""
from __future__ import annotations

import difflib
import os
import shutil
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core.containers import yaz0
from core.containers.rarc_container import RarcContainer
from core.i18n import tr
from core.project_library import images
from plugins.zelda_bmg.bmg_tool import BMGFile

from .build import _section, _write, archive_split

GAME_ID = "GMSP01"
FOLDER = "reference_eu"
LANGUAGES = (("en", "English (EU)"), ("fr", "French (FR)"), ("ge", "German (DE)"), ("sp", "Spanish (ES)"),
             ("it", "Italian (IT)"))

Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]


def is_european_disc(path: str | os.PathLike) -> bool:
    found = images.identify(path)
    return bool(found) and found["kind"] == images.KIND_GC and found["game_id"] == GAME_ID


def unpack(image: str | os.PathLike, project_dir: str | os.PathLike, progress: Progress,
           is_cancelled: Cancelled) -> Optional[str]:
    """Write the BMG files of the European disc ``image`` into ``project_dir/reference_eu`` and return that folder.

    None when cancelled. The folder is written beside its final name and replaces an older one only when complete.
    Raises ValueError for any other image. The disc is only read.
    """
    if not is_european_disc(image):
        raise ValueError(tr("Not the European Super Mario Sunshine disc (GMSP01): {0}", str(image)))
    final = Path(project_dir) / FOLDER
    temporary = final.with_name(f".{FOLDER}-{uuid.uuid4().hex}")
    try:
        with images.open_image(image) as reader:
            archives = [e for e in reader.entries() if e.path.startswith("files/data/") and e.path.endswith(".szs")]
            for number, entry in enumerate(archives):
                if is_cancelled():
                    shutil.rmtree(temporary, ignore_errors=True)
                    return None
                progress(100 * number // len(archives), entry.path)
                raw = reader.read(entry)
                data = yaz0.decompress(raw) if raw[:4] == b"Yaz0" else raw
                if data[:4] != b"RARC":
                    continue
                container = RarcContainer(data)
                for name in container.list_files():
                    if name.lower().endswith(".bmg"):
                        _write(temporary / entry.path / name, container.read_file(name))
        old = final.with_name(f".{FOLDER}-old-{uuid.uuid4().hex}")
        if final.exists():
            os.replace(final, old)
        os.replace(temporary, final)
        shutil.rmtree(old, ignore_errors=True)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    progress(100, "")
    return str(final)


def european_paths(rel: str, lang: str) -> List[str]:
    """Where the European disc keeps the ``lang`` copy of the US message file ``rel`` (slash paths, first wins)."""
    split = archive_split(rel)
    if split is None:
        return []
    archive, member = split
    folder, _, name = member.rpartition("/")
    stem, _, ext = name.rpartition(".")
    prefix = f"{folder}/" if folder else ""
    paths = [f"{archive}/{prefix}{stem}_{lang}.{ext}", f"{archive}/{prefix}_{lang}/{name}",
             f"{archive[:-len('.szs')]}_{lang}.szs/{member}"]
    if archive.endswith("data/common.szs") and folder == "2d":
        paths.append(f"{archive[:-len('common.szs')]}cmn2d_{lang}.szs/{name}")
    return paths


def read_texts(path: Path) -> Optional[List[str]]:
    """The messages of a BMG file as the disc has them (escapes as ``{escape:type:hex}``), or None when it is missing
    or does not parse. The letters are not decoded with the Ukrainian map: é stays é."""
    try:
        data = path.read_bytes()
        inf1, dat1 = _section(data, b"INF1"), _section(data, b"DAT1")
        if inf1 is None or dat1 is None:
            return None
        bmg = BMGFile()
        bmg.load(data[:0x20] + inf1 + dat1)   # BMGFile reads STR1 as another game's layout: leave it out
    except (OSError, ValueError, IndexError):
        return None
    return ["".join(part if isinstance(part, str) else f"{{escape:{part['escape_type']}:{part['data']}}}"
                    for part in message.parts) for message in bmg.messages]


def pairing(us: List[str], english: List[str]) -> Dict[int, int]:
    """``{US message: European message}``: by number when the counts match, otherwise by the English text (equal runs,
    and changed runs of the same length)."""
    if len(us) == len(english):
        return {index: index for index in range(len(us))}
    pairs: Dict[int, int] = {}
    for tag, a0, a1, b0, b1 in difflib.SequenceMatcher(None, us, english, autojunk=False).get_opcodes():
        if tag == "equal" or (tag == "replace" and a1 - a0 == b1 - b0):
            pairs.update(zip(range(a0, a1), range(b0, b1)))
    return pairs


def load_languages(root: Path, blocks: Dict[int, Tuple[str, Path]],
                   to_editor: Callable[[str], str]) -> Dict[str, Dict[Tuple[int, int], str]]:
    """``{label: {(block, message): text}}`` from a ``reference_eu`` folder, English (EU) first.

    ``blocks`` maps a project block to ``(its source path in the unpacked tree, its US file)``. ``to_editor`` turns
    the escapes into the editor's tag aliases.
    """
    result: Dict[str, Dict[Tuple[int, int], str]] = {label: {} for _lang, label in LANGUAGES}
    for block, (rel, us_file) in blocks.items():
        found = {}
        for lang, label in LANGUAGES:
            path = next((root / p for p in european_paths(rel, lang) if (root / p).is_file()), None)
            texts = read_texts(path) if path else None
            if texts is not None:
                found[label] = texts
        english = found.get(LANGUAGES[0][1])
        us = read_texts(us_file) if english is not None else None
        if us is None:
            continue
        pairs = pairing(us, english)
        for label, texts in found.items():
            if len(texts) != len(english):
                continue   # a language that does not share the English file's messages
            for us_index, eu_index in pairs.items():
                result[label][(block, us_index)] = to_editor(texts[eu_index])
    return {label: texts for label, texts in result.items() if texts}
