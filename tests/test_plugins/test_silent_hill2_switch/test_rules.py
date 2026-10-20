"""Silent Hill 2 Switch rules: the source parse is ASCII, the translation parse and the save use the Ukrainian table."""
from plugins.silent_hill2_pc import mes
from plugins.silent_hill2_switch.rules import GameRules


class _Context:
    def __init__(self, versions):
        self._versions = versions

    def existing_versions(self):
        return iter(self._versions)


def _file(*messages):
    return mes.build([m for m in messages])


def test_source_parse_uses_ascii_and_translation_parse_uses_ukrainian():
    source = _file(bytes([0x41, 0x42]))
    translation = _file(bytes([0x6D, 0xCC]))
    rules = GameRules()
    rules.set_load_role("source")
    assert rules.load_data_from_json_obj(source)[0] == [["ab"]]     # 0x41 shows as the PC font's 'a' (byte + 0x20)
    rules.set_load_role("translation")
    assert rules.load_data_from_json_obj(translation)[0] == [["Ні"]]
    rules.set_load_role("source")


def test_save_encodes_edit_and_keeps_bytes_of_unchanged_message():
    rules = GameRules()
    translation = _file(bytes([0x6D, 0xCC]), bytes([0x8E]))
    rules.prepare_save_context(_Context([translation, _file(b"AB", b"CD")]))
    rules.set_load_role("translation")
    rules.load_data_from_json_obj(translation)
    rules.set_load_role("source")
    out = rules.save_data_to_json_obj([["Ні", "о"]], {})
    assert out == translation
    edited = rules.save_data_to_json_obj([["Ні", "оо"]], {})
    assert mes.split(edited)[1] == bytes([0x8E, 0x8E])


def test_message_header_is_not_shown_and_comes_back_on_save():
    raw = _file(bytes([0x00, 0x80, 0x6D, 0xCC]))
    rules = GameRules()
    rules.set_load_role("translation")
    lines = rules.load_data_from_json_obj(raw)[0][0]
    assert lines == ["Ні"]
    rules.prepare_save_context(_Context([raw]))
    assert rules.save_data_to_json_obj([["Ні"]], {}) == raw


def test_real_translation_file_round_trips_through_the_rules():
    import romhacking_root
    folder = romhacking_root.under(r"Silent Hill\Silent Hill 2\Switch\translation\data\etc\message")
    if not folder.is_dir():
        import pytest
        pytest.skip("Silent Hill 2 Switch translation not here")
    path = next(iter(sorted(folder.glob("*.mes"))))
    raw = path.read_bytes()
    rules = GameRules()
    rules.set_load_role("translation")
    lines = rules.load_data_from_json_obj(raw)[0][0]
    rules.set_load_role("source")
    rules.prepare_save_context(_Context([raw]))
    assert rules.save_data_to_json_obj([lines], {}) == raw
