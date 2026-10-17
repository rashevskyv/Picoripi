"""The files the unpack step takes from the Castlevania DS games (USA): the same set as zt/cvds.py ``unpack``.

Dawn of Sorrow (``dos``), Portrait of Ruin (``por``) and Order of Ecclesia (``ooe``), told apart by the game code
in the header. The string table is read from the overlays (the string pointer table is in overlay 0) and written as
``<key>/strings.cvdstext``: JSON with every string as its raw bytes, without the ``01 00`` head and ``EA`` end.
The two fonts and the pictures with text are copied by their NitroFS paths under ``<key>/``.
"""
from core.i18n import tr
import json
import os
import struct
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from core.containers.image_files import ImageError
from core.project_library import images

TEXT_FORMAT = "castlevania-ds-text"
TEXT_FILE = "strings.cvdstext"
HEAD, END = b"\x01\x00", 0xEA
FONTS = ("font/LD_font_u8.DAT", "font/LD_font_u12.DAT")
CODE_AT, FAT_AT, OVERLAY_TABLE_AT = 0x0C, 0x48, 0x50


DOS_REGIONS = (("Character Names", 0x0, 0xB), ("Item Names", 0xC, 0xD9), ("Item Descriptions", 0xDA, 0x1A7),
               ("Enemy Names", 0x1A8, 0x21D), ("Enemy Descriptions", 0x21E, 0x293), ("Soul Names", 0x294, 0x30E),
               ("Soul Descriptions", 0x30F, 0x389), ("Area Names", 0x38A, 0x395), ("Music Names", 0x396, 0x3B2),
               ("System", 0x3B3, 0x3D8), ("Menus", 0x3D9, 0x477), ("Library", 0x478, 0x4A5), ("Events", 0x4A6, 0x50A))
POR_REGIONS = (("Character Names", 0x0, 0xB, 2), ("Item Names", 0xC, 0x15B, 1), ("Item Descriptions", 0x15C, 0x2AB, 1),
               ("Enemy Names", 0x2AC, 0x348, 1), ("Enemy Descriptions", 0x349, 0x3E5, 1),
               ("Skill Names", 0x3E6, 0x451, 1), ("Skill Descriptions", 0x452, 0x4BD, 1),
               ("Music Names (Unused)", 0x4BE, 0x4E6, 1), ("System", 0x4E7, 0x51F, 1), ("Menus 1", 0x520, 0x5FD, 1),
               ("Music Names", 0x5FE, 0x621, 1), ("Language Names", 0x622, 0x626, 1), ("Quest Names", 0x627, 0x64B, 1),
               ("Quest Descriptions", 0x64C, 0x670, 1), ("Menus 2", 0x671, 0x6BD, 1), ("Events", 0x6BE, 0x747, 2),
               ("Debug", 0x748, 0x748, 1))
OOE_REGIONS = (("Character Names", 0x0, 0x15), ("Item Names", 0x16, 0x177), ("Item Descriptions", 0x178, 0x2D9),
               ("Enemy Names", 0x2DA, 0x352), ("Enemy Descriptions", 0x353, 0x3CB), ("System", 0x3CC, 0x407),
               ("Menus 1", 0x408, 0x533), ("Quest Names", 0x534, 0x557), ("Menus 2", 0x558, 0x566),
               ("Term List", 0x567, 0x5A0), ("Area Names", 0x5A1, 0x5C0), ("Quest Descriptions", 0x5C1, 0x5E3),
               ("Music Names", 0x5E4, 0x61C), ("Menus 3", 0x61D, 0x65F), ("Events", 0x660, 0x764))

# background layers, plus the English-only pictures (``_e`` / ``_u``). sc/ = plain bitmaps, bc/ = 8x8 tiles.
DOS_GFX = (
    "sc/f_com00.dat", "sc/f_com01.dat", "sc/f_com02.dat", "sc/f_com03.dat", "sc/f_com04.dat", "sc/f_com05.dat",
    "sc/f_lice.dat", "sc/f_konami.dat", "sc/f_tiobj0.dat", "sc/f_tiobj1.dat", "sc/f_tit_e0.dat", "sc/f_tit_e1.dat",
    "sc/f_tit_e2.dat", "sc/f_roll0.dat", "sc/f_roll1.dat", "sc/f_roll2.dat", "sc/f_roll3.dat", "sc/f_roll4.dat",
    "sc/f_roll5.dat", "sc/f_roll6.dat", "sc/f_roll7.dat", "sc/f_roll8.dat", "sc/f_endtx0.dat", "sc/f_endtx1.dat",
    "sc/f_endtx2.dat", "sc/f_endtx3.dat", "sc/f_gover1.dat", "sc/f_gover2.dat", "sc/f_gover3.dat", "sc/f_gover4.dat",
    "sc/f_name0.dat", "sc/f_top0.dat", "sc/f_top1.dat", "sc/f_vssel_e0.dat", "sc/f_eset.dat", "sc/f_retry.dat",
    "sc/f_net.dat", "sc/f_mainob.dat", "sc/f_mix_e.dat", "sc/f_scrap.dat", "bc/f_topbg0.dat", "bc/f_topbg1.dat",
    "bc/f_topbg2.dat", "bc/f_paper1.dat", "bc/f_paper2.dat", "bc/f_sd_e.dat", "bc/f_shpbg0.dat", "bc/f_shpbg1.dat",
    "bc/f_shpbg2.dat", "bc/f_mixbg0.dat", "bc/f_mixbg1.dat", "bc/f_mixbg2.dat", "bc/f_main0.dat", "bc/f_main1.dat",
    "bc/f_main2.dat", "bc/f_pal0.dat", "bc/f_itemu.dat", "bc/f_abil.dat", "bc/f_conf.dat", "bc/f_ene0.dat",
    "bc/f_ene1.dat", "bc/f_libr.dat", "bc/f_mgs.dat", "sc/f_area_e00.dat", "sc/f_area_e01.dat", "sc/f_area_e02.dat",
    "sc/f_area_e03.dat", "sc/f_area_e04.dat", "sc/f_area_e05.dat", "sc/f_mark_e.dat", "sc/f_res_e0.dat",
)
POR_GFX = (
    "sc/f_com00.dat", "sc/f_com01.dat", "sc/f_com02.dat", "sc/f_com03.dat", "sc/f_com04.dat", "sc/f_com05.dat",
    "sc/f_com06.dat", "sc/f_com07.dat", "sc/f_konami0.dat", "sc/f_konami1.dat", "sc/f_konami2.dat",
    "sc/f_konami3.dat", "sc/f_konami4.dat", "sc/f_konami5.dat", "sc/f_optitle01.dat", "sc/f_optitle02.dat",
    "sc/f_optitle03.dat", "sc/f_optitle04.dat", "sc/f_optitle05.dat", "sc/f_optitle06.dat", "sc/f_optitle07.dat",
    "sc/f_tlogoB0.dat", "sc/f_tlogoB1.dat", "sc/f_tobj0.dat", "sc/f_tobj1.dat", "sc/f_cmnopd_u.dat",
    "sc/f_cmnopd1.dat", "sc/f_gsele0.dat", "sc/f_seleob0.dat", "sc/f_seleob1.dat", "sc/f_name0.dat", "sc/f_emb00.dat",
    "sc/f_emb01.dat", "sc/f_emb02.dat", "sc/f_emb03.dat", "sc/f_menuob0.dat", "sc/f_equipob0.dat", "sc/f_useob0.dat",
    "sc/f_gconfigob.dat", "sc/f_relicsob.dat", "sc/f_zueneselob.dat", "sc/f_zuitemob.dat", "sc/f_zusoulob.dat",
    "sc/f_questob.dat", "sc/f_shoptopob.dat", "sc/f_shopbuyob.dat", "sc/f_fjona_w.dat", "sc/f_fchlt_w.dat",
    "sc/f_who0.dat", "sc/f_oyalist0.dat", "sc/f_retry0.dat", "sc/f_wfsele0_u.dat", "sc/f_coop0.dat", "sc/f_coop1.dat",
    "sc/f_cpsele0.dat", "sc/f_wfmenu0_u.dat", "sc/f_shopcha0.dat", "sc/f_option0_u.dat", "sc/f_fcmenu0_u.dat",
    "sc/f_fclist0.dat", "sc/f_fcent0.dat", "sc/f_bossel0.dat", "sc/f_moonob0_u.dat", "sc/f_gover0.dat",
    "sc/f_gover1.dat", "sc/f_gover2.dat", "sc/f_gover3.dat", "sc/f_govera0.dat", "sc/f_govera1.dat",
    "sc/f_govera2.dat", "sc/f_govera3.dat", "sc/f_edr09.dat", "sc/f_edr0a.dat", "sc/f_edr0b.dat", "sc/f_edr0c.dat",
    "sc/f_edr0d.dat", "sc/f_edr0e.dat", "sc/f_edr0f.dat", "sc/f_edr10.dat", "sc/f_edr11.dat", "sc/f_edr12.dat",
    "sc/f_edr13.dat", "sc/f_edr14.dat", "sc/f_edr15.dat", "sc/f_edr16.dat", "sc/f_edr17.dat", "sc/f_edr18.dat",
    "sc/f_edr19.dat", "sc/f_edr1a.dat", "sc/f_edr1b.dat", "sc/f_edr00.dat", "sc/f_edr01.dat", "sc/f_edr02.dat",
    "sc/f_edr03.dat", "sc/f_edr04.dat", "sc/f_area00_U.dat", "sc/f_area01_U.dat", "sc/f_area02_U.dat",
    "sc/f_area03_U.dat", "sc/f_area04_U.dat", "sc/f_area05_U.dat", "sc/f_area06_U.dat", "sc/f_area07_U.dat",
    "sc/f_area08_U.dat", "bc/f_cmnbg0.dat", "bc/f_cmnbg1.dat", "bc/f_cmnbg2.dat", "bc/f_shoptop0.dat",
    "bc/f_shoptop1.dat", "bc/f_menu0.dat", "bc/f_menu1.dat", "bc/f_equip0.dat", "bc/f_usei0.dat", "bc/f_gconfig.dat",
    "bc/f_talking0.dat", "bc/f_talking1.dat", "bc/f_relics.dat", "bc/f_zuenesel.dat", "bc/f_zuenecont.dat",
    "bc/f_zuitem.dat", "bc/f_zusoul.dat", "bc/f_quest0.dat", "bc/f_quest1.dat", "bc/f_quest2.dat", "bc/f_sbcmn1.dat",
    "bc/f_sbcmn2.dat", "bc/f_mapv0.dat", "bc/f_mapv1.dat", "bc/f_moonbg0.dat", "bc/f_moonbg1.dat", "sc/f_rank1_u.dat",
    "sc/f_rgio_e.dat", "sc/f_sound0_u.dat",
)
OOE_GFX = (
    "sc/f_com00.dat", "sc/f_com01.dat", "sc/f_com02.dat", "sc/f_com03.dat", "sc/f_com04.dat", "sc/f_com05_u.dat",
    "sc/f_com06.dat", "sc/f_com07.dat", "sc/f_tlog00.dat", "sc/f_tlog01.dat", "sc/f_tlog02.dat", "sc/f_tlog03.dat",
    "sc/f_tlog04.dat", "sc/f_tlog05.dat", "sc/f_tlog06.dat", "sc/f_tlog07.dat", "sc/f_tlog08.dat", "sc/f_tlog09.dat",
    "sc/f_tlog0a.dat", "sc/f_tlog0b.dat", "sc/f_tlog0c.dat", "sc/f_tlog0d.dat", "sc/f_tlog0e_e.dat",
    "sc/f_tlog0f_e.dat", "sc/f_tlog10.dat", "sc/f_tlog11.dat", "sc/f_tlog12.dat", "sc/f_tlog13.dat",
    "sc/f_gout00.dat", "sc/f_gout01.dat", "sc/f_gout02.dat", "sc/f_gout03_j.dat", "sc/f_gout04_j.dat",
    "sc/f_gout05_j.dat", "sc/f_gout06_j.dat", "sc/f_gout07_j.dat", "sc/f_gout08.dat", "sc/f_gout09.dat",
    "sc/f_gauge.dat", "sc/f_menu00.dat", "sc/f_menu01.dat", "sc/f_menu02.dat", "sc/f_menu03_e.dat", "sc/f_menu04.dat",
    "sc/f_menu05.dat", "sc/f_gloss0.dat", "sc/f_gloss1_u.dat", "sc/f_gam00.dat", "sc/f_gam01.dat", "sc/f_gam02.dat",
    "sc/f_gam03.dat", "sc/f_gam10.dat", "sc/f_gam11.dat", "sc/f_gam12.dat", "sc/f_gam13.dat", "sc/f_gam20.dat",
    "sc/f_gam21.dat", "sc/f_gam22.dat", "sc/f_gam23.dat", "sc/f_aamap0.dat", "sc/f_aamap1.dat", "sc/f_wmap00.dat",
    "sc/f_wmap01.dat", "sc/f_wmap02.dat", "sc/f_wmap03.dat", "sc/f_wmap04.dat", "sc/f_wmap05.dat", "sc/f_wmap06.dat",
    "sc2/f_prolo0.dat", "sc2/f_prolo1.dat", "sc2/f_prolo2.dat", "sc2/f_enbg00.dat", "sc2/f_enbg01.dat",
    "sc2/f_enbg02.dat", "sc2/f_enbg03.dat", "sc2/f_enbg04.dat", "sc2/f_enbg05.dat", "sc2/f_enbg06.dat",
    "sc2/f_enbg07.dat", "sc2/f_enr00.dat", "sc2/f_enr01.dat", "sc2/f_enr02.dat", "sc2/f_enr03.dat", "sc2/f_enr04.dat",
    "sc2/f_enr05.dat", "sc2/f_enr06.dat", "sc2/f_enr07.dat", "sc2/f_enr08.dat", "sc2/f_enr09.dat", "sc2/f_enr0a.dat",
    "sc2/f_enr0b.dat", "sc2/f_enr0c.dat", "sc2/f_enr0d.dat", "sc2/f_enr0e.dat", "sc2/f_enr0f.dat", "sc2/f_enr10.dat",
    "sc2/f_enr11.dat", "sc2/f_enr12.dat", "sc2/f_enr13.dat", "sc2/f_enr14.dat", "sc2/f_enr15.dat", "sc2/f_enr16.dat",
    "sc2/f_enr17.dat", "sc/f_com05_e.dat", "sc/f_gloss1_e.dat", "sc/f_gout03_e.dat", "sc/f_gout03_u.dat",
    "sc/f_gout04_e.dat", "sc/f_gout04_u.dat", "sc/f_gout05_e.dat", "sc/f_gout05_u.dat", "sc/f_gout06_e.dat",
    "sc/f_gout06_u.dat", "sc/f_gout07_e.dat", "sc/f_gout07_u.dat", "sc/f_mark_e.dat", "sc/f_mark_u.dat",
    "sc/f_menu03_u.dat", "sc/f_race00_e.dat", "sc/f_race00_u.dat", "sc/f_race01_e.dat", "sc/f_race01_u.dat",
    "sc/f_race02_e.dat", "sc/f_race02_u.dat", "sc/f_record02_e.dat", "sc/f_record02_u.dat", "sc/f_shop01_e.dat",
    "sc/f_shop01_u.dat", "sc/f_subwob_e.dat", "sc/f_subwob_u.dat", "sc/f_vsstart01_e.dat", "sc/f_vsstart01_u.dat",
    "sc/f_wiids02_e.dat", "sc/f_wiids02_u.dat", "sc2/f_area00_e.dat", "sc2/f_area00_u.dat", "sc2/f_area01_e.dat",
    "sc2/f_area01_u.dat", "sc2/f_area02_e.dat", "sc2/f_area02_u.dat", "sc2/f_area03_e.dat", "sc2/f_area03_u.dat",
    "sc2/f_area04_e.dat", "sc2/f_area04_u.dat", "sc2/f_area05_e.dat", "sc2/f_area05_u.dat", "sc2/f_area06_e.dat",
    "sc2/f_area06_u.dat", "sc2/f_area07_e.dat", "sc2/f_area07_u.dat", "sc2/f_area08_e.dat", "sc2/f_area08_u.dat",
    "sc2/f_area09_e.dat", "sc2/f_area09_u.dat", "sc2/f_area10_e.dat", "sc2/f_area10_u.dat", "sc2/f_area11_e.dat",
    "sc2/f_area11_u.dat", "sc2/f_area12_e.dat", "sc2/f_area12_u.dat", "sc2/f_area13_e.dat", "sc2/f_area13_u.dat",
)


# game code -> (folder key, title, RAM address of the string pointer table in overlay 0, regions, pictures)
GAMES = {
    "ACVE": ("dos", "Dawn of Sorrow", 0x0222F300, tuple((*r, 0) for r in DOS_REGIONS), DOS_GFX),
    "ACBE": ("por", "Portrait of Ruin", 0x0221BA50, POR_REGIONS, POR_GFX),
    "YR9E": ("ooe", "Order of Ecclesia", 0x021FACC0, tuple((*r, 0) for r in OOE_REGIONS), OOE_GFX),
}


def _u32(image, at: int) -> int:
    return struct.unpack("<I", image.read_at(at, 4))[0]


def _file(image, file_id: int) -> bytes:
    """The bytes of one file, by its id in the ROM's file allocation table."""
    start, end = struct.unpack("<II", image.read_at(_u32(image, FAT_AT) + 8 * file_id, 8))
    return image.read_at(start, end - start)


def _overlays(image) -> Dict[int, Tuple[int, int]]:
    """``{overlay id: (RAM address, file id)}`` from the ARM9 overlay table."""
    table, size = _u32(image, OVERLAY_TABLE_AT), _u32(image, OVERLAY_TABLE_AT + 4)
    raw = image.read_at(table, size)
    out = {}
    for at in range(0, size, 32):
        overlay, ram, _length, _bss, _start, _end, file_id, _flags = struct.unpack_from("<8I", raw, at)
        out[overlay] = (ram, file_id)
    return out


def read_strings(image, table_ram: int, regions) -> List[bytes]:
    """The raw bytes of every string, in table order (without the head and the end byte)."""
    overlays = _overlays(image)
    data = {overlay: _file(image, overlays[overlay][1]) for overlay in {r[3] for r in regions} | {0}}
    out = []
    for text_id in range(regions[-1][2] + 1):
        overlay = next((r[3] for r in regions if r[1] <= text_id <= r[2]), None)
        if overlay is None:
            raise ImageError(tr("string {0:#x} is outside the string table", text_id))
        pointer = struct.unpack_from("<I", data[0], table_ram - overlays[0][0] + 4 * text_id)[0]
        body, at = data[overlay], pointer - overlays[overlay][0]
        if not 0 <= at < len(body) or body[at:at + 2] != HEAD:
            raise ImageError(tr("string {0:#x}: unexpected start at address {1:08X}", text_id, pointer))
        end = body.find(bytes([END]), at + 2)
        if end < 0:
            raise ImageError(tr("string {0:#x}: no end byte", text_id))
        out.append(bytes(body[at + 2:end]))
    return out


def _write_text(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def extract(base: str, target_dir: str, progress: Callable[[int, str], None],
            is_cancelled: Callable[[], bool]) -> Optional[str]:
    with images.open_image(base) as image:
        code = image.read_at(CODE_AT, 4).decode("ascii", "replace")
        if code not in GAMES:
            raise ImageError(tr("game code {0!r} is not a Castlevania DS game (USA)", code))
        key, title, table_ram, regions, gfx = GAMES[code]
        progress(0, f"{title}: {TEXT_FILE}")
        strings = read_strings(image, table_ram, regions)
        bank = {"format": TEXT_FORMAT, "game": key,
                "regions": [[name, first, last] for name, first, last, _overlay in regions],
                "strings": [s.hex() for s in strings]}
        if is_cancelled():
            return None
        _write_text(Path(target_dir, key, TEXT_FILE), (json.dumps(bank, indent=1) + "\n").encode("utf-8"))
        nitro = {entry.path: entry for entry in image.entries()}
        names = (*FONTS, *gfx)
        missing = [name for name in names if name not in nitro]
        if missing:
            raise ImageError(tr("the ROM has no file {0}", missing[0]))
        entries = [nitro[name]._replace(path=f"{key}/{name}") for name in names]
        if not images.write_entries(image, entries, target_dir, progress, is_cancelled):
            return None
    return str(target_dir)
