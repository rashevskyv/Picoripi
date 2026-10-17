"""A save refuses a file that changed on disk outside Picoripi, and writes the Ukrainian text of an unchanged file."""
import json
from types import SimpleNamespace

import pytest

from plugins.system_3ds.rules import GameRules

ORIGINAL = json.dumps({"label_one": {"en": "Hello", "ru": "Привет", "ua": "Привіт"}}, ensure_ascii=False).encode()
EDITED_OUTSIDE = json.dumps({"label_one": {"en": "Hello", "ru": "Привет", "ua": "Вітаю"}}, ensure_ascii=False).encode()


def _context(*versions, name="strings/home/x.json"):
    return SimpleNamespace(relative_path=name, existing_versions=lambda: iter(versions))


def _loaded_rules():
    rules = GameRules()
    rules.load_data_from_json_obj(ORIGINAL)
    return rules


def test_an_unchanged_file_saves_the_edited_text():
    rules = _loaded_rules()
    rules.prepare_save_context(_context(ORIGINAL))

    saved = rules.save_data_to_json_obj([["Бувай"]], {})

    assert json.loads(saved)["label_one"]["ua"] == "Бувай"


def test_a_file_changed_outside_is_refused_and_named():
    rules = _loaded_rules()

    with pytest.raises(ValueError, match="strings/home/x.json changed outside Picoripi"):
        rules.prepare_save_context(_context(EDITED_OUTSIDE))


def test_the_text_picoripi_wrote_is_known_to_the_next_save():
    rules = _loaded_rules()
    rules.prepare_save_context(_context(ORIGINAL))
    saved = rules.save_data_to_json_obj([["Бувай"]], {})

    rules.prepare_save_context(_context(saved))

    assert rules._save_text == saved.decode("utf-8")


def test_the_record_survives_a_saved_session():
    rules = _loaded_rules()
    state = rules.export_runtime_state()
    restored = GameRules()
    restored.restore_runtime_state(state)

    with pytest.raises(ValueError):
        restored.prepare_save_context(_context(EDITED_OUTSIDE))
    restored.prepare_save_context(_context(ORIGINAL))


def test_a_session_without_a_record_adopts_the_file_as_it_is():
    rules = GameRules()
    rules.restore_runtime_state({"blocks": []})

    rules.prepare_save_context(_context(EDITED_OUTSIDE))

    assert rules._save_text is not None
