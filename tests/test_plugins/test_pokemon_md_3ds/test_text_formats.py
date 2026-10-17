"""Mystery Dungeon 3DS text formats without game files: the debug label table (8-byte entries, ``message.File``), the
Lua 5.1 script text (``lua_text``: a constant is read and written, a longer text moves the dump's sizes), and the
debug pack in the unpack list. The byte layouts are the ones measured on the real files (see the module docstrings)."""
import struct

from plugins.pokemon_md_3ds import lua_text, message, unpack


def _debug_member(strings):
    """A ``.dbin`` label table: UTF-16 strings from 0x10, a table of (string offset, hash) pairs, the header."""
    body = bytearray()
    pointers = []
    for text in strings:
        pointers.append(0x10 + len(body))
        body += text.encode("utf-16-le") + b"\0\0"
    body += bytes(-len(body) % 4)
    table = 0x10 + len(body)
    for index, pointer in enumerate(pointers):
        body += struct.pack("<II", pointer, 0x1000 + index)
    header = 0x10 + len(body)
    body += struct.pack("<II", len(strings), table)
    body += bytes(-(0x10 + len(body)) % 16)
    pointer_list = 0x10 + len(body)
    offsets = [4, 8] + [table + 8 * i for i in range(len(strings))] + [header + 4]
    last = 0
    for offset in offsets:
        value = offset - last
        last = offset
        chunk = [value & 0x7F]
        value >>= 7
        while value:
            chunk.append(0x80 | (value & 0x7F))
            value >>= 7
        body += bytes(reversed(chunk))
    body += b"\0"
    body += bytes(-(0x10 + len(body)) % 16)
    return b"SIR0" + struct.pack("<III", header, pointer_list, 0) + bytes(body)


def test_a_debug_label_table_reads_its_strings_and_rebuilds_longer_ones():
    raw = _debug_member(["__START__", "TALK_MESSAGE_FRIEND_AFTER_HERO"])
    file = message.File(raw)
    assert file.stride == 8
    assert file.texts("psmd") == ["__START__", "TALK_MESSAGE_FRIEND_AFTER_HERO"]
    assert file.rebuild(file.texts("psmd"), "psmd") == raw
    longer = message.File(raw).rebuild(["__START__", "TALK_MESSAGE_FRIEND_AFTER_HERO_LONGER"], "psmd")
    assert message.File(longer).texts("psmd") == ["__START__", "TALK_MESSAGE_FRIEND_AFTER_HERO_LONGER"]


def test_a_table_of_neither_stride_is_refused():
    raw = bytearray(_debug_member(["a"]))
    header = struct.unpack_from("<I", raw, 4)[0]
    struct.pack_into("<I", raw, header + 4, 0x20)     # the table offset no longer ends at the header
    try:
        message.File(bytes(raw))
    except message.FormatError:
        return
    raise AssertionError("a bad table was read")


def _dump():
    inner = lua_text.Proto(source=b"@x.lua", lines=bytes(8), counts=bytes([0, 0, 1, 2]), code=bytes(8),
                           consts=[lua_text.Const(3, struct.pack("<d", 1.5)),
                                   lua_text.Const(0, None)])
    main = lua_text.Proto(source=b"@x.lua", lines=bytes(8), counts=bytes([0, 0, 1, 2]), code=bytes(4),
                          consts=[lua_text.Const(4, b"name"),
                                  lua_text.Const(4, b"Test constant text."),
                                  lua_text.Const(1, b"\x01")],
                          protos=[inner], lineinfo=[1], locvars=[(b"self", 0, 3)], upvalues=[None])
    return lua_text.dump(main)


def test_a_lua_dump_round_trips_and_its_text_constants_are_the_prose_ones():
    raw = _dump()
    assert lua_text.dump(lua_text.parse(raw)) == raw
    assert lua_text.texts(raw) == ["Test constant text."]


def test_a_longer_text_constant_is_written_back_and_the_dump_still_reads():
    raw = _dump()
    longer = lua_text.rebuild(raw, ["Test constant text, changed for the rebuild."])
    assert len(longer) > len(raw)
    assert lua_text.texts(longer) == ["Test constant text, changed for the rebuild."]
    assert lua_text.rebuild(raw, lua_text.texts(raw)) == raw


def test_a_file_that_is_not_a_lua_dump_is_refused():
    try:
        lua_text.parse(b"SIR0 not lua")
    except lua_text.LuaError:
        return
    raise AssertionError("not a dump was read")


def test_the_debug_pack_is_unpacked_as_dbin_members():
    assert unpack.PSMD_PACKS["message_debug_en.bin"] == "*.dbin"
    assert unpack.PSMD_PACKS["message_en.bin"] == "*.bin"


def test_the_gti_box_flags_a_line_past_its_measured_edge_and_the_smd_box_loads():
    from pathlib import Path

    from plugins.common import message_window as mw
    from plugins.pokemon_md_3ds import rules

    config = Path(rules.__file__).resolve().parent / "config.json"
    gti = mw.BoxFacts.load(config, "dialogue_gti")
    assert gti.text_width == 386 - 66                      # the box edge minus the text origin
    smd = mw.BoxFacts.load(config, "dialogue_psmd")
    assert (smd.text_x, smd.line_pitch, smd.draw_box) == (78, 24.0, False)
