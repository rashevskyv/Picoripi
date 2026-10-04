"""The HUD words of ``mgso.rel`` (the game module): LIFE, O2, weapon and item labels, boss names.

The code draws these NUL-terminated ASCII strings cell by cell from a glyph atlas texture that
has only ASCII cells, and finds each one through a relocation into the module's ``.data``. So a
string can change only in place: ASCII, at most its slot minus one byte (the slot runs up to the
next non-NUL byte), the rest NUL. ``SLOTS`` lists the visible strings of the USA module (offset in
the file, original text, slot), from the relocation tables (see the workspace's
``reports/visible_text_inventory.md``).

Ukrainian: ``HUD_LETTERS`` writes each capital letter as one byte. Letters shaped like Latin ones use
those (А -> A); the others use ASCII codes no HUD string uses (lowercase b d f..., symbols), whose
atlas cells the workspace redraws as those letters (``tools\\hud_font.py``). Small letters are
written as capitals: the HUD has no others.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

HUD_LETTERS: Dict[str, str] = {
    **dict(zip("АВЕІКМНОРСТХ", "ABEIKMHOPCTX")),
    **dict(zip("БГДЖЗИЙЛПУФЦЧШЩЬЮЯЄЇҐ", "bdfgjpquxz[\\]^_`{|}~@")),
}
_HUD_READ = {code: letter for letter, code in HUD_LETTERS.items() if not "A" <= code <= "Z"}
_HUD_SHARED = {code: letter for letter, code in HUD_LETTERS.items() if "A" <= code <= "Z"}


def encode(text: str) -> bytes:
    """HUD bytes of ``text``: ASCII as is, Ukrainian letters through ``HUD_LETTERS``."""
    out = bytearray()
    for char in text:
        code = HUD_LETTERS.get(char.upper(), char) if not 0x20 <= ord(char) < 0x7F else char
        if not 0x20 <= ord(code) < 0x7F:
            raise ValueError(f"the HUD font has no {char!r}")
        out.append(ord(code))
    return bytes(out)


def decode(raw: bytes) -> str:
    """The text of HUD bytes: a word with a redrawn cell is Ukrainian, so its A, B, E... are too."""
    text = raw.decode("latin-1")
    if not any(char in _HUD_READ for char in text):
        return text
    return "".join(_HUD_READ.get(char) or _HUD_SHARED.get(char, char) for char in text)

SIZE = 5_729_024
HEADER = bytes.fromhex("00000001000000000000000000000014000000"
                       "4c00000000000000230000000300068110004900000048fff00000001001010100000000000000003000000034")

# (file offset, English text, slot bytes). M9 gets 4, not 8: the empty table entries point at the
# NUL after it.
SLOTS: Sequence[Tuple[int, str, int]] = (
    (0x467E80, "M9", 4), (0x467E88, "SOCOM", 8), (0x467E90, "PSG1", 8), (0x467E98, "NIKITA", 8),
    (0x467EA0, "STINGER", 8), (0x467EA8, "CLAYMORE", 12), (0x467EB4, "C4", 4), (0x467EB8, "CHAFF.G", 8),
    (0x467EC0, "STUN.G", 8), (0x467EC8, "MAGAZINE", 12), (0x467ED4, "GRENADE", 8), (0x467EDC, "FAMAS", 8),
    (0x467EE4, "PSG1-T", 8), (0x467EEC, "BOOK", 8),
    (0x467FA4, "RATION", 8), (0x467FAC, "SCOPE", 8), (0x467FB4, "MEDICINE", 12), (0x467FC0, "BANDAGE", 8),
    (0x467FC8, "PENTAZEM", 12), (0x467FD4, "B.ARMOR", 8), (0x467FDC, "STEALTH", 8), (0x467FE4, "MINE.D", 8),
    (0x467FEC, "GAS MASK", 12), (0x467FF8, "N.V.G", 8), (0x468000, "THERM.G", 8), (0x468008, "CAMERA", 8),
    (0x468010, "BOX 1", 8), (0x468018, "CIGS", 8), (0x468020, "CARD", 8), (0x468028, "ROPE", 8),
    (0x468030, "BOX 2", 8), (0x468038, "BOX 3", 8), (0x468040, "KETCHUP", 8), (0x468048, "AP SENSR", 12),
    (0x468054, "BOX 4", 8), (0x46805C, "TIME BOMB", 12), (0x468068, "SCM.SUPR", 12), (0x468074, "BANDANA", 8),
    (0x46807C, "DOG TAGS", 12), (0x468088, "MO DISC", 8), (0x468090, "HANDKER", 8), (0x468098, "PAL KEY", 8),
    (0x46897C, "GUNNER 01", 12), (0x468A10, "BAKER", 12), (0x468BF4, "OCELOT", 8),
    (0x46919C, "PSYCHO MANTIS", 27), (0x4696B0, "SNIPER WOLF", 12), (0x4699B8, "RAVEN", 8),
    (0x46CD50, "MG-REX", 8), (0x46D190, "HIND", 8), (0x46D2BC, "Meryl", 23), (0x46FEF0, "LIFE", 8),
    (0x46FEF8, "Time", 9), (0x4702E4, "GRIP Lv3", 12), (0x4702F0, "GRIP Lv2", 12), (0x4707E8, "NINJA", 8),
    (0x4714AC, "LIQUID", 16), (0x475304, "EQUIP", 8), (0x47530C, "WEAPON", 29), (0x4766F0, "PLAY", 8),
    (0x4766F8, "STOP", 8), (0x476700, "EJECT", 8), (0x47AB88, "CLAYMORE", 12), (0x47AB94, "FULL", 12),
    (0x47ABE8, "Nikita", 8), (0x47C860, "O2", 36), (0x47E038, "GRIP Lv3", 12), (0x47E044, "GRIP Lv2", 12),
    (0x47E080, "LIFE", 8), (0x47E088, "GRIP Lv1", 16), (0x47E528, "Press ", 8), (0x47E6E0, "Non Memory", 13),
    (0x4818FC, "MGS: The Twin Snakes Game", 28), (0x481938, "MGS: The Twin Snakes Photo", 28),
    (0x481A14, "New File", 64), (0x48A4B0, "Meryl", 8), (0x48A4B8, "Otacon", 11), (0x48A4C4, "TIME LEFT", 12),
    (0x48A500, "TIME", 8), (0x48AFD8, "Meryl", 11),
)


def is_rel(data: bytes) -> bool:
    return len(data) == SIZE and data[:len(HEADER)] == HEADER


def read(data: bytes) -> List[bytes]:
    """The current bytes of every slot's string (without the NUL)."""
    return [bytes(data[offset:data.index(b"\0", offset, offset + slot)]) for offset, _text, slot in SLOTS]


def write(data: bytes, changes: Dict[int, bytes]) -> bytes:
    """``data`` with slot ``index`` -> new ASCII bytes written in place; a string longer than its
    slot or with a non-ASCII byte raises ``ValueError`` (the game has no room or no glyph)."""
    out = bytearray(data)
    for index, new in changes.items():
        offset, text, slot = SLOTS[index]
        bad = sorted({chr(b) for b in new if not 0x20 <= b < 0x7F})
        if bad:
            raise ValueError(f"mgso.rel '{text}': only ASCII letters exist in the HUD font ({''.join(bad)!r})")
        if len(new) > slot - 1:
            raise ValueError(f"mgso.rel '{text}': {len(new)} characters, the game has room for {slot - 1}")
        out[offset:offset + slot - 1] = new + bytes(slot - 1 - len(new))
    return bytes(out)
