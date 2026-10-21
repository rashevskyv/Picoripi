"""Unpack Yo-kai Watch 1 in the Project Manager wizard: text, fonts, menu textures and speaker tables of its ARC0 archives.

The 3DS game (USA) keeps everything in ``romfs/yw1_a.fa``. The Switch game (Japanese) keeps it in the base game's
``yw1_a.fa`` and the update's ``yw1_1_1.fa``; the game reads the update's files in place of the base archive's. The
update's RomFS is a BKTR patch over the base RomFS, and Picoripi's Switch reader applies it. The archives are read in
place in the image (the Switch base archive is 3.4 GB), and the selected members are written as they are stored:
``source/<member>`` is the project's source (``get_source_subfolder``), and ``meta/<member>`` holds the tables the
speaker lookup reads beside it. This is the layout of the owner's workspaces (zt ``level5.py``, ``level5nx.py``).
"""
from typing import Any, Callable, Dict, List, Optional

from core.containers.console_crypto import RangeView
from core.containers.image_files import ImageError, ImageFile, check_name
from core.i18n import tr
from core.project_library import images

from .arc0 import Arc0
from .speakers import GAMES

SWITCH_BASE = "0100C0000CEEA000"
SWITCH_UPDATE = "0100C0000CEEA800"
N3DS_GAMES = ("AYWE",)                       # Yo-kai Watch (USA)
SOURCE, META = "source", "meta"
# The archives of each platform; a member of a later archive replaces the same member of an earlier one.
ARCHIVES = {"3ds": ("romfs/yw1_a.fa",), "switch": ("romfs/yw1_a.fa", "romfs/yw1_1_1.fa")}
LANG = {"3ds": GAMES["yw1"]["lang"], "switch": GAMES["ywnx"]["lang"]}


def identify(path: str) -> Optional[Dict[str, Any]]:
    """``{"role", "platform"}`` of a Yo-kai Watch 1 image (3DS USA, Switch base or update), else None."""
    found = images.identify(path)
    if found is None:
        return None
    if found["kind"] == images.KIND_3DS and found["game_id"] in N3DS_GAMES:
        return {"role": "base", "platform": "3ds"}
    if found["kind"] == images.KIND_SWITCH and found["game_id"] in (SWITCH_BASE, SWITCH_UPDATE):
        return {"role": "base" if found["game_id"] == SWITCH_BASE else "update", "platform": "switch"}
    return None


def folder_of(member: str, platform: str) -> Optional[str]:
    """``meta`` for a speaker table, ``source`` for a text table, font or menu texture, None for any other member."""
    name = member.rsplit("/", 1)[-1]
    if ((member.startswith("data/txt/ev/") and "_map" in name) or member.startswith("data/res/character/chara_base")
            or (member.startswith("data/res/map/")
                and any(key in name for key in ("_npc_set_", "_npc_base_talk_", "_npc_talk_")))):
        return META
    lang = LANG[platform]
    if member.endswith(f"{lang}.cfg.bin") or (member.startswith("fnt/") and member.endswith(".xf")):
        return SOURCE
    if member.endswith(".cfg.bin"):
        return None
    if platform == "switch":
        texture = member.startswith("data/menu/") and member.endswith((".xi", ".xa"))
    else:   # the English images: .../en/..., *_en.xa, *_en_f.xa
        code = lang.strip("_")
        texture = f"/{code}/" in member or f"_{code}." in member or f"_{code}_" in name
    return SOURCE if texture else None


def unpack(sources: Dict[str, str], target_dir: str, progress: Callable[[int, str], None],
           is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write ``source/`` and ``meta/`` into ``target_dir`` and return it; None when the user cancelled.

    None too when the base file is no Yo-kai Watch 1 image (another game of the series, a folder): the host then
    uses it as it is or refuses the image. Raises ImageError when the Switch update is missing.
    """
    base, update = sources.get("base"), sources.get("update")
    found = identify(base) if base else None
    if found is None or found["role"] != "base":
        return None
    if found["platform"] == "3ds":
        with images.open_image(base, target_dir, is_cancelled, progress) as reader:
            return write_archives(reader, reader.entries(), "3ds", target_dir, progress, is_cancelled)
    if not update:
        raise ImageError(tr("Choose the update file too: the game reads its newest files from the update."))
    # The cache of a compressed (.nsz) image is a folder of the target: the reader deletes its copy on close.
    with images.open_image(base, target_dir, is_cancelled, progress) as base_reader, \
            images.open_image(update, target_dir, is_cancelled, progress) as update_reader:
        entries = update_reader.patched_romfs_entries(base_reader)
        return write_archives(update_reader, entries, "switch", target_dir, progress, is_cancelled)


def write_archives(reader, entries: List[ImageFile], platform: str, target_dir: str,
                   progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[str]:
    """Write the selected members of the platform's archives (found in ``entries``) into ``target_dir``."""
    by_path = {entry.path: entry for entry in entries}
    members: Dict[str, ImageFile] = {}
    for name in ARCHIVES[platform]:
        entry = by_path.get(name)
        if entry is None:
            raise ImageError(tr("The image has no {0}.", name))
        view = RangeView(reader.source(entry), entry.offset, entry.size)
        try:
            archive = Arc0(view, is_cancelled)
        except ValueError as exc:   # a broken index (an ImageError of the image reader is a ValueError too)
            raise ImageError(tr("The archive {0} cannot be read: {1}", name, str(exc))) from None
        for member, (offset, size) in archive.files.items():
            members[member] = ImageFile(member, archive.data + offset, size, None, view)
    if is_cancelled():
        return None
    wanted = []
    for member, file in sorted(members.items()):
        folder = folder_of(member, platform)
        if folder:
            for part in member.split("/"):
                check_name(part)
            wanted.append(file._replace(path=f"{folder}/{member}"))
    progress(0, tr("Writing {0} files", str(len(wanted))))
    return target_dir if images.write_entries(reader, wanted, target_dir, progress, is_cancelled) else None
