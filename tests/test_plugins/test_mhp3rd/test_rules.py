"""The Monster Hunter Portable 3rd HD plugin: the rules class and the dict form of a translation file (synthetic)."""
from plugins.mhp3rd.lang_file import LangDocument, from_json_obj, to_json_obj
from plugins.testing import check_loads, check_round_trip, check_validator

SAMPLE = {
    "16": {"2:20": "Cancel", "2:21": "Yes", "2:60": "~B03Switch Equipment"},
    "4289": {"0:0": "Hello\nhunter.", "1:0": "Second dialogue"},
}


def test_the_plugin_loads():
    check_loads("mhp3rd")


def test_a_sample_survives_load_and_save():
    check_round_trip("mhp3rd", SAMPLE)


def test_the_plugin_validates():
    check_validator("mhp3rd")


def test_saved_data_keeps_block_names_and_keys():
    from plugins.mhp3rd.rules import GameRules

    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(SAMPLE)
    blocks[0][1] = "Да"
    saved = rules.save_data_to_json_obj(blocks, names)
    assert list(saved) == ["16", "4289"]
    assert saved["16"]["2:21"] == "Да"
    assert list(saved["16"]) == ["2:20", "2:21", "2:60"]


def test_lang_text_and_dict_form_agree():
    text = (
        "language = uk\n"
        "name = Українська\n"
        "[16]\n"
        "2:20 = Скасувати\n"
        "2:21 =  Так\n"
        "[4289]\n"
        "0:0 = Рядок\\nдруга лінія\n"
    )
    obj = to_json_obj(LangDocument.parse(text))
    assert obj == {"16": {"2:20": "Скасувати", "2:21": " Так"}, "4289": {"0:0": "Рядок\nдруга лінія"}}
    again = LangDocument.parse(from_json_obj(obj, "uk", "Українська"))
    assert to_json_obj(again) == obj
