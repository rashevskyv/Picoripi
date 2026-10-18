"""Rock N' Roll Racing (SNES): the plugin's load, save and build hooks. The real-ROM test skips without the owner's zip."""
import json
from pathlib import Path
import zipfile

import pytest

import romhacking_root
from plugins.rock_n_roll_racing import rom_text as rt
from plugins.rock_n_roll_racing.rules import GameRules, TARGET_ID, TEXT_FILE

USA = ("Rock N Roll Racing", "ISO", "Rock N' Roll Racing (USA).zip")


def _progress(_percent, _text):
    return None


def _never_cancelled():
    return False


def _bank_with(strings):
    return {"format": rt.TEXT_FORMAT, "blocks": [{"id": "text1", "name": "Menus", "strings": [
        {"id": f"{offset:04X}", "offset": offset, "budget": budget, "raw": raw.hex()}
        for offset, budget, raw in strings]}]}


def test_load_shows_text_and_save_keeps_untouched_strings_and_encodes_edits():
    bank = _bank_with([(0xE180, 6, b"PLAYER"), (0xE190, 5, b"AB\rCD")])
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(bank)
    assert blocks == [["PLAYER", "AB\nCD"]]
    assert names == {"0": "Menus"}
    blocks[0][0] = "UA"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert saved["blocks"][0]["strings"][0]["raw"] == b"UA".hex()
    assert saved["blocks"][0]["strings"][1]["raw"] == b"AB\rCD".hex()


def test_save_refuses_a_character_the_game_has_no_code_for():
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(_bank_with([(0xE180, 6, b"PLAYER")]))
    blocks[0][0] = "Г"
    with pytest.raises(ValueError, match="no code"):
        rules.save_data_to_json_obj(blocks, names)


def test_build_target_writes_rom_and_ips_from_the_unpacked_folder(tmp_path):
    rom_bytes = bytearray(rt.ROM_SIZE)
    rom_bytes[rt.HEADER:rt.HEADER + len(rt.TITLE)] = rt.TITLE
    rom_bytes[rt.REGION_OFFSET] = rt.REGION_USA
    rom_bytes[rt.TEXT_START:rt.TEXT_START + 6] = b"PLAYER"
    rom = bytes(rom_bytes)
    source = tmp_path / "source"
    (source / "rom").mkdir(parents=True)
    (source / "rom" / "usa.sfc").write_bytes(rom)
    (source / TEXT_FILE).parent.mkdir(parents=True)
    (source / TEXT_FILE).write_text(json.dumps(rt.extract(rom)), encoding="utf-8")
    translation = tmp_path / "translation"
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(rt.extract(rom))
    blocks[0][0] = "UA"
    edited = rules.save_data_to_json_obj(blocks, names)
    (translation / TEXT_FILE).parent.mkdir(parents=True)
    (translation / TEXT_FILE).write_text(json.dumps(edited), encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    result = GameRules().build_target(TARGET_ID, str(source), str(translation), str(out),
                                      _progress, _never_cancelled)
    patched = Path(result).read_bytes()
    assert patched[rt.TEXT_START:rt.TEXT_START + 6] == b"UA    "
    assert (out / "Rock N' Roll Racing (USA) (UA).ips").read_bytes().startswith(b"PATCH")


@romhacking_root.needs(USA)
def test_real_rom_unpacks_and_builds_a_one_string_patch(tmp_path):
    with zipfile.ZipFile(romhacking_root.path(*USA)) as archive:
        name = next(info.filename for info in archive.infolist() if info.filename.lower().endswith(".sfc"))
        original = archive.read(name)
    usa = tmp_path / "usa.sfc"
    usa.write_bytes(original)
    rules = GameRules()
    source = tmp_path / "source"
    assert rules.unpack_sources({"base": str(usa)}, str(source), _progress, _never_cancelled) == str(source)
    bank = json.loads((source / TEXT_FILE).read_text(encoding="utf-8"))
    blocks, names = rules.load_data_from_json_obj(bank)
    assert blocks[0][0] == "PLAYER"
    blocks[0][0] = "UA"
    translation = tmp_path / "translation"
    (translation / TEXT_FILE).parent.mkdir(parents=True)
    (translation / TEXT_FILE).write_text(
        json.dumps(rules.save_data_to_json_obj(blocks, names), ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    result = rules.build_target(TARGET_ID, str(source), str(translation), str(out), _progress, _never_cancelled)
    patched = Path(result).read_bytes()
    assert len(patched) == len(original)
    changed = [i for i, (a, b) in enumerate(zip(original, patched)) if a != b]
    checksum_field = range(rt.CHECKSUM_OFFSET, rt.CHECKSUM_OFFSET + 4)
    outside = [i for i in changed if not (rt.TEXT_START <= i < rt.TEXT_END) and i not in checksum_field]
    assert changed and not outside
    assert patched[rt.TEXT_START:rt.TEXT_START + 6] == b"UA    "
