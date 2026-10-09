"""Pokémon Trinity plugin (Scarlet/Violet, Legends: Z-A): the gfmsg message file (line encryption, padding, flags),
variables as tags, grammar branches whose lengths are written again, and a save over the original file."""
import struct

from core.formats import SaveContext
from plugins.common import gfmsg
from plugins.testing import check_loads, check_round_trip, check_validator, load_rules

PLUGIN = "pokemon_trinity"


def _units(text):
    return list(struct.unpack(f"<{len(text)}H", text.encode("utf-16-le")))


# line 0 "Egg" (flags 4), line 1: a variable, a page break, a gender branch (Master / Miss), a newline
LINES = [(_units("Egg"), 4),
         ([0x10, 2, 0x0101, 0] + _units(" used it!") + [0x10, 1, 0xBE01] + _units("M")
          + [0x10, 3, 0x1100, 0xFF, 0x0305] + _units("asteriss\nok"), 0)]
SAMPLE = gfmsg.write(LINES)


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert {".dat"} <= {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)


def test_the_file_layout_encryption_and_padding():
    assert gfmsg.is_gfmsg(SAMPLE) and gfmsg.read(SAMPLE) == LINES
    count, size = struct.unpack_from("<HI", SAMPLE, 2)[0], struct.unpack_from("<I", SAMPLE, 4)[0]
    assert count == 2 and size + 0x10 == len(SAMPLE)
    offset, length, flags = struct.unpack_from("<iHH", SAMPLE, 0x14)
    assert (offset, length, flags) == (20, 4, 4)                      # "Egg" + terminator, after the line table
    assert struct.unpack_from("<H", SAMPLE, 0x10 + offset)[0] == ord("E") ^ 0x7C89
    assert struct.unpack_from("<i", SAMPLE, 0x1C)[0] % 4 == 0         # lines start on 4 bytes


def test_variables_and_branches_become_tags_and_back():
    text = gfmsg.to_editor(LINES[1][0])
    assert text == "{VAR 0101 0000} used it!{PAGE}M{GENDER 00FF|aster|iss}\nok"
    assert gfmsg.from_editor(text) == LINES[1][0]
    longer = gfmsg.from_editor("М{GENDER 00FF|айстре|іс}")               # the branch lengths follow the text
    assert longer[:1] == _units("М") and longer[1:6] == [0x10, 3, 0x1100, 0xFF, 0x0206]
    assert gfmsg.TAG_RE.fullmatch("{PLURAL 0001||s}") and not gfmsg.TAG_RE.fullmatch("{nope}")


def test_a_save_keeps_the_line_flags_of_the_file_it_writes_over():
    rules = load_rules(PLUGIN)
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    rules.prepare_save_context(SaveContext(relative_path="message/dat/English/common/x.dat",
                                           existing_versions=lambda: iter([SAMPLE])))
    assert rules.save_data_to_json_obj(blocks, names) == SAMPLE
    blocks[0][0] = "Яйце"
    saved = gfmsg.read(rules.save_data_to_json_obj(blocks, names))
    assert saved[0] == (_units("Яйце"), 4) and saved[1] == LINES[1]
