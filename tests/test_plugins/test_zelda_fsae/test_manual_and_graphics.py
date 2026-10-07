"""The manual (NTPG pages in a BLZ NARC) and the graphics packs of Four Swords Anniversary Edition."""
import struct
from pathlib import Path

import pytest
from PIL import Image

from core.containers import nitro
from core.formats import SaveContext
from core.texture_formats import sources as tex_sources
from plugins.testing import load_rules
from plugins.zelda_fsae import manual
from plugins.zelda_fsae.packs import CmpPack, ZeldatPack
from test_core.test_containers_nitro import narc

FSAE = Path(r"E:\Emulators\RomHacking\Zelda\Four Swords Anniversary")


def _block(magic: bytes, body: bytes) -> bytes:
    body += bytes(-len(body) % 4)
    return magic + struct.pack("<I", 8 + len(body)) + body


def _page(strings, boxes) -> bytes:
    """An NTPG file: ``strings`` (raw UTF-16 without terminator), ``boxes`` [(string index, [line bytes])]."""
    raws = [s + b"\0\0" for s in strings]
    offsets, at = [], 4 * (len(raws) + 1)
    for raw in raws:
        offsets.append(at)
        at += len(raw)
    offsets.append(at)
    blocks = [_block(b"nap1", bytes(8)), _block(b"txp1", struct.pack(f"<I{len(offsets)}I", len(raws), *offsets)
                                                + b"".join(raws))]
    for index, lines in boxes:
        body = struct.pack("<8H", 8, 8, 240, 16 * len(lines), index, len(lines), 13, 16) + bytes(16)
        body += b"".join(struct.pack("<4H", 10 * n // 2, 16, 0, n) for n in lines)
        blocks.append(_block(b"txt1", body))
    blocks.append(_block(b"pae1", b""))
    data = b"".join(blocks)
    return b"NTPG" + struct.pack("<HHIHH", 0xFEFF, 0x0200, 16 + len(data), 16, len(blocks)) + data


def _units(text: str) -> bytes:
    return text.encode("utf-16-le")


def test_page_text_lines_codes_and_rebuild():
    second = _units("Hello ") + struct.pack("<3H", 2, 4, 0x1CE7) + _units("big") + struct.pack("<3H", 1, 4, 3)
    second += _units(" world")
    data = _page([_units("Title"), second], [(1, [12, len(second) - 12])])
    page = manual.Page(data)
    assert page.texts() == ["Title", "Hello \n[color:7399]big[pic:3] world"]
    assert page.build(page.texts()) == data
    out = manual.Page(page.build(["Назва", "Один\nдва\nтри"]))
    assert out.texts() == ["Назва", "Один\nдва\nтри"]
    (_index, lines), = out.boxes().values()
    assert [line[3] for line in lines] == [8, 6, 6] and all(line[1] == 16 for line in lines)


def test_unchanged_line_keeps_its_width():
    data = _page([_units("ab cd")], [(0, [6, 4])])
    page = manual.Page(data)
    out = manual.Page(page.build(["ab \ncd!!!"]))
    widths = [line[0] for line in out.boxes()[0][1]]
    assert widths == [30, 50]           # "ab " keeps its stored width; "cd!!!" gets the box's 10 px a character


def test_plugin_loads_and_saves_the_manual():
    page = _page([_units("General Information"), _units("Text " * 40)], [(1, [400])])
    names = [f"arc/ntmc/{manual.LANGUAGE}/manual", f"arc/ntpg/{manual.LANGUAGE}/page_01"]
    plain = narc(dict.fromkeys(names, page))
    raw = nitro.blz_compress(plain)
    rules = load_rules("zelda_fsae")
    blocks, block_names = rules.load_data_from_json_obj(raw)
    assert blocks == [["General Information", ("Text " * 40)]] * 2
    assert block_names == {"0": "Manual: contents", "1": "Manual: page_01"}
    assert rules.save_data_to_json_obj(blocks, block_names) == raw
    blocks[1][1] = "Текст"
    rules.reset_runtime_state()
    rules.prepare_save_context(SaveContext(existing_versions=lambda: iter([raw])))
    saved = rules.save_data_to_json_obj(blocks, block_names)
    again = load_rules("zelda_fsae").load_data_from_json_obj(saved)[0]
    assert again == [["General Information", "Text " * 40], ["General Information", "Текст"]]


# -- the workspace's own files ------------------------------------------------------------------

def _need(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"{path} is not on this machine")
    return path.read_bytes()


def test_real_manual_round_trips_and_an_edit_reads_back():
    raw = _need(FSAE / "source" / "manpages_narc_eu.blz")
    rules = load_rules("zelda_fsae")
    blocks, names = rules.load_data_from_json_obj(raw)
    assert len(blocks) == 18 and sum(map(len, blocks)) == 293
    assert names["0"] == "Manual: contents" and blocks[1][0] == "General Information"
    assert rules.save_data_to_json_obj(blocks, names) == raw
    plain = nitro.blz_decompress(raw)
    assert nitro.NarcContainer(plain).pack() == plain


def test_real_graphics_packs_round_trip():
    for name, cls, count in (("subtask_eu_en.cmp", CmpPack, 6), ("zeldat_eu_en.bin", ZeldatPack, 18)):
        data = _need(FSAE / "source" / name)
        assert cls.can_handle(data)
        pack = cls(data)
        assert len(pack.list_files()) == count
        pack.write_file("#1", pack.read_file("#1"))
        assert pack.pack() == data
    assert not CmpPack.can_handle(_need(FSAE / "source" / "eu.kmsg"))
    assert not ZeldatPack.can_handle(_need(FSAE / "source" / "font_ltn.nftr"))


def test_real_texture_sources_resolve_in_colour_and_round_trip(tmp_path):
    _need(FSAE / "source" / "subtask.cmp")
    rules = load_rules("zelda_fsae")
    found = tex_sources.resolve(rules.get_texture_sources(), {
        "source_path": str(FSAE / "source"), "translation_path": str(tmp_path), "is_directory_mode": True})
    keys = {source.key for source in found}
    assert len(found) == 21 and "zeldat.bin/#502" in keys and "subtask_eu_en.cmp/#4" in keys
    assert next(s for s in found if s.key == "zeldat_eu_en.bin/#10#32x32").size == (256, 32)   # GAME OVER letters
    assert next(s for s in found if s.key == "zeldat_eu_en.bin/#10#16x32").size == (256, 32)   # as 16 slots
    for source in found:                                    # every picture: its own PNG writes nothing back
        image = Image.open(_png(source.read_original().image)).convert("RGBA")
        assert source.write(image) is False, source.key
    logo = next(s for s in found if s.key == "zeldat.bin/#502").read_original().image
    assert any(c[3] and c[0] > 150 and max(c[1], c[2]) < 80 for _n, c in logo.getcolors(1 << 16))   # red, not grey
    plate = next(s for s in found if s.key == "zeldat_eu_en.bin/#2")
    image = plate.read_original().image
    colour = image.getpixel((20, 4))
    image.paste((250, 250, 250, 255), (0, 0, 8, 8))         # an off-palette white: the bank's nearest colour
    assert plate.write(image) and (tmp_path / "zeldat_eu_en.bin").is_file()
    redrawn = plate.read_current().image
    assert redrawn.getpixel((3, 3))[3] == 255 and redrawn.getpixel((3, 3)) != colour
    assert redrawn.crop((8, 0, 256, 16)).tobytes() == image.crop((8, 0, 256, 16)).tobytes()


def _png(image):
    import io
    out = io.BytesIO()
    image.save(out, "PNG")
    out.seek(0)
    return out


def test_real_texture_sources_match_the_game_palettes():
    _need(FSAE / "source" / "subtask.cmp")
    from plugins.zelda_fsae import palettes
    assert palettes.build(FSAE / "source") == load_rules("zelda_fsae").get_texture_sources()
