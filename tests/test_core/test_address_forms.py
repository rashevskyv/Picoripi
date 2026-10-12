"""Forms of address: the table, its resolution order, the dialog and the prompts."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QComboBox

from core.address_forms import DEFAULT_RULES, known_names, load_table, resolve, resolve_for, save_table
from core.project_models import Project
from handlers.translation.ai_prompt_composer import AIPromptComposer
from ui.address_forms_dialog import AddressFormsDialog


def _table():
    return {
        "traits": {"Link": ["child", "male"], "Zelda": ["royalty", "child"], "Rusl": ["adult"], "Ilia": ["child"]},
        "rules": list(DEFAULT_RULES),
        "pairs": [{"speaker": "Link", "addressee": "Zelda", "form": "informal"}],
    }


class TestResolve:
    def test_a_pair_beats_the_rules_and_names_match_loosely(self):
        assert resolve(_table(), " link ", "ZELDA") == "informal"
        assert resolve(_table(), "Zelda", "Link") == "informal"   # royalty child -> child: child -> child rule

    def test_rules_apply_in_order_with_the_wildcard(self):
        assert resolve(_table(), "Link", "Rusl") == "formal"       # child -> adult
        assert resolve(_table(), "Rusl", "Link") == "informal"     # adult -> child
        assert resolve(_table(), "Rusl", "Zelda") == "formal"      # * -> royalty
        assert resolve(_table(), "Ilia", "Link") == "informal"     # child -> child

    def test_no_answer_when_the_table_does_not_know(self):
        assert resolve(_table(), "Link", "Midna") is None
        assert resolve(_table(), "", "Link") is None
        assert resolve({"traits": {}, "rules": [], "pairs": []}, "Link", "Zelda") is None


class TestStore:
    def test_round_trip_through_the_project_metadata(self):
        project = Project(name="TP")
        assert load_table(project) == {"traits": {}, "rules": DEFAULT_RULES, "pairs": []}

        save_table(project, _table())
        reloaded = Project.from_dict(json.loads(json.dumps(project.to_dict())))

        assert load_table(reloaded) == _table()
        assert resolve_for(SimpleNamespace(project_manager=SimpleNamespace(project=reloaded)), "Link", "Rusl") == "formal"

    def test_an_untouched_table_leaves_no_key_and_junk_rows_are_dropped(self):
        project = Project(name="TP")
        save_table(project, {"traits": {"Link": []}, "rules": list(DEFAULT_RULES), "pairs": [{"speaker": "A", "form": "formal"}]})
        assert "address_forms" not in project.metadata

        save_table(project, {"traits": {}, "rules": [{"from": "*", "to": "*", "form": "sideways"}], "pairs": []})
        assert project.metadata["address_forms"] == {"traits": {}, "rules": [], "pairs": []}

    def test_known_names_merge_the_table_and_the_speaker_pool(self):
        assert known_names(_table(), ["Midna", "link"]) == ["Ilia", "Link", "Midna", "Rusl", "Zelda"]


class TestDialog:
    def test_the_dialog_lists_speakers_and_saves_what_was_typed(self, qtbot, monkeypatch):
        project = Project(name="TP")
        manager = SimpleNamespace(project=project, save=MagicMock(return_value=True))
        mw = SimpleNamespace(project_manager=manager)
        monkeypatch.setattr("core.speaker_resolution.build_speaker_pool", lambda _mw: {(0, 0): "Link", (0, 1): "Rusl"})
        dialog = AddressFormsDialog(mw, parent=None)
        qtbot.addWidget(dialog)

        assert [dialog.characters.value(r, 0) for r in range(2)] == ["Link", "Rusl"]
        assert dialog.rule_table.table.rowCount() == len(DEFAULT_RULES)
        dialog.characters.table.item(0, 1).setText("child, male")
        dialog.characters.table.item(1, 1).setText("adult")
        row = dialog.pairs.add_row(["Link", "Rusl", "informal"])
        assert isinstance(dialog.pairs.table.cellWidget(row, 2), QComboBox)
        dialog.accept()

        manager.save.assert_called_once()
        table = load_table(project)
        assert table["traits"] == {"Link": ["child", "male"], "Rusl": ["adult"]}
        assert table["pairs"] == [{"speaker": "Link", "addressee": "Rusl", "form": "informal"}]
        assert resolve(table, "Link", "Rusl") == "informal"


class TestPrompts:
    def _composer(self, project):
        mw = MagicMock()
        mw.data_store = mw
        mw.data_store.data = [["Hi there"]]
        mw.project_manager.project = project
        rules = MagicMock()
        rules.get_addressee_for_string.return_value = "Rusl"
        mw.current_game_rules = rules
        composer = AIPromptComposer(SimpleNamespace(
            mw=mw, data_processor=None, ui_updater=None, _glossary_manager=None, _series_glossary_managers=[]
        ))
        composer._get_mempalace_client = MagicMock(return_value=None)
        composer._find_speaker_in_script = MagicMock(return_value=None)
        composer._fetch_story_context = MagicMock(return_value=None)
        composer._get_structured_story_context = MagicMock(return_value={})
        composer._resolve_prompt_speaker = MagicMock(return_value=("Link", set()))
        composer._translate_speaker = lambda name: name
        return composer

    def test_batch_items_and_single_requests_carry_the_form(self):
        project = Project(name="TP")
        save_table(project, _table())
        composer = self._composer(project)
        items = [{"id": 0, "text": "Hi there"}]

        _, batch_user, _ = composer.compose_batch_request("sys", items, items, block_idx=0, mode_description="t")
        _, single_user = composer.compose_messages("sys", "Hi there", block_idx=0, string_idx=0, expected_lines=1, mode_description="t")

        payload = json.loads(batch_user[batch_user.index("{"):batch_user.rindex("}") + 1])
        item = payload["strings_to_translate"][0]
        assert item["addressee"] == "Rusl" and item["address_form"] == "formal"
        assert "Addressee: Rusl" in single_user and "Address form: formal" in single_user

    def test_no_table_no_field(self):
        composer = self._composer(Project(name="TP"))
        items = [{"id": 0, "text": "Hi there"}]
        _, batch_user, _ = composer.compose_batch_request("sys", items, items, block_idx=0, mode_description="t")
        assert "address_form" not in batch_user
