"""Xenoblade Chronicles X: Definitive Edition plugin: modern BDAT tables (shared with Xenoblade 3), the credits
roll (``crt``: slot offsets rebuilt, shared strings kept shared, table padded to 16), both formats through one
``GameRules``, the tag manager, and the MIBL block start inside a layout (the footer page is only added when
the footer does not fit after the last mip level)."""
import struct

from PIL import Image

from core.formats import SaveContext
from core.texture_formats import mibl, wilay
from plugins.common import bdat
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules
from plugins.xenoblade_x_de import crt
from plugins.xenoblade_x_de.rules import TAG_RE
from test_plugins.test_xenoblade_3.test_rules import SAMPLE

PLUGIN = "xenoblade_x_de"


def _credits(rows):
    """A credits file: ``rows`` are lists of 7 slot texts (None = unused slot); strings in first-use order."""
    body, table, where = bytearray(), bytearray(), {}
    for n, slots in enumerate(rows):
        words = [0x41580000, n % 2, 0, 0]
        for text in slots:
            if text is None:
                words += [0, 0, 0xFFFFFFFF, 0, crt.NONE]
                continue
            if text not in where:
                where[text] = len(table)
                table += text.encode("utf-8") + b"\0"
            words += [0, 0x10, 0xFFC4D11D, 2, where[text]]
        body += struct.pack(f"<{crt.WORDS}I", *words)
    head = struct.pack("<4s3I", crt.MAGIC, len(rows), 16, 16 + len(body))
    return head + bytes(body) + bytes(table) + bytes(-len(table) % 16)


CREDITS = _credits([["JAPANESE VOICE CAST", None, None, None, None, None, None],
                    [None, "ELMA", None, "Houko Kuwashima", None, None, None],
                    [None, "LYNLEE", None, "Mariya Ise", None, None, None],
                    ["JAPANESE VOICE CAST", None, None, None, None, None, None]])


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".bdat", ".crt"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_both_file_kinds_survive_load_and_save():
    assert bdat.is_bdat(SAMPLE) and crt.is_crt(CREDITS) and not crt.is_crt(SAMPLE) and not bdat.is_bdat(CREDITS)
    check_round_trip(PLUGIN, SAMPLE)
    check_round_trip(PLUGIN, CREDITS)


def test_the_credits_are_read_in_row_order_and_written_with_new_strings():
    texts = ["JAPANESE VOICE CAST", "ELMA", "Houko Kuwashima", "LYNLEE", "Mariya Ise", "JAPANESE VOICE CAST"]
    assert crt.read(CREDITS) == texts
    assert crt.write(CREDITS, texts) == CREDITS
    new = ["ЯПОНСЬКІ АКТОРИ", "ЕЛЬМА", "Houko Kuwashima", "ЛІНЛІ", "Mariya Ise", "ЯПОНСЬКІ АКТОРИ"]
    out = crt.write(CREDITS, new)
    assert crt.read(out) == new and len(out) % 16 == 0
    strings = struct.unpack_from("<I", out, 12)[0]
    for row in range(4):                                                   # rows keep every word but the slot offsets
        before = struct.unpack_from(f"<{crt.WORDS}I", CREDITS, 16 + row * crt.WORDS * 4)
        after = struct.unpack_from(f"<{crt.WORDS}I", out, 16 + row * crt.WORDS * 4)
        assert [w for k, w in enumerate(after) if k not in crt.SLOTS] == [w for k, w in enumerate(before) if k not in crt.SLOTS]
    assert out[strings:].count("ЯПОНСЬКІ АКТОРИ".encode("utf-8")) == 1   # a shared string is stored once
    try:
        crt.write(CREDITS, new[:-1])
    except ValueError as error:
        assert "texts" in str(error)
    else:
        raise AssertionError("a wrong line count must not be written")


def test_a_save_writes_over_the_newest_file_and_checks_the_line_count():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(CREDITS)
    rules.prepare_save_context(SaveContext(relative_path="ui/credit/endroll.crt", existing_versions=lambda: iter([CREDITS])))
    blocks[0][1] = "ЕЛЬМА"
    assert crt.read(rules.save_data_to_json_obj(blocks, names))[1] == "ЕЛЬМА"
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    rules.prepare_save_context(SaveContext(relative_path="bdat/us/common_ms.bdat", existing_versions=lambda: iter([SAMPLE])))
    blocks[0][1] = "Відкрити"
    assert bdat.read(rules.save_data_to_json_obj(blocks, names))[1] == "Відкрити"
    try:
        rules.save_data_to_json_obj([blocks[0][:2]], names)
    except ValueError as error:
        assert "text cells" in str(error)
    else:
        raise AssertionError("a wrong line count must not be written")


def test_the_tag_manager_accepts_the_games_codes_only():
    rules = load_rules(PLUGIN)
    manager = rules.tag_manager_class()
    for tag in ("[ML:icon icon=btn_a ]", "[System:Color name=tutorial ]", "[/System:Color]", "[ST:col p1=green ]", "[ML:undisp ]"):
        assert manager.is_tag_legitimate(tag) and TAG_RE.fullmatch(tag), tag
    for text in ("[color]", "[ML:icon", "plain", "[XX:1]"):
        assert not manager.is_tag_legitimate(text), text


def test_a_mibl_block_in_a_layout_starts_after_the_layout_header():
    """R8 64x64 fills a page exactly, so its footer needs one more page; R8 8x8 leaves room for it."""
    full = mibl.build(Image.new("RGBA", (64, 64), (200, 0, 0, 255)), 1, 1)
    small = mibl.build(Image.new("RGBA", (8, 8), (90, 0, 0, 255)), 1, 1)
    assert len(full) == 8192 and len(small) == 4096
    header = b"LAHD" + bytes(4096 - 4)
    layout = header + small + full
    assert [(k, s, e) for k, s, e in wilay.blocks(layout)] == [("mibl", 4096, 8192), ("mibl", 8192, 16384)]
    textures = wilay.read(layout, {})
    assert [t.image.size for t in textures] == [(8, 8), (64, 64)]
    assert textures[0].image.getpixel((3, 3))[0] == 90 and textures[1].image.getpixel((60, 60))[0] == 200
