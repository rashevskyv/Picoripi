"""Skyward Sword plugin (HD and Wii): big-endian MSBT with readable tags, ATR1 windows and speakers, MSBF
conversations, version-dependent widths, reference languages by label, and a source folder project end to
end. Synthetic files only (real-file checks: test_real_data.py)."""
import struct
from types import SimpleNamespace

from core.data_state_processor import DataStateProcessor
from core.project_manager import ProjectManager
from core.project_models import Project
from handlers.project_action.load_worker import ProjectLoadWorker
from plugins.common.msbt import Msbt
from plugins.testing import check_round_trip
from plugins.zelda_sshd import messages, msbf, reference, tags
from plugins.zelda_sshd.rules import BOX_WIDTHS, HD, WII, GameRules

PLUGIN = "zelda_sshd"


def _section(magic: bytes, body: bytes, pad: bytes = b"\xab") -> bytes:
    data = magic + struct.pack(">I", len(body)) + b"\x00" * 8 + body
    return data + pad * (-len(data) % 16)


def _labels(names) -> bytes:
    entries = b"".join(bytes([len(name)]) + name.encode() + struct.pack(">I", index) for index, name in enumerate(names))
    return struct.pack(">III", 1, len(names), 12) + entries


def text(*parts) -> bytes:
    """A TXT2 entry (UTF-16BE): str parts and (group, type, params) tags."""
    out = b""
    for part in parts:
        out += part.encode("utf-16-be") if isinstance(part, str) else \
            struct.pack(">HHHH", 0x0E, part[0], part[1], len(part[2])) + part[2]
    return out + b"\x00\x00"


def msbt(entries) -> bytes:
    """A Skyward Sword MSBT (LBL1, ATR1 of 3 bytes, TXT2); ``entries`` is ``[(label, text bytes, box, speaker)]``."""
    atr1 = struct.pack(">II", len(entries), 3) + b"".join(bytes([box, 0, speaker]) for _l, _t, box, speaker in entries)
    texts = [entry[1] for entry in entries]
    offsets, position = [], 4 + 4 * len(texts)
    for entry_text in texts:
        offsets.append(position)
        position += len(entry_text)
    txt2 = struct.pack(f">I{len(texts)}I", len(texts), *offsets) + b"".join(texts)
    body = _section(b"LBL1", _labels([e[0] for e in entries])) + _section(b"ATR1", atr1) + _section(b"TXT2", txt2)
    header = b"MsgStdBn" + b"\xfe\xff" + b"\x00\x00" + bytes([1, 3]) + struct.pack(">HHI", 3, 0, 0x20 + len(body))
    return header + b"\x00" * 10 + body


def flow(nodes, branches, entries) -> bytes:
    """An MSBF: ``nodes`` are (type, next, value at 12, value at 14); ``entries`` {label: node}."""
    raw = struct.pack(">HH", len(nodes), len(branches)) + bytes(12)
    for kind, following, at12, at14 in nodes:
        raw += struct.pack(">BBHHHHHHH", kind, 0xFF, 0, 0, 0, following, 0x54, at12, at14)
    raw += struct.pack(f">{len(branches)}H", *branches)
    names = sorted(entries, key=entries.get)
    fen1 = struct.pack(">III", 1, len(names), 12) + b"".join(
        bytes([len(name)]) + name.encode() + struct.pack(">I", entries[name]) for name in names)
    body = _section(b"FLW3", raw) + _section(b"FEN1", fen1)
    return b"MsgFlwBn\xfe\xff\x00\x00\x00\x03\x00\x02" + struct.pack(">I", 0x20 + len(body)) + bytes(12) + body


RED, DEFAULT = (0, 3, b"\x00\x00"), (0, 3, b"\xff\xff")
HERO, WAIT, FACE = (2, 0, b""), (1, 4, b"\x00\x0f"), (1, 9, b"\x00\x0a\x07\x05")
TERRY = msbt([
    ("TERY_01", text(FACE, "Hey, ", HERO, "!", WAIT, " Buy a ", RED, "Bomb", DEFAULT, "?"), 1, 0),
    ("TERY_02", text("Thank you!"), 1, 0),
    ("FAI_01", text("Master, I calculate a 60% probability."), 2, 0),
    ("TERY_99", text("Not shown by any flow."), 1, 0),
])
TERRY_TEXT = ["{face:0:10:7:5}Hey, {heroName}!{wait:15} Buy a {color:Red}Bomb{color:Default}?", "Thank you!",
              "Master, I calculate a 60% probability.", "Not shown by any flow."]
# entry 105_01 -> message 0 -> branch -> message 1 / message 2; entry 105_02 -> message 2
TERRY_FLOW = flow([(4, 1, 0, 0), (1, 2, 0, 0), (2, 0xFFFF, 2, 0), (1, 0xFFFF, 1, 0), (1, 0xFFFF, 2, 0),
                   (4, 4, 0, 0)], [3, 4], {"105_01": 0, "105_02": 5})


def test_the_sample_survives_load_and_save():
    check_round_trip(PLUGIN, TERRY)


def test_tags_have_names_and_round_trip():
    tokens = Msbt(TERRY).messages
    assert [tags.to_editor(m, False) for m in tokens] == TERRY_TEXT
    assert [tags.from_editor(shown, False) for shown in TERRY_TEXT] == tokens
    for shown in ("{item:11}", "{count:0:2}", "{word:3}", "{icon:41}", "{speed:-5}", "{textSize:1}",
                  "{choice1:65535}", "{endWait:75:0}", "{sup}", "{/sup}", "{ctl17:8}", "{tag:9:1:0102}"):
        assert tags.render_tag(tags.parse_tag(shown, ">"), False) == shown
    assert tags.parse_tag("{speed:-5}", ">").params == b"\xfb\xcd"      # odd length: 0xCD pad, as the game
    assert "colour" in tags.describe("{color:Red}")
    assert tags.from_editor("{not a tag} text", False) == ["{not a tag} text"]


def test_unchanged_messages_keep_their_bytes_and_edits_keep_labels_and_attributes():
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(TERRY)
    assert blocks == [TERRY_TEXT]
    assert rules.save_data_to_json_obj(blocks, names) == TERRY
    edited = ["{face:0:10:7:5}Гей, {heroName}! Ґанок, їжа, є, пам’ять?", *TERRY_TEXT[1:]]
    saved = Msbt(rules.save_data_to_json_obj([edited], names))
    assert saved.labels == Msbt(TERRY).labels and saved.section(b"ATR1") == Msbt(TERRY).section(b"ATR1")
    assert tags.to_editor(saved.messages[0], False) == edited[0]
    assert saved.messages[1:] == Msbt(TERRY).messages[1:]


def test_conversations_follow_the_flow_from_each_entry():
    assert msbf.conversations(TERRY_FLOW) == {0: "105_01", 1: "105_01", 2: "105_01"}


def test_speakers_come_from_the_speaker_byte_fis_window_and_the_files_owner():
    assert messages.attributes(Msbt(TERRY).section(b"ATR1"), 2) == {"box": 2, "speaker_byte": 0}
    assert messages.speaker("105-Terry", "TERY_01", 1) == "Beedle"
    assert messages.speaker("100-Town", "TW_03", 2) == "Fi"
    assert messages.speaker("100-Town", "TW_01", 1) is None
    assert messages.speaker("599-Demo", "Demo62_01:01") == "Zelda"          # HD ATR1 speaker byte (table)


def test_reference_paths_map_a_project_file_to_its_archive_member():
    assert reference.locate("US/Object/en_US/1-Town/105-Terry.msbt") == \
        ("object", "1-Town", "1-Town/105-Terry.msbt", "en_US")
    assert reference.locate("Layout/Title2D/text/en_US_titleBG_00.msbt") == \
        ("layout", "Title2D", "text/{lang}_titleBG_00.msbt", "en_US")
    assert reference.locate("US/Layout/Title2D/text/en_US_titleBG_00.msbt")[1] == "Title2D"


def u8(files) -> bytes:
    """A U8 archive of ``{path: bytes}`` (one folder level), laid out as Nintendo's tools do."""
    folders = sorted({path.split("/")[0] for path in files if "/" in path})
    names, nodes = b"\x00", []

    def name(text_name):
        nonlocal names
        at = len(names)
        names += text_name.encode() + b"\x00"
        return at

    data, blobs = 0, []
    nodes.append([1, 0, 0, 0])
    for folder in folders:
        index = len(nodes)
        nodes.append([1, name(folder), 0, 0])
        for path in sorted(p for p in files if p.startswith(folder + "/")):
            nodes.append([0, name(path.split("/", 1)[1]), data, len(files[path])])
            blobs.append(files[path])
            data += len(files[path]) + (-len(files[path]) % 32)
        nodes[index][3] = len(nodes)
    nodes[0][3] = len(nodes)
    head = 0x20 + len(nodes) * 12 + len(names)
    start = head + (-head % 32)
    table = b"".join(struct.pack(">III", kind << 24 | at, off + start if kind == 0 else off, size)
                     for kind, at, off, size in nodes)
    body = b"".join(blob + bytes(-len(blob) % 32) for blob in blobs)
    return (b"\x55\xaa\x38\x2d" + struct.pack(">III", 0x20, len(nodes) * 12 + len(names), start) + bytes(16)
            + table + names + bytes(start - head) + body)


def _project(tmp_path, layout="Layout"):
    source = tmp_path / "source"
    story = source / "US" / "Object" / "en_US" / "1-Town"
    story.mkdir(parents=True)
    (story / "105-Terry.msbt").write_bytes(TERRY)
    (story / "105-Terry.msbf").write_bytes(TERRY_FLOW)
    title = msbt([("T_startText_00:00", text("Start"), 0, 0)])
    (source / layout / "Title2D" / "text").mkdir(parents=True)
    (source / layout / "Title2D" / "text" / "en_US_titleBG_00.msbt").write_bytes(title)
    manager = ProjectManager()
    manager.project_dir = str(tmp_path)
    manager.project_file_path = str(tmp_path / "project.uiproj")
    manager.project = Project(name="SS", plugin_name=PLUGIN)
    manager.project.metadata = {"source_path": str(source), "translation_path": str(tmp_path / "translation"),
                                "is_directory_mode": True}
    rules = GameRules()
    manager.sync_project_files(plugin=rules)
    results = []
    worker = ProjectLoadWorker(manager, rules)
    worker.finished_with_result.connect(results.append)
    worker.run()
    loaded = results[0]
    rules.mw = SimpleNamespace(project_manager=manager, block_to_project_file_map=loaded["block_to_project_file_map"],
                               font_map={"S": {"width": 20}, "t": {"width": 10}, "a": {"width": 10},
                                         "r": {"width": 10}})
    blocks = {name: int(index) for index, name in loaded["block_names"].items()}
    return rules, manager, loaded, blocks


def test_an_hd_source_folder_gives_context_and_saves_only_the_edit(tmp_path):
    rules, manager, loaded, blocks = _project(tmp_path)
    terry, title = blocks["105-Terry"], blocks["en_US_titleBG_00"]
    assert loaded["data"][terry] == TERRY_TEXT
    assert rules.version() == HD
    assert rules.get_speaker_for_string(terry, 0) == "Beedle"
    assert rules.get_speaker_for_string(terry, 2) == "Fi"
    assert rules.get_speaker_for_string(title, 0) is None
    assert rules.get_string_layout(terry, 0) == {"warn_width": BOX_WIDTHS[HD][1], "max_width": BOX_WIDTHS[HD][1],
                                                 "font_file": "normal_00_hd.json", "lines_per_page": 4}
    assert rules.get_string_layout(title, 0)["max_width"] == 96          # "Start" = 60 units, x1.6
    assert rules.get_ai_flow_group_for_string(terry, 0) == rules.get_ai_flow_group_for_string(terry, 1) == \
        "ss:105-Terry:105_01"
    assert rules.get_ai_flow_group_for_string(terry, 3) is None
    scene = rules.get_scene_context_for_string(terry, 0)
    assert (scene["label"], scene["msg_group"], scene["location_candidates"]) == \
        ("TERY_01", "105_01", ["Skyloft and the Sky"])
    assert "conversation 105_01" in rules.get_ai_flow_context_for_string(terry, 0)
    assert rules.get_translation_context_for_string(title, 0)["has_speaker"] is False
    assert rules.calculate_string_width_override("{heroName}{icon:3}", {"L": {"width": 5}, "i": {"width": 1},
                                                                         "n": {"width": 2}, "k": {"width": 3}}) == 11 + 45

    output = [list(rows) for rows in loaded["data"]]
    output[terry][1] = "Дякую, ґаздо! Їжте, є пам’ять."
    mw = SimpleNamespace(state=None, project_manager=manager, current_game_rules=rules,
                         block_to_project_file_map=loaded["block_to_project_file_map"],
                         data_store=SimpleNamespace(block_names=loaded["block_names"],
                                                    edited_data={(terry, 1): output[terry][1]}))
    saved, _warnings, errors = DataStateProcessor(mw)._perform_save_impl(output)
    assert (saved, errors) == (True, [])
    written = Msbt((tmp_path / "translation" / "US" / "Object" / "en_US" / "1-Town" / "105-Terry.msbt").read_bytes())
    assert [tags.to_editor(m, False) for m in written.messages] == [TERRY_TEXT[0], output[terry][1], *TERRY_TEXT[2:]]
    assert written.messages[0] == Msbt(TERRY).messages[0]


def test_a_wii_source_folder_uses_the_wii_widths_and_fonts(tmp_path):
    rules, _manager, _loaded, blocks = _project(tmp_path, layout="US/Layout")
    assert rules.version() == WII
    assert rules.get_string_layout(blocks["105-Terry"], 0)["max_width"] == BOX_WIDTHS[WII][1] == 650
    assert rules.calculate_string_width_override("Yes{choice1:65535}No way{choice2:0}No", {"Y": {"width": 9}, "e": {"width": 5}, "s": {"width": 5}, "N": {"width": 10}, "o": {"width": 5}, " ": {"width": 3}, "w": {"width": 7}, "a": {"width": 5}, "y": {"width": 5}}) == 35
    sources = {entry["font_map"]: entry.get("params", {}) for entry in rules.get_font_sources() if "font_map" in entry}
    assert sources == {"normal_00_wii.json": {"min_sheets": 29}, "special_00_wii.json": {"min_sheets": 17},
                       "normal_02_wii.json": {"min_sheets": 3}}
    others = [entry for entry in rules.get_font_sources() if "font_map" not in entry]
    assert others and all("params" not in entry for entry in others)     # icons, HOME Menu...: sheets as they are


HOME_CSV = ('"接続"\t"Press ① and ②\r\non each Wii Remote."\t"Bitte"\r\n'
            '"リセット"\t"Reset the software?"\t"Zurücksetzen?"\r\n')
BOM = b"\xfe\xff"


def test_the_wii_home_menu_table_edits_only_the_english_cell(tmp_path):
    raw = BOM + HOME_CSV.encode("utf-16-be")
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    assert blocks == [["Press ① and ②\non each Wii Remote.", "Reset the software?"]]
    assert rules.save_data_to_json_obj(blocks, names) == raw
    edited = rules.save_data_to_json_obj([['UA "TEST"\nline', "Reset the software?"]], names)
    assert edited == BOM + HOME_CSV.replace("Press ① and ②\r\non each Wii Remote.",
                                            'UA ""TEST""\r\nline').encode("utf-16-be")
    # in a project: the table is a block, the save keeps the other languages of the file
    home = tmp_path / "source" / "HomeButton2"
    home.mkdir(parents=True)
    (home / "home.csv").write_bytes(raw)
    rules, manager, loaded, blocks = _project(tmp_path, layout="US/Layout")
    index = blocks["home"]
    assert loaded["data"][index][1] == "Reset the software?"
    output = [list(rows) for rows in loaded["data"]]
    output[index][1] = "UA TEST"
    mw = SimpleNamespace(state=None, project_manager=manager, current_game_rules=rules,
                         block_to_project_file_map=loaded["block_to_project_file_map"],
                         data_store=SimpleNamespace(block_names=loaded["block_names"],
                                                    edited_data={(index, 1): "UA TEST"}))
    saved, _warnings, errors = DataStateProcessor(mw)._perform_save_impl(output)
    assert (saved, errors) == (True, [])
    written = (tmp_path / "translation" / "HomeButton2" / "home.csv").read_bytes()
    assert written == raw.replace("Reset the software?".encode("utf-16-be"), "UA TEST".encode("utf-16-be"))


def test_reference_languages_match_by_label_and_put_russian_first(tmp_path):
    rules, _manager, _loaded, blocks = _project(tmp_path)
    terry = blocks["105-Terry"]
    romfs = tmp_path / "romfs"
    russian = msbt([("TERY_02", text("Спасибо!"), 1, 0), ("TERY_01", text("Эй, ", HERO, "!"), 1, 0)])
    french = msbt([("TERY_01", text("Salut !"), 1, 0)])
    for folder, lang, data in (("RU", "ru_RU", russian), ("US", "fr_US", french)):
        (romfs / folder / "Object" / lang).mkdir(parents=True)
        (romfs / folder / "Object" / lang / "1-Town.arc").write_bytes(u8({"1-Town/105-Terry.msbt": data}))
    found = rules.load_multi_reference(str(romfs), {str(terry): "105-Terry"})
    assert list(found) == ["Russian (RU)", "French (US)"]
    assert found["Russian (RU)"] == {(terry, 0): "Эй, {heroName}!", (terry, 1): "Спасибо!"}
    assert found["French (US)"] == {(terry, 0): "Salut !"}


def test_the_wii_channel_banner_shows_its_members_decompressed_and_hashes_them_again():
    import hashlib

    from core.containers import lz10
    from plugins.zelda_sshd.banner import WiiBannerContainer

    def imd5(plain: bytes) -> bytes:
        payload = b"LZ77" + lz10.compress(plain)
        return b"IMD5" + struct.pack(">I", len(payload)) + bytes(8) + hashlib.md5(payload).digest() + payload

    inner = u8({"arc/a.tpl": b"\x00\x20\xaf\x30" + bytes(60)})
    head = bytes(0x40) + b"IMET" + bytes(0x600 - 0x44)
    raw = head + u8({"meta/banner.bin": imd5(inner), "meta/sound.bin": b"BNS " + bytes(28)})
    container = WiiBannerContainer(raw)
    assert WiiBannerContainer.can_handle(raw) and not WiiBannerContainer.can_handle(inner)
    assert container.read_file("meta/banner.bin") == inner
    container.write_file("meta/banner.bin", inner)
    assert container.pack() == raw                      # an unchanged member keeps its stored bytes
    changed = inner.replace(bytes(60), b"\x11" * 60)
    container.write_file("meta/banner.bin", changed)
    again = WiiBannerContainer(container.pack())
    assert again.read_file("meta/banner.bin") == changed
    stored = again._u8.read_file("meta/banner.bin")
    assert stored[16:32] == hashlib.md5(stored[32:]).digest()
    assert again.pack()[:0x600] == head
