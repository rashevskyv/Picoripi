"""Reference columns from the seed: the key of each row finds its project block, the text is shown, nothing is saved."""
import json

from plugins.zelda_ladx_hd.rules import GameRules, REFERENCE_FILE


SEED = {
    "eng.lng": {
        "menu_start": {"ua_gb": "Почати", "swuk": None, "score": 0.5},
        "menu_back": {"ua_gb": None, "swuk": None, "score": None},
    },
    "dialog_eng.lng": {
        "dialog_a": {"ua_gb": "Текст А", "swuk": "Рядок А", "score": 1.0},
        "not_in_project": {"ua_gb": "Зайве", "swuk": None, "score": 0.9},
    },
}

PROJECT_BLOCKS = {"0": "dialog_a", "1": "menu_start", "2": "menu_back"}


def _seed(tmp_path):
    path = tmp_path / REFERENCE_FILE
    path.write_text(json.dumps(SEED, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_reference_rows_map_to_project_blocks_by_key(tmp_path):
    columns = GameRules().load_multi_reference(str(_seed(tmp_path)), block_names=PROJECT_BLOCKS)
    assert columns["UA GB (closest GBC dialogue)"] == {(0, 0): "Текст А  [1.00]", (1, 0): "Почати  [0.50]"}
    assert columns["SWUK (same GBC dialogue)"] == {(0, 0): "Рядок А  [1.00]"}


def test_seed_file_path_is_accepted(tmp_path):
    folder = _seed(tmp_path)
    by_file = GameRules().load_multi_reference(str(folder / REFERENCE_FILE), block_names=PROJECT_BLOCKS)
    assert by_file == GameRules().load_multi_reference(str(folder), block_names=PROJECT_BLOCKS)


def test_no_seed_or_no_blocks_gives_no_columns(tmp_path):
    assert GameRules().load_multi_reference(str(tmp_path), block_names=PROJECT_BLOCKS) == {}
    assert GameRules().load_multi_reference(str(_seed(tmp_path)), block_names={}) == {}


def test_real_seed_maps_a_key_to_its_project_block():
    """The editor's block order is the project's: the dialogue file first, then eng.lng (block 780 is
    main_menu_new_game, the opener's index)."""
    import os
    from pathlib import Path

    root = os.environ.get("PICORIPI_ROMHACKING", "").strip()
    seed = Path(root) / "Zelda" / "Links Awakening" / "HD" / "reference" / REFERENCE_FILE if root else None
    if seed is None or not seed.is_file():
        import pytest
        pytest.skip("PICORIPI_ROMHACKING is not set or the HD reference seed is missing")
    from plugins.zelda_ladx_hd import lng
    languages = Path(root) / "_new" / "Links Awakening DX HD" / "Data" / "Languages"
    order = []
    for name in ("dialog_eng.lng", "eng.lng"):
        order += [e.key for e in lng.parse((languages / name).read_bytes()).entries()]
    names = {str(i): key for i, key in enumerate(order)}
    columns = GameRules().load_multi_reference(str(seed), block_names=names)
    ua = columns["UA GB (closest GBC dialogue)"]
    assert names["780"] == "main_menu_new_game"
    assert ua[(780, 0)].startswith(" МЕНТАХ")
    assert len(ua) > 400


def test_reference_does_not_change_the_saved_file(tmp_path):
    rules = GameRules()
    text = "menu_start Start Game\r\nmenu_back Back\r\n"
    data, names = rules.load_data_from_json_obj(text)
    rules.load_multi_reference(str(_seed(tmp_path)), block_names={"0": "menu_start", "1": "menu_back"})
    assert rules.save_data_to_json_obj(data, names) == text
