"""The declaration format: what problems() refuses, and how an id is found in source text."""
from core.project_library.supported_images import appears_in, declared_in, ids_of, normalise, problems


def test_a_clean_declaration_has_no_problems():
    entries = [{"kind": "disc", "id": "GZLE01", "region": "USA"}, {"kind": "any"}, {"kind": "unchecked", "region": "EUR"}]
    assert problems(entries) == []


def test_each_wrong_declaration_is_named_once():
    assert problems([]) == ["supported_images must be a non-empty list"]
    assert "needs an id" in problems([{"kind": "title", "id": "", "region": "All regions"}])[0]
    assert "takes no id" in problems([{"kind": "any", "id": "x"}])[0]
    assert "region is missing" in problems([{"kind": "disc", "id": "GZLE01"}])[0]
    assert "kind 'cube'" in problems([{"kind": "cube", "id": "x", "region": "USA"}])[0]
    assert "keys the host does not read" in problems([{"kind": "any", "colour": "red"}])[0]


def test_the_ids_of_the_chosen_kinds_come_in_order():
    entries = normalise([{"kind": "disc", "id": "A", "region": "USA"}, {"kind": "unchecked"},
                         {"kind": "serial", "id": "B", "region": "USA"}])
    assert ids_of(entries) == ("A", "B")
    assert ids_of(entries, ("serial",)) == ("B",)


def test_an_id_is_found_whatever_its_punctuation():
    assert appears_in("SLUS-00067", 'name = "SLUS_000.67"')
    assert not appears_in("SLUS-00068", 'name = "SLUS_000.67"')


def test_declared_in_reads_the_folder_and_is_empty_when_missing(tmp_path):
    (tmp_path / "config.json").write_text('{"supported_images": [{"kind": "any", "note": "x"}]}', encoding="utf-8")
    assert declared_in(tmp_path) == [{"kind": "any", "id": "", "region": "", "note": "x"}]
    assert declared_in(tmp_path / "missing") == []
