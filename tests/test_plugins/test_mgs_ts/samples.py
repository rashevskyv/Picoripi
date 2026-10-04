"""Small Twin Snakes files built in memory for the plugin tests."""
import struct

from plugins.mgs_ts import gcx, subtitles

STAMP = b"\xc3\x5c\x1c\x40"
JAPANESE = b"\x81\x13\x81\x2e\x8c\x01\x82\x19\n"
LINES = {
    "E": [b"Snake, you have to find the chief.\n", b"What is that?\n", b"The base is on the island.\n"],
    "F": [b"Snake, tu dois trouver le chef de la base.\n", b"Qu'est-ce que c'est que ce truc ?\n",
          b"La base est sur une le du nord.\n"],
    "G": [b"Snake, du musst den Chef finden und die Tur offnen.\n", b"Was ist das denn da?\n",
          b"Die Basis ist auf der Insel und nicht hier.\n"],
    "I": [b"Snake, devi trovare il capo per la missione e non.\n", b"Che cosa e quella cosa che ti hai?\n",
          b"La base si trova sull'isola, che non ci sono.\n"],
    "S": [b"Snake, tienes que encontrar el jefe de la base y no.\n", b"Que es eso que se ve por los lados?\n",
          b"La base esta en la isla y no se ve con los ojos.\n"],
    "J": [JAPANESE, JAPANESE, JAPANESE],
}


def table(strings, room=0, binary=b""):
    area, entries = bytearray(), []
    for text in strings:
        entries.append(gcx.STRING_FLAG | len(area))
        area += text + b"\0"
    area += bytes(room)
    if binary:
        area += bytes(-len(area) % 4)
        entries.append(len(area))
        area += binary
    area += bytes(-len(area) % 4)
    table_end = 0x10 + 4 * len(entries)
    data_end = table_end + len(area)
    tail = b"FP\x07\x00" + bytes(12)                  # what follows the data (the kanji bitmaps)
    head = struct.pack("<4I", data_end + len(tail), 0x10, table_end, data_end)
    return head + struct.pack(f"<{len(entries)}I", *entries) + bytes(area) + tail


def talk(index, speaker, clip=None):
    """A codec line: the voice clip (when given), then talk(speaker, face, string)."""
    voice = b"\x0a" + struct.pack("<H", clip) + b"\x00\x00\x01\x05\x04\x8d" if clip is not None else b""
    return (voice + b"\x16\x6d\x13\xeb\x91\x3b\x09\x06" + speaker.to_bytes(3, "little") + b"\x06\x74\xef\xee"
            + b"\xc1\x54\x6d\x0e" + index.to_bytes(3, "little"))


def gcx_file(strings=None, room=0, speakers=(), clips=False):
    """One GCX: build stamp, one hash pair, the table, a script of talk lines."""
    strings = strings if strings is not None else [s for lang in "EFGISJ" for s in LINES[lang]]
    script = b"".join(talk(i, gcx.strcode24(name), clip=(i % 3) + 100 if clips else None)
                      for i, name in speakers)
    return STAMP + struct.pack(">4I", 0x1234, 0x10, 0, 0) + table(strings, room) + script + bytes(8)


def codec_file():
    """Two sections, the first one twice: like codec.dat."""
    first = gcx_file(speakers=[(0, "campbell"), (1, "solid_snake"), (2, "campbell")])
    second = gcx_file([b"Second call.\n", b"Deuxieme appel de la base.\n", b"Zweiter Anruf und die Basis.\n",
                       b"Seconda chiamata e non.\n", b"Segunda llamada y no.\n", JAPANESE],
                      speakers=[(0, "naomi")])
    return first + second + first


def record(lang, texts, speaker=0, frame=0):
    body = bytearray()
    for n, text in enumerate(texts):
        padded = text + b"\0" * (-(len(text) + 1) % 4 + 1)
        body += struct.pack("<4I", n * 100, n * 100 + 90, speaker, 16 + len(padded)) + padded
    size = (0x14 + len(body)) // 16 * 16 + 16
    out = struct.pack(">4I", lang << 16 | subtitles.SUBTITLE, size, frame, 0) + struct.pack("<I", len(body)) + body
    return out + bytes(size - len(out))


def container(slots):
    """A stream file: per slot, stream headers, the records, an end record, padding to 0x800."""
    out = bytearray()
    for records, extra_sectors in slots:
        out += b"\0\0\0\x10\0\0\0\x10\0\0\0\0\0\x01\0\x04"
        out += b"".join(records)
        out += struct.pack(">4I", subtitles.END, 0x10, 0, 0)
        out += bytes(-len(out) % 0x800 + 0x800 * extra_sectors)
    return bytes(out)


def demo_container():
    slot_one = [record(1, [b"It's been a long time, Snake.", b"I should have known\x80|it was you."]),
                record(2, [b"Ca fait longtemps, Snake.", b"J'aurais du savoir que c'etait toi."]),
                record(7, [JAPANESE, JAPANESE])]
    slot_two = [record(1, [b"Hey!"], speaker=gcx.strcode24("enemy")), record(3, [b"He!"])]
    return container([(slot_one, 0), (slot_two, 0)])


def subs_file(kind="cutscene"):
    return subtitles.write(subtitles.scan(demo_container()), kind=kind)


def font_file(widths=(4, 5, 7)):
    """An MGS font of three glyphs, 6 rows high."""
    height = 6
    bitmaps = [bytes(((width * height * 2 + 7) // 8)) for width in widths]
    bitmaps = [bytes([0xFF]) + b[1:] for b in bitmaps]
    data_offset = 8 + 4 * len(widths)
    table, offset = bytearray(struct.pack("<H", data_offset) + b"\x00\x08HL\x00\x00"), 0
    for width, bitmap in zip(widths, bitmaps):
        table += struct.pack("<HH", offset, (width - 1) << 4 | (0x800 if width == 7 else 0))
        offset += len(bitmap)
    return bytes(table) + b"".join(bitmaps) + b"\0\0"
