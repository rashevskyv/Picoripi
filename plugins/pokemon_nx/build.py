"""Build the Pokémon Sword / Shield or Legends: Arceus mod: the changed files as a LayeredFS romfs.

A changed file of the translation goes to its romfs path (``plugins.common.romfs_mod``). A changed file of a pack's
``<pack>.gfpak.d`` folder goes back into its ``.gfpak``: the pack is written again with that entry as an Oodle block
(kind 3, the library's Kraken compressor), the other entries keep their bytes (``core.containers.gfpak.replace_stored``).

Sword and Shield share one romfs, so the mod is written for both title ids. Legends: Arceus has one title id. The game
is told by the source: a pack (``.gfpak``) in the source means Legends: Arceus.
"""
import re
from pathlib import Path
from typing import Callable, Dict, List

from core.containers import console_crypto, gfpak
from core.i18n import tr
from core.unreal.oodle import Oodle, OodleError
from plugins.common import romfs_mod

SWORD_SHIELD_TITLES = ("0100ABF008968000", "01008DB008C2C000")   # Pokémon Sword, Pokémon Shield
ARCEUS_TITLES = ("01001F5010DFA000",)                            # Pokémon Legends: Arceus
MOD_DIR = "atmosphere"
OODLE_SLOT = "oodle"   # the console_keys slot of the Oodle core library (the unpack asks for it the same way)
PACK_FOLDER = re.compile(r"^(.+\.gfpak)\.d/(\d+)[_.]")


def _oodle_compressor() -> Callable[[bytes], bytes]:
    """The Oodle library's Kraken compressor; the library path comes from the console key store (slot ``oodle``)."""
    path = console_crypto.key_path(OODLE_SLOT)
    if not path:
        raise ValueError(tr("The Oodle library is needed to write the Legends: Arceus packs: give its path in the wizard."))
    try:
        return Oodle(path).compress
    except OodleError as exc:
        raise ValueError(str(exc)) from None


def titles_of(source: Path) -> List[str]:
    """The title ids of the game the source belongs to (Legends: Arceus when it holds a pack)."""
    return list(ARCEUS_TITLES if any(source.rglob("*.gfpak")) else SWORD_SHIELD_TITLES)


def build_switch(source_dir: str, translation_dir: str, output_dir: str,
                 progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
    source, out = Path(source_dir), Path(output_dir) / MOD_DIR
    changes = romfs_mod.changed_files(source, translation_dir)
    loose: Dict[str, bytes] = {}
    packs: Dict[str, Dict[int, bytes]] = {}
    for rel, data in changes.items():
        found = PACK_FOLDER.match(rel)
        if found:
            packs.setdefault(found.group(1), {})[int(found.group(2))] = data
        else:
            loose[rel] = data
    compress = _oodle_compressor() if packs else None
    for number, (pack_rel, edits) in enumerate(sorted(packs.items()), start=1):
        if is_cancelled():
            raise InterruptedError()
        progress(100 * number // len(packs), pack_rel)
        original = source / pack_rel
        if not original.is_file():
            raise ValueError(tr("The pack {0} is not in the source: unpack the game again.", pack_rel))
        try:
            loose[pack_rel] = gfpak.replace_stored(original.read_bytes(), edits, compress)
        except (gfpak.GfpakError, IndexError, ValueError, OodleError) as exc:
            raise ValueError(tr("The pack {0} does not write: {1}", pack_rel, str(exc))) from None
    romfs_mod.write_titles(out, titles_of(source), loose)
    return str(out)
