"""Wind Waker HD: the English message pack unpacked into the project's source root.

The pack is a plain SARC. A message or font file is a member ``X_msbt.szs`` / ``X_msbp.szs`` / ``X_bffnt.szs``: a
Yaz0 SARC that holds ``X.msbt`` / ``X.msbp`` / ``X.bffnt``. The unpack writes ``Message/``, ``Font/``, the pack itself
into ``Pack/``, and the game's layouts (``content/Common/Layout``, optional) into ``Layout/`` -- the same folders the
workspace's unpack makes, so the project's font and texture sources resolve. A .wua (Cemu archive) or .wux (encrypted
disc image) is not read; the wizard needs the extracted game folder or the pack file.
"""
from pathlib import Path
from typing import Callable, Optional

from core.containers import yaz0
from core.containers.sarc import Sarc
from core.i18n import tr

PACK_FILE = "permanent_2d_UsEnglish.pack"
GAME_PACK_REL = Path("content", "Common", "Pack", PACK_FILE)
GAME_LAYOUT_REL = Path("content", "Common", "Layout")
MESSAGE_FOLDER = "Message"
FONT_FOLDER = "Font"
PACK_FOLDER = "Pack"
LAYOUT_FOLDER = "Layout"
_FOLDER_BY_EXT = {"msbt": MESSAGE_FOLDER, "msbp": MESSAGE_FOLDER, "bffnt": FONT_FOLDER}


def is_english_pack(path: str) -> bool:
    """True for the English pack file, by its name and its SARC header."""
    file_path = Path(path)
    if file_path.name.lower() != PACK_FILE.lower() or not file_path.is_file():
        return False
    try:
        with open(file_path, "rb") as stream:
            return stream.read(4) == b"SARC"
    except OSError:
        return False


def pack_of(path: str) -> Optional[Path]:
    """The English pack a chosen file or game folder holds, or None."""
    chosen = Path(path)
    if chosen.is_dir():
        candidate = chosen / GAME_PACK_REL
        return candidate if is_english_pack(str(candidate)) else None
    return chosen if is_english_pack(path) else None


def unpack_messages(path: str, target_dir: str, progress: Callable[[int, str], None],
                    is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the pack's files into ``target_dir``; return ``target_dir``, or None on cancel."""
    chosen = Path(path)
    pack_path = pack_of(path)
    if pack_path is None:
        raise ValueError(tr("{0} is not a Wind Waker HD message pack. Use the extracted {1}.",
                            chosen.name, PACK_FILE))
    raw = pack_path.read_bytes()
    pack = Sarc(raw)
    members = sorted(name for name in pack.files if name.rsplit("_", 1)[-1] in
                     ("msbt.szs", "msbp.szs", "bffnt.szs"))
    if not members:
        raise ValueError(tr("The pack {0} holds no message files.", pack_path.name))
    target = Path(target_dir)
    for done, member in enumerate(members, start=1):
        if is_cancelled():
            return None
        inner = Sarc(yaz0.decompress(pack.files[member]))
        for name, data in inner.files.items():
            ext = name.rsplit(".", 1)[-1]
            if Path(name).name != name or ext not in _FOLDER_BY_EXT:
                continue
            folder = target / _FOLDER_BY_EXT[ext]
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(data)
        progress(100 * done // len(members), member)
    if is_cancelled():
        return None
    (target / PACK_FOLDER).mkdir(parents=True, exist_ok=True)
    (target / PACK_FOLDER / PACK_FILE).write_bytes(raw)
    layout_dir = _layout_folder(chosen, pack_path)
    layouts = sorted(layout_dir.glob("*.szs")) if layout_dir is not None and layout_dir.is_dir() else []
    if layouts:
        (target / LAYOUT_FOLDER).mkdir(parents=True, exist_ok=True)
    for layout in layouts:
        (target / LAYOUT_FOLDER / layout.name).write_bytes(layout.read_bytes())
    return target_dir


def _layout_folder(chosen: Path, pack_path: Path) -> Optional[Path]:
    """The game's layout folder: under the chosen game folder, or above a pack that sits in content\\Common\\Pack."""
    if chosen.is_dir():
        return chosen / GAME_LAYOUT_REL
    depth = len(GAME_PACK_REL.parts) - 1
    parents = list(pack_path.parents)
    return parents[depth] / GAME_LAYOUT_REL if len(parents) > depth else None
