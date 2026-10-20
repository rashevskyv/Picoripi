"""Silent Hill 2 for the sh23ds 3DS port: the Ukrainian message files and the text font, in the packer's layout.

The output is ``3ds/sh23ds/events/*.msg`` and ``3ds/sh23ds/ui/font.{bin,t3x}``. Copy the folder over the packer's
``3ds`` folder: these files replace the packer's files of the same name, the others stay as the packer wrote them.
The format follows the port's readers (``port/source/events.c``, ``port/source/font.c``) and the packer's
``sh2conv`` writers (``events_pack.py``, ``ui.py``); the code is written again here from those descriptions.
"""
import os
import struct
from typing import Callable, List, Tuple

import numpy as np
from PIL import Image

from core.i18n import tr
from plugins.silent_hill2_pc import mes

FONT_SOURCE = os.path.join("EE", "sh2e", "font")
TGA_NAME = "font000.tga"           # the Switch UA atlas: 44x64 cells, 100 per row, cell index = byte
WIDTH_NAME = "fontwdata.bin"       # 224 u16: the PC width of each cell in its low byte
CELL = (44, 64)
CELLS_PER_ROW = 100
FONT_CELLS = 224                   # cells 0..223 (ASCII and the Ukrainian letters); the full-width codes stay out
FONT_SIZES = ((20, 30), (16, 24))  # the PC's cell of font 0 and font 1 (sh2conv/ui.py)
PC_TO_3DS = (0.625, 0.46875)       # 3DS pixels per PC unit, across and down (port/source/font.h)
TGA_PER_PC_UNIT = 2.5              # atlas pixels per PC unit across, the median of the table's widths against the ink
ATLAS_WIDTH = 512
SPACE_ADVANCE = 7
FORMAT_LA4 = 0x09
PAD = 1

# Message file per output name. The stage files take their name from the stage number (events_pack.py).
SINGLE_MESSAGES = {
    "common.msg": "common_msg_e.mes",
    "item.msg": "item_x_msg_e.mes",
    "result.msg": "result_msg_e.mes",
    "memo.msg": "memo_x_msg_e.mes",
    "mcard.msg": "m_card_x_msg_e.mes",
    "option.msg": "option_msg_e.mes",
}

# Stage number -> name in stage_<name>_msg_e.mes. From the packer's stage table (sh2-3ds-port-kit/data/dc/stage_table.json,
# the PS2 enum names; stages 1..58, checked 2026-10-20), and DC_STAGE_MSG in events_pack.py for 53..58. Stage 0 is
# Stg_null (no stage): the stage_sample_msg_e.mes file has no stage and is not written.
STAGE_NAMES = {
    1: "tgs_trial",
    2: "toilet", 3: "observation", 4: "forest", 5: "town_east", 6: "apart_e1f", 7: "apart_e2f",
    8: "apart_e3fw", 9: "apart_e3fe", 10: "apart_w1f", 11: "apart_w2f", 12: "apart_stair", 13: "apart_out",
    14: "town_west", 15: "bowling", 16: "to_heaven", 17: "heaven_night", 18: "hospital_1f_f",
    19: "hospital_2f_f", 20: "hospital_3f_f", 21: "hospital_rf_f", 22: "hospital_1fw_b", 23: "hospital_1fe_b",
    24: "hospital_2f_b", 25: "hospital_3f_b", 26: "hospital_bf_b", 27: "hospital_pass", 28: "society",
    29: "delusion_2", 30: "delusion_3", 31: "prison_n", 32: "prison_s", 33: "prison_bf", 34: "labyrinth_w",
    35: "labyrinth_e", 36: "labyrinth_n", 37: "eddie_boss", 38: "lake", 39: "hotel_bf_f", 40: "hotel_1f_f",
    41: "hotel_2f_f", 42: "hotel_3f_f", 43: "hotel_bf_b", 44: "hotel_1f_b", 45: "hotel_2f_b", 46: "hotel_3f_b",
    47: "hotel_fire", 48: "end_recovery", 49: "end_maria", 50: "end_suicide", 51: "end_rebirth", 52: "end_dog",
    53: "x_heaven", 54: "x_town", 55: "x_mansion_1f", 56: "x_mansion_2f", 57: "x_mansion_bf", 58: "x_apart",
}


# ---- messages -------------------------------------------------------------------------------------------------

def _is_control(d: bytes, p: int) -> bool:
    return p + 1 < len(d) and d[p] == 0 and d[p + 1] != 0 and not d[p + 1] & 0x0F


def _text_char(b: int) -> str:
    # Ukrainian cells: byte b is the glyph cell, drawn as code b (port font.c: code = char - 0x20)
    return chr(b + 0x20) if b < 0xE0 else "?"


_STRIP = " \t\n\r\x0b\x0c\x1c\x1d\x1e\x1f"   # Python's ASCII whitespace; the cells 0x85 and 0xA0 are letters here


def _message_text(d: bytes, start: int, end: int) -> str:
    pages, s = [], []
    p = start
    while p < end:
        if not s:
            p += p & 1
            while _is_control(d, p):
                p += 2
            if p >= end:
                break
        b = d[p]
        if b == 0xFF and p + 1 < end:
            c = d[p + 1]
            p += 2
            if c == 0xFF:
                pages.append("".join(s).strip(_STRIP))
                s = []
            elif c == 0xFD:
                s.append("\n")
            elif 0xE0 <= c <= 0xE3:
                s.append(chr(1 + c - 0xE0))
            elif c == 0xF6:
                s.append("\x05")
            continue
        s.append(_text_char(b))
        p += 1
    if s:
        pages.append("".join(s).strip(_STRIP))
    return "\f".join(x for x in pages if x)


def load_texts(data: bytes) -> List[str]:
    """The messages of a message file, as the packer's sh2mes reads them, with the Ukrainian cell bytes kept."""
    starts = mes.table_starts(data)
    out = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(data)
        out.append(_message_text(data, start, end))
    return out


def msg_file(texts: List[str]) -> bytes:
    """A MSG1 file: count, offsets from the file start, then each message as NUL-terminated Latin-1 bytes."""
    blobs = [text.encode("latin-1") + b"\0" for text in texts]
    offsets = []
    position = 8 + 4 * len(blobs)
    for blob in blobs:
        offsets.append(position)
        position += len(blob)
    return struct.pack(f"<4sI{len(offsets)}I", b"MSG1", len(offsets), *offsets) + b"".join(blobs)


# ---- font -----------------------------------------------------------------------------------------------------

def _morton(u: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Index of a texel inside its 8x8 tile (the 3DS tile order, port/source/font.c ink_boxes)."""
    return (u & 1) | (r & 1) << 1 | (u & 2) << 1 | (r & 2) << 2 | (u & 4) << 2 | (r & 4) << 3


def la4_levels(alpha: np.ndarray) -> bytes:
    """LA4 texels: one byte per texel, L in the high nibble, A in the low. The glyphs are white, so L is 15
    where the texel has ink, and 0 where it is fully transparent (tex3ds blacks those out)."""
    h, w = alpha.shape
    rows, cols = np.mgrid[0:h, 0:w]
    position = ((rows >> 3) * (w >> 3) + (cols >> 3)) * 64 + _morton(cols, rows)
    luminance = np.where(alpha > 0, 15, 0).astype(np.uint8)
    out = np.zeros(w * h, np.uint8)
    out[position.ravel()] = ((luminance << 4) | (alpha >> 4)).ravel()
    return out.tobytes()


def t3x_la4(alpha: np.ndarray) -> bytes:
    """A .t3x file of one LA4 image without mipmaps: the Tex3DS header, the 'no compression' header, the texels."""
    h, w = alpha.shape
    body = la4_levels(alpha)
    lw, lh = w.bit_length() - 1, h.bit_length() - 1
    head = struct.pack("<HBBB", 1, (lw - 3) | (lh - 3) << 3, FORMAT_LA4, 0)
    # the sub-texture covers the whole image: left 0, top 1, right 1, bottom 0 (in 1/1024 units)
    head += struct.pack("<HH4H", w, h, 0, 1024, 1024, 0)
    size = len(body)
    packed = bytes([0, size & 0xFF, size >> 8 & 0xFF, size >> 16 & 0xFF]) + body
    return head + packed + b"\0" * (-len(packed) % 4)


def _atlas_height(used: int) -> int:
    height = 64
    while height < used:
        height *= 2
    return height


def font_pack(translation_dir: str) -> Tuple[bytes, np.ndarray]:
    """font.bin bytes and the alpha atlas, built from the Ukrainian atlas of the translation."""
    tga = os.path.join(translation_dir, FONT_SOURCE, TGA_NAME)
    widths_path = os.path.join(translation_dir, FONT_SOURCE, WIDTH_NAME)
    if not os.path.isfile(tga) or not os.path.isfile(widths_path):
        raise ValueError(tr("The Ukrainian font (EE/sh2e/font) is missing from the translation folder."))
    with open(widths_path, "rb") as handle:
        widths = struct.unpack("<224H", handle.read(448))
    atlas_img = Image.open(tga).convert("RGBA")
    alpha_src = atlas_img.getchannel("A")
    atlas = np.zeros((512, ATLAS_WIDTH), np.uint8)
    out = [b"FNT1", struct.pack("<H", len(FONT_SIZES))]
    x = y = 0
    for cell_w, cell_h in FONT_SIZES:
        sh = int(PC_TO_3DS[1] * cell_h + 0.5)
        records = []
        for code in range(FONT_CELLS):
            # the PC width: font 0 from the table; font 1 has no table of its own, so its widths scale with the cell
            pc_width = (widths[code] & 0xFF) * cell_w // FONT_SIZES[0][0]
            advance = SPACE_ADVANCE if code == 0 else pc_width + 2
            col, row = code % CELLS_PER_ROW, code // CELLS_PER_ROW
            box = (col * CELL[0], row * CELL[1], col * CELL[0] + CELL[0], row * CELL[1] + CELL[1])
            cell = np.asarray(alpha_src.crop(box))
            inked = np.nonzero(cell.any(axis=0))[0]
            if code == 0 or not inked.size:
                records.append(struct.pack("<HHHBBBB", code, 0, 0, 0, 0, min(advance, 255), 0))
                continue
            ink = cell[:, inked[0]:inked[-1] + 1]
            if not pc_width:
                # the table has no width for this cell (cell 112 has ink but a 0 width): take the ink's width
                pc_width = max(1, round(ink.shape[1] / TGA_PER_PC_UNIT)) * cell_w // FONT_SIZES[0][0]
                advance = pc_width + 2
            # the ink, cut to its columns and drawn at the PC width (sh2conv/ui.py write_font does the same to the PC glyph)
            sw = max(1, int(PC_TO_3DS[0] * pc_width + 0.5))
            small = np.asarray(Image.fromarray(ink).resize((sw, sh), Image.LANCZOS))
            if x + sw + PAD > ATLAS_WIDTH:
                x, y = 0, y + sh + PAD
            atlas[y:y + sh, x:x + sw] = small
            records.append(struct.pack("<HHHBBBB", code, x, y, sw, sh, min(advance, 255), 0))
            x += sw + PAD
        x, y = 0, y + sh + PAD
        out.append(struct.pack("<HHH", cell_w, cell_h, len(records)))
        out += records
    height = _atlas_height(y)
    return b"".join(out), atlas[:height]


def build_font(translation_dir: str, ui_dir: str) -> None:
    font_bin, alpha = font_pack(translation_dir)
    with open(os.path.join(ui_dir, "font.bin"), "wb") as handle:
        handle.write(font_bin)
    with open(os.path.join(ui_dir, "font.t3x"), "wb") as handle:
        handle.write(t3x_la4(alpha))


# ---- the build ------------------------------------------------------------------------------------------------

def message_jobs() -> List[Tuple[str, str]]:
    """(output file, message file) for every message file the port reads and the translation can change."""
    jobs = list(SINGLE_MESSAGES.items())
    jobs += [(f"s{stage:02d}.msg", f"stage_{name}_msg_e.mes") for stage, name in sorted(STAGE_NAMES.items())]
    return jobs


def build(translation_dir: str, output_dir: str, progress: Callable[[int, str], None],
          is_cancelled: Callable[[], bool]) -> str:
    """Writes 3ds/sh23ds/ into output_dir and returns that folder. Message files the translation lacks are skipped."""
    root = os.path.join(output_dir, "3ds", "sh23ds")
    events_dir = os.path.join(root, "events")
    ui_dir = os.path.join(root, "ui")
    os.makedirs(events_dir, exist_ok=True)
    os.makedirs(ui_dir, exist_ok=True)
    message_dir = os.path.join(translation_dir, "data", "etc", "message")
    jobs = message_jobs()
    written = 0
    for index, (out_name, mes_name) in enumerate(jobs):
        if is_cancelled():
            return root          # the host drops a cancelled build
        source = os.path.join(message_dir, mes_name)
        if os.path.isfile(source):
            with open(source, "rb") as handle:
                texts = load_texts(handle.read())
            with open(os.path.join(events_dir, out_name), "wb") as handle:
                handle.write(msg_file(texts))
            written += 1
        progress(100 * index // (len(jobs) + 1), mes_name)
    if not written:
        raise ValueError(tr("The translation has no message files for sh23ds."))
    build_font(translation_dir, ui_dir)
    progress(100, "")
    return root
