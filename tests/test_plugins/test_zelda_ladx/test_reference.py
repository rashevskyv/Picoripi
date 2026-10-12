"""Reference columns: a JSON file maps DialogNNN to the reference text and lands on the matching dialogue (real ROM)."""
import json

from .test_rules import _rules_and_data


def test_reference_text_lands_on_the_named_dialogue(tmp_path):
    _raw, rules, _blocks, _names = _rules_and_data()
    (tmp_path / "ua_gb.json").write_text(json.dumps({"Dialog001": "Яке полегшення!"}, ensure_ascii=False),
                                         encoding="utf-8")
    result = rules.load_multi_reference(str(tmp_path))
    assert result["Ukrainian GB v0.1 (decoded)"] == {(0, 1): "Яке полегшення!"}


def test_missing_reference_files_give_no_columns(tmp_path):
    _raw, rules, _blocks, _names = _rules_and_data()
    assert rules.load_multi_reference(str(tmp_path)) == {}
    assert rules.supports_reference_patch() is True
