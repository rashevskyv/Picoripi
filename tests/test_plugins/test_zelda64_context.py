"""Zelda 64 context extractor: text-id heuristics, message decoding, scene actor lists, the JSON from a tiny decomp."""
import json
import struct

from plugins.common import zelda64_context as ctx

ACTOR_SOURCE = """/*
 * File: z_en_ma4.c
 * Overlay: ovl_En_Ma4
 * Description: Romani (ranch girl)
 */
#define ENMA4_TEXT_GREETING 0x3335
typedef struct ShopEntry {
    /* 0x00 */ s16 objectId;
    /* 0x02 */ u16 descriptionTextId;
} ShopEntry;
static ShopEntry sEntries[] = { { OBJECT_GI_RUPY, 0x0083 }, { OBJECT_GI_BOMB, 0x0844 } };
static u16 sTextIds[] = { 0x3340, 0x3341 };
static s16 sOther[] = { 0x1234 };
static u16 D_80BF048C[] = { 0x3350 };

u16 EnMa4_GetTextId(EnMa4* this) {
    return this->flag ? 0x3336 : 0x3337;
}

void EnMa4_Talk(EnMa4* this, PlayState* play) {
    Message_StartTextbox(play, 0x0042, &this->actor);   // item message, passed straight to the textbox
    this->actor.textId = this->day == 1 ? 0x3338 : 0x3339;
    player->actor.textId = D_80BF048C[params];
    if (this->textId == 0x333A) {}
    MSCRIPT_CMD_BEGIN_TEXT(0x333B),
    MSCRIPT_CMD_CHECK_TEXT_CHOICE(0x0010, 0x0200, 0x0),
    switch (this->textId) {
        case 0x333C:
            break;
        case 0x2:
            break;
    }
    switch (this->state) {
        case 0x4444:
            break;
    }
    SubS_OfferTalkExchangeFacing(&this->actor, play, 100.0f, 100.0f, PLAYER_IA_NONE, 0x2000, 0x2000);
    gDPLoadTextureBlock(gfx++, tex, G_IM_FMT_I, 0x0400, 48);
    this->textIdIndex = 0x5;
    Math_SmoothStepToS(&this->actor.world.rot.y, yaw, 10, 0x3000, 0x100);
    // Message_StartTextbox(play, 0x7777, NULL); a comment is not code
}
"""


def test_scan_text_ids_takes_text_contexts_only():
    ids = ctx.scan_text_ids(ACTOR_SOURCE)
    assert ids == {0x3335, 0x0083, 0x0844, 0x3340, 0x3341, 0x3350, 0x3336, 0x3337, 0x0042,
                   0x3338, 0x3339, 0x333A, 0x333B, 0x333C}


def _mm(body: bytes, next_id: int = 0xFFFF) -> bytes:
    return bytes([0, 0, 0xFE]) + struct.pack(">H", next_id) + b"\xff" * 6 + body + b"\xbf"


def test_decode_message_mm_and_oot():
    mm = ctx.decode_message("mm", _mm(b"You got the \x01Hero's\x11Bow\x00!\x10\x03Blue\x00", next_id=0x1234))
    assert mm.text == "You got the Hero's Bow! Blue"
    assert mm.spans == [(0x01, "Hero's Bow"), (0x03, "Blue")]
    assert mm.links == [0x1234]
    oot = ctx.decode_message("oot", b"Go to \x05\x41Kokiri\x01Forest\x05\x40.\x07\x10\x9d\x02")
    assert oot.text == "Go to Kokiri Forest."
    assert oot.spans == [(0x41, "Kokiri Forest")]
    assert oot.links == [0x109D]


def test_read_message_table():
    data = b"AAAA" + b"BBBBBBBB"
    code = b"\0" * 8 + struct.pack(">HBBI", 0x0001, 0, 0, 0x07000000) + struct.pack(">HBBI", 0x0102, 0, 0, 0x07000004)
    code += struct.pack(">HBBI", 0xFFFF, 0, 0, 0x0700000C)
    assert ctx.read_message_table(code, 8, data) == {0x0001: b"AAAA", 0x0102: b"BBBBBBBB"}


class FakeRom:
    """dmadata-like file list: (vrom start, vrom end, rom start, rom end) and contents."""

    def __init__(self, blobs):
        self.blobs = blobs
        self.files = [(0x1000 * i, 0x1000 * i + len(b), 0, 0) for i, b in enumerate(blobs)]

    def read_file(self, index):
        return self.blobs[index]


def test_scene_placements_reads_rooms_and_alternate_headers():
    # room: main header with one actor, alternate header list -> second header with another actor
    room = bytearray(0x80)
    struct.pack_into(">BBHI", room, 0x00, 0x18, 0, 0, 0x03000030)
    struct.pack_into(">BBHI", room, 0x08, 0x01, 1, 0, 0x03000040)
    struct.pack_into(">BBHI", room, 0x10, 0x14, 0, 0, 0)
    struct.pack_into(">II", room, 0x30, 0, 0x03000020)
    struct.pack_into(">BBHI", room, 0x20, 0x01, 1, 0, 0x03000050)
    struct.pack_into(">BBHI", room, 0x28, 0x14, 0, 0, 0)
    struct.pack_into(">H12xH", room, 0x40, 0x2005, 0x0310)    # MM keeps flags in the top bits of the id
    struct.pack_into(">H12xH", room, 0x50, 0x0006, 0x0001)
    scene = bytearray(0x40)
    struct.pack_into(">BBHI", scene, 0x00, 0x04, 1, 0, 0x02000020)
    struct.pack_into(">BBHI", scene, 0x08, 0x14, 0, 0, 0)
    struct.pack_into(">II", scene, 0x20, 0x1000, 0x1080)       # room 0 = file 1
    rom = FakeRom([bytes(scene), bytes(room)])
    scenes = {0: {"segment": "test_scene", "name": "Test", "enum": "SCENE_TEST", "title_text_id": 0}}
    placed = ctx.scene_placements(rom, ["test_scene", "test_room_0"], scenes, 0x1FFF)
    assert placed == {0: [(0x0005, 0x0310), (0x0006, 0x0001)]}


def _decomp(tmp_path):
    root = tmp_path / "mm"
    (root / "include/tables").mkdir(parents=True)
    (root / "include/tables/actor_table.h").write_text(
        "/* 0x000 */ DEFINE_ACTOR_INTERNAL(Player, ACTOR_PLAYER, ALLOCTYPE_NORMAL, \"Player\")\n"
        "/* 0x001 */ DEFINE_ACTOR(En_Ma4, ACTOR_EN_MA4, ALLOCTYPE_NORMAL, \"En_Ma4\")\n")
    (root / "include/tables/scene_table.h").write_text(
        "// Romani Ranch\n/* 0x00 */ DEFINE_SCENE(Z2_F01, SCENE_F01, 0x0120, CFG, RESTRICTIONS_NONE, FLAGS)\n")
    (root / "include/tables/notebook_table.h").write_text(
        "/* 0x00 */ DEFINE_PERSON(BOMBERS_NOTEBOOK_PERSON_ROMANI, gTex, 0x21CE, EVENT, 0x2138, FLAG)\n")
    (root / "include/z64actor.h").write_text("    /* 0x05 */ TATL_HINT_ID_RED_CHUCHU,\n")
    actor = root / "src/overlays/actors/ovl_En_Ma4"
    actor.mkdir(parents=True)
    (actor / "z_en_ma4.c").write_text(ACTOR_SOURCE + "void f(void) { this->actor.hintId = TATL_HINT_ID_RED_CHUCHU; }\n")
    player = root / "src/overlays/actors/ovl_player_actor"
    player.mkdir(parents=True)
    (player / "z_player.c").write_text(
        " * Description: Player\n    GET_ITEM(ITEM_BOW, OBJECT_GI_BOW, GID_BOW, 0x22, 0x80, CHEST_ANIM_LONG),\n")
    (root / "src/code").mkdir(parents=True)
    (root / "src/code/z_message.c").write_text("void f(void) { Message_StartTextbox(play, 0x1B93, NULL); }\n")
    return root


def test_build_context_without_rom(tmp_path):
    context = ctx.build_context("mm", _decomp(tmp_path))
    messages = context["messages"]
    assert messages["0x3338"] == {"speakers": ["Romani (ranch girl)"], "actors": ["En_Ma4"], "scenes": []}
    assert messages["0x1B93"]["actors"] == ["code/z_message"] and messages["0x1B93"]["speakers"] == []
    assert messages["0x1905"]["speakers"] == ["Tatl"]
    assert messages["0x1905"]["about"] == "Romani (ranch girl)"
    assert messages["0x21CE"]["notebook"] == "person: Romani"
    assert context["stats"]["messages_with_actor"] == len(ctx.scan_text_ids(ACTOR_SOURCE)) + 2
    assert [g["term"] for g in context["glossary"]] == ["Romani"]   # without a ROM no text to verify more
    assert json.loads(ctx.dumps(context)) == context


def test_cli_writes_json(tmp_path):
    out = tmp_path / "context.json"
    assert ctx.main(["--game", "mm", "--decomp", str(_decomp(tmp_path)), "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data) == {"source", "messages", "glossary", "stats"}
    assert data["source"]["game"] == "mm" and not (tmp_path / "context.json.tmp").exists()
