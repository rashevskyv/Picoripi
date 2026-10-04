"""Small Tingle Tuner files built in memory: a message file and a client program with a tile font."""
import struct

from core.containers import lz10
from plugins.zelda_tingle import tuner

PROGRAM_ADDRESS = 0x0201B000
TILES_AT = 0x100                      # tile block inside the program
TILE_ROOM = 0x400
GLYPHS = 0x20


def message_file(halfword_offsets=False):
    messages = [tuner.encode(text) for text in (
        "{anim:13}{color:4}Tingle Bomb\n{color:0}For {color:2}10 Rupees{color:0}!",
        "Kooloo-limpah!", "Kooloo-limpah!", "{choice2:0} Buy\n  Quit", "")]
    return tuner.pack(tuner.MessageFile(messages, halfword_offsets))


def tiles():
    """Glyph 1 is an 'A'-like letter in ink 15 on background 1; glyph 2 an icon with other colours."""
    data = bytearray(bytes([0x11]) * (GLYPHS * 32))
    data[32:64] = bytes([0x11, 0xF1, 0x1F, 0x11] * 8)
    data[64:96] = bytes(range(32))
    return bytes(data)


def program(text=b""):
    body = bytearray(0x800)
    block = lz10.compress(tiles(), vram=True)
    body[TILES_AT:TILES_AT + len(block)] = block
    body[0x600:0x600 + len(text) + 1] = text + b"\xff"
    return bytes(body)


def client(prog=None):
    head = bytearray(0x1A4)
    stream = lz10.compress(prog if prog is not None else program())
    tail_start = 0x1A4 + len(stream)
    tail = b"TAIL" * 8
    struct.pack_into("<I", head, 0x190, 0x02000000 + tail_start)
    struct.pack_into("<I", head, 0x198, 0x02000000 + tail_start + len(tail))
    return bytes(head) + stream + tail


PARAMS = {
    "program_offset": "0x1A4", "program_address": hex(PROGRAM_ADDRESS), "tail_pointers": ["0x190", "0x198"],
    "tiles_address": hex(PROGRAM_ADDRESS + TILES_AT), "tiles_room": hex(TILE_ROOM), "glyph_offset": "0",
    "glyph_count": GLYPHS, "advance": 6, "chars": {"0x01": "A", "0x03": "Б"},
    "slots": {"codes": {"0x03": "0x05"}, "tables": [["0x03", "0x04", hex(PROGRAM_ADDRESS + 0x700), "0x06"]]},
}
