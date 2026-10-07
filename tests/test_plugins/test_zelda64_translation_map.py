"""The N64 Zelda plugins write Ukrainian into font slots of one map (``translation_map.json``): the same map
feeds the encoder, the decoder, the width check and the Font Editor, so a letter always lands on the glyph
drawn for it."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from plugins.zelda_mm64.rules import GameRules as MajoraRules
from plugins.zelda_oot64.rules import GameRules as OcarinaRules

PANGRAM = "Чуєш їх, доцю, га? Кумедна ж ти, прощайся без ґольфів! ЇЖАК ҐАВА Є м’ята"
UKRAINIAN = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯабвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
LOOK_ALIKES = dict(zip("АВЕКМНОРСТХІаеіорсху", "ABEKMHOPCTXIaeiopcxy"))


@pytest.fixture(params=[OcarinaRules, MajoraRules], ids=["oot64", "mm64"])
def rules(request):
    return request.param(None)


def test_every_ukrainian_letter_has_its_own_slot(rules):
    tmap = rules.translation_map()
    assert set(UKRAINIAN) <= set(tmap)
    assert not set("ЁЪЫЭёъыэ") & set(tmap)              # Russian-only letters take no slot
    slots = rules.letter_slots()
    shared = [code for code in set(slots.values()) if list(slots.values()).count(code) > 1]
    assert not shared


def test_look_alike_letters_keep_the_latin_glyph_and_no_latin_letter_is_redrawn(rules):
    tmap = rules.translation_map()
    for letter, latin in LOOK_ALIKES.items():
        assert tmap[letter] == latin
    others = {letter: char for letter, char in tmap.items() if letter not in LOOK_ALIKES}
    assert not [char for char in others.values() if char.isascii() and char.isalnum()]


def test_a_ukrainian_pangram_survives_encode_and_decode(rules):
    body = rules.text_format.encode(PANGRAM, rules.letter_slots())
    decoded = rules.decode_text(body)
    # Look-alikes and the apostrophe come back as the Latin characters they share with the English text
    expected = "".join(LOOK_ALIKES.get(ch, ch) for ch in PANGRAM).replace("’", "'")
    assert decoded == expected
    assert all(byte < 0x100 for byte in body)


def test_the_width_check_measures_a_letter_by_its_slot(rules):
    slot = rules.letter_slots()["Щ"]
    assert rules.calculate_string_width_override("Щ", {}) == rules._char_width(slot)


def test_the_projects_map_wins_over_the_plugins(tmp_path):
    (tmp_path / "translation_map.json").write_text(json.dumps({"Щ": "#"}), encoding="utf-8")
    rules = OcarinaRules(SimpleNamespace(project_manager=SimpleNamespace(project_dir=str(tmp_path))))
    assert rules.translation_map() == {"Щ": "#"}
    assert rules.text_format.encode("Щ", rules.letter_slots()) == b"#"


def test_the_shipped_maps_are_the_plugins_own_files():
    for plugin in ("zelda_oot64", "zelda_mm64", "zelda_tww", "zelda_hwde"):
        path = Path(__file__).resolve().parents[2] / "plugins" / plugin / "translation_map.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert set(UKRAINIAN) <= set(data), plugin


ROMS = {"oot64": Path(r"E:\Emulators\RomHacking\Zelda\Ocarina of Time\N64\rom\Legend of Zelda, The - Ocarina of Time (USA).z64"),
        "mm64": Path(r"E:\Emulators\RomHacking\Zelda\Majoras Mask\N64\rom\Legend of Zelda, The - Majora's Mask (USA).z64")}


def _font_codes(fmt, body):
    """The font characters of a message body (control codes and their arguments skipped)."""
    codes, i = [], 0
    while i < len(body):
        control = fmt.controls.get(body[i])
        if body[i] != fmt.newline and control is None:
            codes.append(body[i])
        i += 1 + (control.args if control else 0)
    return codes


def test_no_english_message_or_credit_uses_a_cell_a_ukrainian_letter_takes(rules, request):
    """The maps are confirmed against the US ROMs: Latin stays fully usable (see translation_map.md)."""
    from plugins.common import z64_text
    from plugins.common.n64_rom import N64Rom
    from plugins.zelda_oot64.msg_codec import CONTROLS as NES_CONTROLS

    path = ROMS[request.node.callspec.id]
    if not path.is_file():
        pytest.skip(f"{path} is not on this machine")
    rom = N64Rom(path.read_bytes())
    layout = next(iter(rules.layouts.values()))
    code = rom.read_file(layout.code_file)
    fmt = rules.text_format
    taken = {slot for letter, slot in rules.letter_slots().items()
             if not (rules.translation_map()[letter].isascii()
                     and (rules.translation_map()[letter].isalnum() or rules.translation_map()[letter] == "'"))}
    messages = z64_text.read_messages(fmt, code, layout.table_offset, rom.read_file(layout.text_file))
    # the credits: the next table in `code`, the next file; OoT's control codes in both games
    credits_fmt = z64_text.TextFormat(controls=NES_CONTROLS, newline=1, end=2, charmap=fmt.charmap)
    credits_table = layout.table_offset + 8 * len(z64_text.read_table(code, layout.table_offset))
    credits = z64_text.read_messages(credits_fmt, code, credits_table, rom.read_file(layout.text_file + 1))
    assert len(messages) > 2000 and len(credits) > 40
    used = {c for m in messages for c in _font_codes(fmt, m.body)}
    used |= {c for m in credits for c in _font_codes(credits_fmt, m.body)}
    assert len(taken) >= 45 and not taken & used
