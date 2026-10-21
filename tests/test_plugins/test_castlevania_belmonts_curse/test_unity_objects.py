"""Castlevania: Belmont's Curse fonts and interface texts on synthetic Unity files: a type tree, a format 22 serialized file
with its objects, and a UnityFS bundle around it. The tests write these files themselves; no game data is used."""
import io
import json
import struct

from PIL import Image

from core.unity.binary import Writer
from core.unity.serialized import SerializedFile
from core.unity.typetree import Node, write_value
from core.unity.unityfs import Bundle
from plugins.castlevania_belmonts_curse import fonts, ui_text

CAB = "CAB-synthetic"


def node(kind, name, children=()):
    return Node(type=kind, name=name, size=-1, meta=0, children=list(children))


def _blob(root) -> bytes:
    """A type tree blob (version 22 layout): node count, string buffer size, the nodes, the buffer."""
    buffer = bytearray()
    offsets = {}

    def at(text):
        if text not in offsets:
            offsets[text] = len(buffer)
            buffer.extend(text.encode("utf-8") + b"\x00")
        return offsets[text]

    records = []

    def walk(item, level):
        records.append(struct.pack("<hBBIIiiiQ", 1, level, 0, at(item.type), at(item.name), item.size,
                                   len(records), item.meta, 0))
        for child in item.children:
            walk(child, level + 1)

    walk(root, 0)
    return struct.pack("<ii", len(records), len(buffer)) + b"".join(records) + bytes(buffer)


def _serialized(types, objects) -> bytes:
    """A format 22 serialized file. ``types``: [(class id, root node)]; ``objects``: [(path id, type index, value)]."""
    payloads = []
    for path_id, kind, value in objects:
        writer = Writer("<")
        write_value(types[kind][1], value, writer)
        payloads.append((path_id, kind, bytes(writer.buf)))
    data = bytearray()
    starts = []
    for path_id, kind, raw in payloads:
        data += b"\x00" * (-len(data) % 8)
        starts.append((path_id, len(data), len(raw), kind))
        data += raw
    meta = Writer("<")
    meta.cstr("2022.3.62f2")
    meta.pack("i", 19)                     # target platform
    meta.pack("B", 1)                      # type trees enabled
    meta.pack("i", len(types))
    for class_id, root in types:
        meta.pack("i", class_id)
        meta.pack("B", 0)                  # stripped
        meta.pack("h", -1)                 # script index
        if class_id == 114:
            meta.bytes(bytes(16))          # script id
        meta.bytes(bytes(16))              # old type hash
        meta.bytes(_blob(root))
        meta.pack("i", 0)                  # type dependencies
    meta.pack("i", len(starts))
    for path_id, start, size, kind in starts:
        meta.align(4)
        meta.pack("q", path_id)
        meta.pack("q", start)
        meta.pack("I", size)
        meta.pack("i", kind)
    meta.pack("i", 0)                      # script types
    meta.pack("i", 0)                      # externals
    meta.pack("i", 0)                      # reference types
    metadata = bytes(meta.buf)
    metadata_end = 48 + len(metadata)
    data_offset = metadata_end + (-metadata_end % 16)
    head = bytearray(48)
    struct.pack_into(">I", head, 0, len(metadata))
    struct.pack_into(">I", head, 8, 22)
    struct.pack_into(">I", head, 20, len(metadata))
    struct.pack_into(">qqq", head, 24, data_offset + len(data), data_offset, 0)
    return bytes(head) + metadata + bytes(data_offset - metadata_end) + bytes(data)


def _bundle(serialized: bytes) -> bytes:
    """A UnityFS bundle (format 7, stored blocks) holding the one serialized file ``CAB``."""
    info = bytes(16) + struct.pack(">i", 1) + struct.pack(">IIH", len(serialized), len(serialized), 0)
    info += struct.pack(">i", 1) + struct.pack(">qqI", 0, len(serialized), 4) + CAB.encode("utf-8") + b"\x00"
    head = bytearray(b"UnityFS\x00") + struct.pack(">I", 7) + b"5.x.x\x00" + b"2022.3.62f2\x00"
    head += struct.pack(">q", 0) + struct.pack(">III", len(info), len(info), 0x40)
    head += b"\x00" * (-len(head) % 16)
    return bytes(head) + info + serialized


def _texture_root():
    return node("Texture2D", "Base", [
        node("string", "m_Name"), node("int", "m_Width"), node("int", "m_Height"),
        node("int", "m_TextureFormat"), node("int", "m_CompleteImageSize"),
        node("TypelessData", "image data"),
        node("StreamingInfo", "m_StreamData", [node("UInt64", "offset"), node("UInt32", "size"),
                                               node("string", "path")]),
    ])


def _font_root():
    pptr = node("PPtr", "data", [node("int", "m_FileID"), node("SInt64", "m_PathID")])
    return node("MonoBehaviour", "Base", [
        node("string", "m_Name"),
        node("vector", "m_GlyphTable", [node("Array", "Array", [node("int", "size"),
                                                                node("struct", "data", [node("int", "m_Index")])])]),
        node("vector", "m_AtlasTextures", [node("Array", "Array", [node("int", "size"), pptr])]),
        node("int", "m_AtlasWidth"), node("int", "m_AtlasHeight"),
    ])


def _text_root():
    return node("MonoBehaviour", "Base", [
        node("string", "m_Name"), node("string", "m_text"), node("int", "m_fontAsset"), node("float", "m_fontSize"),
    ])


def _font_bundle() -> bytes:
    """A bundle with one TextMesh Pro font asset, its 4x4 Alpha8 atlas inline (path ids 1 and 2)."""
    font = {"m_Name": "LatinFont", "m_GlyphTable": [{"m_Index": 0}, {"m_Index": 1}],
            "m_AtlasTextures": [{"m_FileID": 0, "m_PathID": 2}], "m_AtlasWidth": 4, "m_AtlasHeight": 4}
    atlas = {"m_Name": "LatinFont Atlas", "m_Width": 4, "m_Height": 4, "m_TextureFormat": 1,
             "m_CompleteImageSize": 16, "image data": list(range(16)), "m_StreamData": {"offset": 0, "size": 0,
                                                                                     "path": ""}}
    types = [(114, _font_root()), (28, _texture_root())]
    return _bundle(_serialized(types, [(1, 0, font), (2, 1, atlas)]))


def _ui_bundle() -> bytes:
    """A bundle with two shown texts, one placeholder and one empty text (path ids 10 to 13)."""
    texts = [(10, "Start"), (11, "New Text"), (12, ""), (13, "Options")]
    objects = [(path, 0, {"m_Name": f"Label{path}", "m_text": text, "m_fontAsset": 77, "m_fontSize": 20.0})
               for path, text in texts]
    return _bundle(_serialized([(114, _text_root())], objects))


def test_font_pair_round_trips_and_the_atlas_takes_its_new_size():
    original = _font_bundle()
    pairs = fonts.font_pairs(original)
    assert set(pairs) == {"LatinFont"}
    font_json, atlas_png = pairs["LatinFont"]
    assert json.loads(font_json.decode("utf-8"))["m_AtlasWidth"] == 4
    assert Image.open(io.BytesIO(atlas_png)).size == (4, 4)

    edited = json.loads(font_json.decode("utf-8"))
    edited["m_AtlasWidth"], edited["m_AtlasHeight"] = 8, 8
    edited["m_GlyphTable"].append({"m_Index": 2})
    bigger = Image.new("L", (8, 8), 200)
    built = fonts.build_font_bundle(original, {"LatinFont": (json.dumps(edited).encode("utf-8"), _png(bigger))})
    assert built is not None
    again = fonts.font_pairs(built)["LatinFont"]
    assert json.loads(again[0].decode("utf-8")) == edited
    assert Image.open(io.BytesIO(again[1])).size == (8, 8)
    assert set(Image.open(io.BytesIO(again[1])).getdata()) == {200}


def test_an_unchanged_font_pair_writes_no_bundle():
    original = _font_bundle()
    assert fonts.build_font_bundle(original, fonts.font_pairs(original)) is None


def test_a_font_pair_with_other_fields_is_refused():
    original = _font_bundle()
    font_json, atlas_png = fonts.font_pairs(original)["LatinFont"]
    edited = json.loads(font_json.decode("utf-8"))
    edited["m_Extra"] = 1
    try:
        fonts.build_font_bundle(original, {"LatinFont": (json.dumps(edited).encode("utf-8"), atlas_png)})
    except ValueError as error:
        assert "other fields" in str(error)
    else:
        raise AssertionError("a font with extra fields must be refused")


def test_shown_texts_skip_placeholders_and_empty_texts():
    entries, unread = ui_text.entries(_ui_bundle())
    assert unread == 0
    assert entries == [(f"{CAB}/10", "Start"), (f"{CAB}/13", "Options")]


def test_a_text_is_written_back_and_the_other_fields_keep_their_values():
    data = _ui_bundle()
    built = ui_text.build_bundle(data, {f"{CAB}/10": "Почати", f"{CAB}/12": ""})
    assert built is not None
    entries, _unread = ui_text.entries(built)
    assert entries == [(f"{CAB}/10", "Почати"), (f"{CAB}/13", "Options")]
    serialized = SerializedFile(Bundle(built).read(CAB))
    value = serialized.read(10)
    assert value["m_fontAsset"] == 77 and value["m_fontSize"] == 20.0 and value["m_Name"] == "Label10"


def test_writing_the_same_text_gives_no_bundle():
    assert ui_text.build_bundle(_ui_bundle(), {f"{CAB}/10": "Start"}) is None


def test_a_table_name_drops_the_content_hash():
    assert ui_text.table_name("ui-hud_assets_all_8ddf9cf77c0a67facd6afb06596def1a.bundle") == "ui-hud"
    assert ui_text.table_name("room-cemetery2_room25_uid113_scenes_all_7b232b1c0c4cf284327b0257c8ef0e8f.bundle") \
        == "room-cemetery2_room25_uid113"


def _png(image) -> bytes:
    from io import BytesIO
    out = BytesIO()
    image.save(out, "PNG")
    return out.getvalue()
