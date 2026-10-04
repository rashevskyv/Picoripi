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
