"""The lines the wizard and the Project Manager row show for a plugin's declared images."""
from ui.project_manager.image_labels import summary_lines


def test_an_id_shows_its_kind_id_region_and_note():
    lines = summary_lines([{"kind": "disc", "id": "GZLE01", "region": "USA", "note": "GameCube"}])
    assert lines == ["Disc ID GZLE01, USA (GameCube)"]


def test_the_rom_hashes_share_one_line_and_an_unstated_region_is_named():
    entries = [{"kind": "hash", "id": "a" * 40, "region": "USA", "note": "Red"},
               {"kind": "hash", "id": "b" * 40, "region": "USA", "note": "Blue"},
               {"kind": "code", "id": "ADAE", "region": "Not stated", "note": ""}]
    assert summary_lines(entries) == ["Product code ADAE, Region not stated", "2 ROM versions: Red, Blue"]


def test_open_and_unchecked_declarations_have_no_id():
    assert summary_lines([{"kind": "any", "id": "", "region": "", "note": ""}]) == ["Any file"]
    assert summary_lines([{"kind": "unchecked", "id": "", "region": "EUR", "note": ""}]) == ["Not checked by ID: EUR"]
