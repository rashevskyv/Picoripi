"""The World Ends with You: which game pictures with text the Textures window lists (``texture_sources.json``).

The pictures are 8 x 8 tiles in the game's ``pack`` archives (``core.containers.twewy_pack``). A tile member
starts with a 4-byte header (byte 0 = 0, bits 8-31 = the member size) and holds 4-bit tiles, or 8-bit tiles
when its pack's palette has 256 colours. Next to the tiles a pack holds BGR555 palettes (16 colours a bank),
screen maps (u16 per 8 x 8 place: tile in bits 0-9, bank in bits 12-15) and sprite cell tables. The
``*.nbfc`` / ``*.nbfp`` / ``*.nbfs`` files of ``Apl_Mor`` are plain 8-bit tiles, palette and map.

``describe(source folder)`` makes the entries (format ``tiles``): every tile member of the packs in
``PICTURE_FILES``, coloured with its pack's palette; a background's tiles take their banks from its map.
Sprites are shown as a plain tile sheet (pieces in storage order). ``python -m plugins.twewy.textures <source>``
writes the plugin's ``texture_sources.json``.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.containers.twewy_pack import TwewyPack

# The packs with menus, titles, captions, logos and other text pictures (NitroFS paths).
PICTURE_FILES = (
    "Apl_Mor/Grp_Title.bin", "Apl_Tak/Grp_BrandLogo.bin", "Apl_Tak/Grp_Menu_fontSCR.bin",
    "Apl_Tak/Grp_MenuTop_BGD00.bin", "Apl_Tak/Grp_MenuTop_BGU00.bin", "Apl_Tak/Grp_MenuTop_OBD00.bin",
    "Apl_Tak/Grp_MenuTop_OBD01.bin", "Apl_Tak/Grp_MenuTop_OBD02.bin", "Apl_Tak/Grp_MenuTop_OBU00.bin",
    "Apl_Tak/Grp_MenuTop_OBU01.bin", "Apl_Tak/Grp_MenuBadge_BGD00.bin", "Apl_Tak/Grp_MenuBadge_BGU00.bin",
    "Apl_Tak/Grp_MenuBadge_OBD00.bin", "Apl_Tak/Grp_MenuBadge_OBU00.bin", "Apl_Tak/Grp_MenuEquip_BGD00.bin",
    "Apl_Tak/Grp_MenuEquip_BGU00.bin", "Apl_Tak/Grp_MenuEquip_OBD00.bin", "Apl_Tak/Grp_MenuEquip_OBU00.bin",
    "Apl_Tak/Grp_MenuScena_BGD00.bin", "Apl_Tak/Grp_MenuScena_BGU00.bin", "Apl_Tak/Grp_MenuScena_OBD00.bin",
    "Apl_Tak/Grp_MenuScena_OBD01.bin", "Apl_Tak/Grp_MenuScena_OBD02.bin", "Apl_Tak/Grp_MenuScena_OBD03.bin",
    "Apl_Tak/Grp_MenuScena_OBU00.bin", "Apl_Tak/Grp_Menu_BGD.bin", "Apl_Tak/Grp_Menu_BGU.bin",
    "Apl_Tak/Grp_MenuIcon.bin", "Apl_Tak/Grp_MenuLuck.bin", "Apl_Tak/Grp_Save_BGD00.bin",
    "Apl_Tak/Grp_Save_BGU00.bin", "Apl_Tak/Grp_Save_OBD00.bin", "Apl_Tak/Grp_Save_OBD01.bin",
    "Apl_Tak/Grp_Save_OBU00.bin", "Apl_Tak/Grp_Shop_BGD00.bin", "Apl_Tak/Grp_Shop_OBD00.bin",
    "Apl_Tak/Grp_Shop_OBD01.bin", "Apl_Tak/Grp_Shop_OBD02.bin", "Apl_Tak/Grp_Shop_OBU00.bin",
    "Apl_Tak/Grp_Result_BGD00.bin", "Apl_Tak/Grp_Result_OBD00.bin", "Apl_Tak/Grp_Result_OBD01.bin",
    "Apl_Tak/Grp_Result_OBU00.bin", "Apl_Tak/Grp_Result_OBU01.bin", "Apl_Tak/Grp_Friend_BGD00.bin",
    "Apl_Tak/Grp_Friend_OBD00.bin", "Apl_Tak/Grp_Friend_OBD01.bin", "Apl_Tak/Grp_Friend_OBD02.bin",
    "Apl_Tak/Grp_Depart_BGD00.bin", "Apl_Tak/Grp_Depart_OBD00.bin", "Apl_Tak/Grp_Depart_OBD01.bin",
    "Apl_Tak/Grp_Tuset_BGD00.bin", "Apl_Tak/Grp_Tuset_OBD00.bin", "Apl_Tak/Grp_Tuset_OBD01.bin",
    "Apl_Tak/Grp_Tuset_OBD02.bin", "Apl_Tak/Grp_Tusin_BGD00.bin", "Apl_Tak/Grp_Tusin_OBD00.bin",
    "Apl_Tak/Grp_Tusin_OBU00.bin", "Apl_Kit/Grp_LocaTitle.bin", "Apl_Kit/Grp_FldSubTitle.bin",
    "Apl_Kit/Grp_FldDownScreen.bin", "Apl_Fur/Grp_Continue.bin", "Apl_Fur/Grp_Tutorial.bin",
    "Apl_Fur/Grp_Tutorialial.bin", "Apl_Fur/Grp_BtlCmd.bin", "Apl_Fur/Bin_BtlMenu.bin", "Apl_Fur/Grp_MenuSmpl.bin",
    "Apl_Fuk/Grp_FldMessWin.bin", "Apl_Fuk/Grp_DelMenu.bin", "Apl_Fuk/Grp_OtosuMenu.bin",
    "Apl_Fuk/Grp_OtosuMenuObj.bin", "Apl_Hor/Grp_Nrep_Back.bin", "Apl_Hor/Grp_Nrep_PartsD.bin",
    "Apl_Hor/Grp_Nrep_PartsU.bin", "Apl_Suy/Grp_Staff_PartA_Pack.bin", "Apl_Suy/Grp_Staff_PartB_Pack.bin",
    "Apl_Suy/Grp_Staff_PartC_Pack.bin", "Apl_Suy/Grp_Staff_PartD_Pack.bin", "Apl_Sug/Grp_baycmnobj.bin",
    "Apl_Sug/Grp_baymenovobj.bin", "Apl_Sug/Grp_baymenuunobj.bin",
)
# The plain background files of Apl_Mor (copyright and opening screens): tiles, palette.
BG_FILES = ("Apl_Mor/COPY_RG_SE", "Apl_Mor/COPY_UG_CRI", "Apl_Mor/COPY_UG_JP", "Apl_Mor/N_COPY_RG_NIN",
            "Apl_Mor/OpeningBG_RG", "Apl_Mor/OpeningBG_UGstart", "Apl_Mor/OpeningBG_UGstart2")
SOURCE_FILES = PICTURE_FILES + tuple(f"{name}.{ext}" for name in BG_FILES for ext in ("nbfc", "nbfp", "nbfs"))


def header_size(data: bytes) -> int:
    """The size a tile / map member's header gives (bits 8-31 of u32 0), or 0 when it has none."""
    size = int.from_bytes(data[1:4], "little")
    return size if len(data) >= 8 and data[0] == 0 and size == len(data) else 0


def _palette(members: Dict[str, bytes]) -> Optional[bytes]:
    """The pack's palette: a plain member of whole banks, not a table that starts with a small count."""
    for name, data in members.items():
        if (not header_size(data) and data[:4] != b"pack" and 0 < len(data) <= 0x200 and len(data) % 32 == 0
                and struct.unpack_from("<I", data, 0)[0] >= 0x80):
            return data
    return None


def _map_banks(screen: bytes, tiles: int) -> Optional[Dict[int, int]]:
    """``{tile: bank}`` from a screen map, or None when ``screen`` is not a map of ``tiles`` tiles."""
    banks: Dict[int, int] = {}
    for (entry,) in struct.iter_unpack("<H", screen[4:len(screen) // 2 * 2]):
        if entry & 0x3FF >= tiles:
            return None
        banks.setdefault(entry & 0x3FF, entry >> 12)
    return banks


def _entries_of_pack(pack: TwewyPack, path: str, prefix: str) -> List[Dict[str, Any]]:
    names = pack.list_files()[1:-1]
    members = {name: pack.read_file(name) for name in names}
    out: List[Dict[str, Any]] = []
    for name, data in members.items():
        if data[:4] == b"pack":
            out += _entries_of_pack(TwewyPack(data), path, f"{prefix}{name}/")
    shaped = {name: data for name, data in members.items() if header_size(data)}
    if not shaped:
        return out
    palette = _palette(members)
    bpp = 8 if palette and len(palette) >= 0x200 else 4
    biggest = max(shaped, key=lambda name: len(shaped[name]))
    tile_count = (len(shaped[biggest]) - 4) * 8 // bpp // 64
    screens = [d for n, d in shaped.items() if n != biggest and _map_banks(d, tile_count) is not None]
    for name, data in shaped.items():
        if any(data is screen for screen in screens):
            continue
        tiles = (len(data) - 4) * 8 // bpp // 64
        if not tiles:
            continue
        params: Dict[str, Any] = {"bpp": bpp, "offset": 4, "per_row": 32 if tiles >= 32 else tiles}
        if palette:
            params["palette"] = palette.hex()
        if bpp == 4 and name == biggest and screens:
            banks = _map_banks(screens[0], tiles) or {}
            if any(banks.values()):
                params["banks"] = "".join(f"{banks[t]:x}" if t in banks else "." for t in range(tiles))
        kind = "background" if name == biggest and screens else "sprites"
        out.append({"label": f"{Path(path).stem} {prefix}{name} ({kind})", "kind": "menu", "format": "tiles",
                    "path": path, "member": f"{prefix}{name}", "params": params})
    return out


def describe(source: Path) -> List[Dict[str, Any]]:
    """The Textures window's entries for the files under ``source`` (the project's source folder)."""
    out: List[Dict[str, Any]] = []
    for path in PICTURE_FILES:
        if (source / path).is_file():
            out += _entries_of_pack(TwewyPack((source / path).read_bytes()), path, "")
    for name in BG_FILES:
        tiles, palette = source / f"{name}.nbfc", source / f"{name}.nbfp"
        if tiles.is_file() and palette.is_file():
            out.append({"label": f"{Path(name).name} (background)", "kind": "title_screen", "format": "tiles",
                        "path": f"{name}.nbfc",
                        "params": {"bpp": 8, "per_row": 32, "palette": palette.read_bytes().hex()}})
    return out


if __name__ == "__main__":
    entries = describe(Path(sys.argv[1]))
    target = Path(__file__).with_name("texture_sources.json")
    target.write_text("[\n" + ",\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n]\n",
                      encoding="utf-8")
    print(f"{len(entries)} entries -> {target}")
