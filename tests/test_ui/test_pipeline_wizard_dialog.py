"""The pipeline wizard: what it reads from a project, and what it launches."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.glossary_manager import STATUS_CONFIRMED
from core.pipeline_status import DONE, NOT_STARTED, PARTIAL
from core.speaker_alias_merge import ALIAS_FILENAME
from PyQt6.QtWidgets import QWidget

from ui.pipeline_wizard_dialog import (
    PipelineWizardDialog,
    Step,
    capabilities_of,
    steps_for,
)


def _mw(tmp_path, *, entries=(), aliases=None, data=None, edited=None,
        capabilities=("speaker_attribution",), codes=None):
    mw = MagicMock()
    mw.project_manager.project_dir = str(tmp_path)
    mw.current_game_rules.get_capabilities.return_value = set(capabilities)
    # The plugin groups rows by voice; two codes is enough to have a fraction.
    codes = {(0, 0): "Voice 8", (0, 1): "Voice 9"} if codes is None else codes
    mw.current_game_rules.get_speaker_for_string = lambda b, s: codes.get((b, s))
    composer = mw.translation_handler.prompt_composer
    script = tmp_path / "script.txt"
    script.write_text("RENADO\nWelcome to Kakariko.\n", encoding="utf-8")
    composer._find_script_path.return_value = str(script)
    composer._get_mempalace_client.return_value = None
    mw.translation_handler.glossary_handler.glossary_manager.get_entries.return_value = list(entries)
    mw.data_store.data = data if data is not None else [["line one", "line two"]]
    mw.data_store.edited_file_data = edited if edited is not None else []
    mw.data_store.edited_data = {}
    if aliases:
        (tmp_path / ALIAS_FILENAME).write_text(json.dumps(aliases), encoding="utf-8")
    return mw


def _write_markup_project(tmp_path):
    """The file Markup Studio leaves beside the script."""
    from core.script_markup.hierarchy_ai_jobs import (
        HIERARCHY_FORMAT_VERSION,
        HIERARCHY_PROJECT_FORMAT,
    )
    from core.script_markup.hierarchy_markup import default_type_definitions

    payload = {
        "format": HIERARCHY_PROJECT_FORMAT,
        "version": HIERARCHY_FORMAT_VERSION,
        "raw_text": "RENADO\nWelcome to Kakariko.",
        "type_definitions": [
            {"type_id": d.type_id, "label": d.label,
             "description": d.description, "color": d.color}
            for d in default_type_definitions().values()
        ],
        "hierarchy_marks": [
            {"start_line": 0, "end_line": 0, "depth": 0,
             "type_id": "speaker", "approved": True, "origin": "manual"},
            {"start_line": 1, "end_line": 1, "depth": 0,
             "type_id": "text", "approved": True, "origin": "manual"},
        ],
    }
    path = tmp_path / "script_markup_project.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _entry(**kwargs):
    return SimpleNamespace(
        notes=kwargs.get("notes", ""),
        translation=kwargs.get("translation", ""),
        status=kwargs.get("status", ""),
    )


def _shown(dialog):
    """Every step key in the tree, parents and children alike."""
    return [step.key for step in dialog._steps if dialog._item_for(step.key) is not None]


@pytest.mark.usefixtures("qapp")
class TestReadingTheProject:
    def test_a_bare_project_shows_every_step_unstarted(self, tmp_path):
        dialog = PipelineWizardDialog(_mw(tmp_path))

        assert all(s.state == NOT_STARTED for s in dialog._states.values())
        assert "0 / 5 steps complete" in dialog.headline.text()
        dialog.deleteLater()

    def test_partial_work_is_shown_as_a_count_not_a_bare_light(self, tmp_path):
        """The whole reason the wizard exists: say how far, not just 'not done'."""
        mw = _mw(tmp_path, entries=[
            _entry(notes="a note", translation="переклад", status=STATUS_CONFIRMED),
            _entry(notes="a note"),
            _entry(),
        ])
        dialog = PipelineWizardDialog(mw)

        assert dialog._states["describe"].state == PARTIAL
        assert dialog._states["describe"].detail == "2 / 3 terms described"
        assert dialog._states["seed"].state == DONE
        dialog.deleteLater()

    def test_naming_some_speakers_is_not_naming_them_all(self, tmp_path):
        """One of two codes named is half the step, not a finished one."""
        dialog = PipelineWizardDialog(_mw(tmp_path, aliases={"Voice 8": "ZANT"}))

        assert dialog._states["speakers"].state == PARTIAL
        assert dialog._states["speakers"].detail == "1 / 2 speaker codes named"
        dialog.deleteLater()

    def test_the_code_inventory_is_read_once_per_project(self, tmp_path):
        """It walks every row, and naming a code does not change what exists."""
        mw = _mw(tmp_path)
        calls = []
        original = mw.current_game_rules.get_speaker_for_string
        mw.current_game_rules.get_speaker_for_string = lambda b, s: (
            calls.append((b, s)) or original(b, s)
        )
        dialog = PipelineWizardDialog(mw)
        seen = len(calls)

        dialog.refresh()

        assert seen > 0 and len(calls) == seen
        dialog.deleteLater()

    def test_text_progress_comes_from_the_edited_rows(self, tmp_path):
        mw = _mw(tmp_path, data=[["Hello", "Goodbye"]], edited=[["Вітаю", "Goodbye"]])
        dialog = PipelineWizardDialog(mw)

        assert dialog._states["text"].detail == "1 / 2 rows translated"
        dialog.deleteLater()

    def test_a_broken_probe_still_opens_the_window(self, tmp_path):
        """A wizard that crashes on a half-set-up project is worse than useless."""
        mw = _mw(tmp_path)
        mw.translation_handler.glossary_handler.glossary_manager.get_entries.side_effect = RuntimeError

        dialog = PipelineWizardDialog(mw)

        assert _shown(dialog) == [s.key for s in dialog._steps]
        dialog.deleteLater()


class TestTheWizardIsTheEnginesNotOneGames:
    """Steps needing the game's own data appear only where a plugin supplies it."""

    def test_a_plugin_that_declares_nothing_still_gets_the_whole_text_path(self):
        keys = [step.key for step in steps_for(set())]

        assert keys == ["markup", "context", "glossary", "text"]

    def test_speaker_merging_appears_only_where_the_game_attributes_speakers(self):
        assert "speakers" not in [s.key for s in steps_for({"glossary_seed"})]
        assert "speakers" in [s.key for s in steps_for({"speaker_attribution"})]

    def test_structural_seeding_is_part_of_the_one_glossary_route(self):
        assert "glossary" in [s.key for s in steps_for({"glossary_seed"})]
        assert "structural_seed" not in [s.key for s in steps_for({"glossary_seed"})]

    def test_an_unknown_capability_adds_nothing(self):
        assert steps_for({"time_travel"}) == steps_for(set())

    def test_a_plugin_with_no_capabilities_hook_is_not_an_error(self):
        assert capabilities_of(object()) == set()

    def test_a_hook_that_raises_is_read_as_no_capabilities(self):
        class Rules:
            def get_capabilities(self):
                raise RuntimeError("boom")

        assert capabilities_of(SimpleNamespace(current_game_rules=Rules())) == set()


@pytest.mark.usefixtures("qapp")
class TestNavigation:
    def test_a_bare_plugin_sees_a_shorter_pipeline(self, tmp_path):
        dialog = PipelineWizardDialog(_mw(tmp_path, capabilities=()))

        assert "speakers" not in [step.key for step in dialog._steps]
        assert len(_shown(dialog)) == 4
        dialog.deleteLater()

    def test_a_game_with_no_script_says_so_rather_than_nagging(self, tmp_path):
        """'No script' is nothing to do; 'script not marked up' is work waiting."""
        mw = _mw(tmp_path)
        mw.translation_handler.prompt_composer._find_script_path.return_value = None
        dialog = PipelineWizardDialog(mw)

        assert "no script found" in dialog._states["markup"].detail
        dialog.deleteLater()

    def test_it_opens_on_the_first_unfinished_step(self, tmp_path):
        mw = _mw(tmp_path, aliases={"Voice 8": "ZANT"})
        dialog = PipelineWizardDialog(mw)

        # Markup is step one and nothing has been marked up.
        assert dialog._current_key() == "markup"
        dialog.deleteLater()

    def test_every_step_lists_its_state_beside_its_name(self, tmp_path):
        dialog = PipelineWizardDialog(_mw(tmp_path))

        text = dialog._item_for("markup").text(0)
        assert "Mark up the script" in text
        assert "not marked up" in text
        dialog.deleteLater()

    def test_selecting_a_step_explains_why_it_exists(self, tmp_path):
        dialog = PipelineWizardDialog(_mw(tmp_path))

        dialog.select_step("speakers")

        assert "Voice 8" in dialog.why.text()
        assert dialog.run_button.isVisible() or not dialog.isVisible()
        dialog.deleteLater()


@pytest.mark.usefixtures("qapp")
class TestItDoesNotBlockTheToolsItOpens:
    def test_the_wizard_is_not_modal(self, tmp_path):
        """A modal wizard locks the user out of the window it just launched."""
        dialog = PipelineWizardDialog(_mw(tmp_path))

        assert dialog.isModal() is False
        dialog.deleteLater()

    def test_the_wizard_is_its_own_alt_tab_window(self, tmp_path):
        from PyQt6.QtCore import Qt

        dialog = PipelineWizardDialog(_mw(tmp_path))

        assert dialog.parent() is None
        assert dialog.windowFlags() & Qt.WindowType.Window
        assert not dialog.testAttribute(Qt.WidgetAttribute.WA_QuitOnClose)
        dialog.deleteLater()

    def test_opening_it_again_reuses_the_same_window(self, tmp_path):
        from ui.main_window.main_window_actions import MainWindowActions

        mw = _mw(tmp_path)
        mw.pipeline_wizard_dialog = None
        actions = MainWindowActions.__new__(MainWindowActions)
        actions.mw = mw

        actions.open_pipeline_wizard()
        first = mw.pipeline_wizard_dialog
        actions.open_pipeline_wizard()

        assert mw.pipeline_wizard_dialog is first
        first.deleteLater()

    def test_coming_back_to_the_window_re_reads_the_project(self, tmp_path):
        """The tool ran beside the wizard, so its result only shows on return."""
        mw = _mw(tmp_path)
        dialog = PipelineWizardDialog(mw)
        assert dialog._states["speakers"].state == NOT_STARTED

        (tmp_path / ALIAS_FILENAME).write_text(
            json.dumps({"Voice 8": "ZANT", "Voice 9": "GANON"}), encoding="utf-8"
        )
        dialog.refresh()

        assert dialog._states["speakers"].state == DONE
        dialog.deleteLater()

    def test_an_activation_event_is_survivable(self, tmp_path):
        from PyQt6.QtCore import QEvent

        dialog = PipelineWizardDialog(_mw(tmp_path))

        dialog.changeEvent(QEvent(QEvent.Type.ActivationChange))

        assert _shown(dialog) == [s.key for s in dialog._steps]
        dialog.deleteLater()


@pytest.mark.usefixtures("qapp")
class TestEmbeddedTools:
    """A step that is a workflow of its own is shown here, not in a second window."""

    def test_the_context_step_hosts_a_widget_instead_of_a_button(self, tmp_path):
        dialog = PipelineWizardDialog(_mw(tmp_path))
        step = dialog._step_for("context")

        assert step.embed is not None
        assert step.run is None
        dialog.deleteLater()

    def test_the_markup_step_hosts_the_studio_instead_of_a_button(self, tmp_path):
        dialog = PipelineWizardDialog(_mw(tmp_path))
        step = dialog._step_for("markup")

        assert step.embed is not None
        assert step.run is None
        dialog.select_step("markup")
        assert dialog.stack.currentWidget() is not dialog._explain_page
        dialog.deleteLater()

    def test_an_explaining_step_stays_on_the_explanation_page(self, tmp_path):
        dialog = PipelineWizardDialog(_mw(tmp_path))

        dialog.select_step("text")

        assert dialog.stack.currentWidget() is dialog._explain_page
        dialog.deleteLater()

    def test_an_embed_that_cannot_start_falls_back_to_the_explanation(self, tmp_path):
        """Better a paragraph than an empty pane on a half-set-up project."""
        dialog = PipelineWizardDialog(_mw(tmp_path))
        broken = Step("x", "X", "why", embed=lambda mw, parent: (_ for _ in ()).throw(RuntimeError))

        assert dialog._page_for(broken) is dialog._explain_page
        dialog.deleteLater()

    def test_an_embedded_widget_is_built_once_and_reused(self, tmp_path):
        dialog = PipelineWizardDialog(_mw(tmp_path))
        built = []
        step = Step("x", "X", "why", embed=lambda mw, parent: built.append(1) or QWidget())
        first = dialog._page_for(step)

        assert dialog._page_for(step) is first
        assert len(built) == 1
        dialog.deleteLater()

    def test_the_markup_project_is_handed_over_not_asked_for(self, tmp_path):
        """Step one located the file; making the user browse for it is busywork."""
        _write_markup_project(tmp_path)
        mw = _mw(tmp_path)
        mw.script_markup_studio_project_path = ""
        dialog = PipelineWizardDialog(mw)

        dialog._page_for(dialog._step_for("context"))

        assert mw.script_markup_studio_project_path == str(
            tmp_path / "script_markup_project.json"
        )
        dialog.deleteLater()

    def test_a_project_the_user_already_chose_is_left_alone(self, tmp_path):
        _write_markup_project(tmp_path)
        chosen = tmp_path / "chosen.json"
        chosen.write_text("{}", encoding="utf-8")
        mw = _mw(tmp_path)
        mw.script_markup_studio_project_path = str(chosen)
        dialog = PipelineWizardDialog(mw)

        dialog._page_for(dialog._step_for("context"))

        assert mw.script_markup_studio_project_path == str(chosen)
        dialog.deleteLater()

    def test_direct_context_builder_does_not_route_through_pipeline(self, tmp_path):
        from ui.main_window.main_window_actions import MainWindowActions

        mw = _mw(tmp_path)
        mw.pipeline_wizard_dialog = None
        actions = MainWindowActions.__new__(MainWindowActions)
        actions.mw = mw
        actions.mempalace_actions = MagicMock()

        actions.open_mempalace_builder()

        actions.mempalace_actions.open_mempalace_builder.assert_called_once_with()
        assert mw.pipeline_wizard_dialog is None


@pytest.mark.usefixtures("qapp")
class TestLaunching:
    def test_a_step_triggers_the_action_the_menu_used_to(self, tmp_path):
        mw = _mw(tmp_path)
        dialog = PipelineWizardDialog(mw)

        dialog.select_step("speakers")
        dialog._run_current()

        mw.merge_speakers_action.trigger.assert_called_once()
        dialog.deleteLater()

    def test_the_glossary_step_hosts_the_automatic_route(self, tmp_path):
        dialog = PipelineWizardDialog(_mw(tmp_path))

        step = dialog._step_for("glossary")

        assert step.embed is not None
        assert step.run is None
        dialog.deleteLater()

    def test_the_last_step_has_no_button_to_press(self, tmp_path):
        """Translating is done in the editor, not from a wizard button."""
        dialog = PipelineWizardDialog(_mw(tmp_path))

        dialog.select_step("text")

        assert dialog._step_for("text").run is None
        dialog._run_current()  # must not raise
        dialog.deleteLater()

    def test_a_tool_that_blows_up_does_not_take_the_wizard_with_it(self, tmp_path):
        mw = _mw(tmp_path)
        mw.merge_speakers_action.trigger.side_effect = RuntimeError("boom")
        dialog = PipelineWizardDialog(mw)

        dialog.select_step("speakers")
        dialog._run_current()

        assert _shown(dialog) == [s.key for s in dialog._steps]
        dialog.deleteLater()


@pytest.mark.usefixtures("qapp")
class TestTheGlossaryStepsAreOneStep:
    """The model's glossary passes are one uninterrupted user-facing route."""

    def test_naming_speakers_is_nested_under_marking_up_the_script(self, tmp_path):
        dialog = PipelineWizardDialog(_mw(tmp_path))

        assert dialog._item_for("speakers").parent() is dialog._item_for("markup")
        dialog.deleteLater()

    def test_the_stages_around_the_glossary_stay_at_the_top(self, tmp_path):
        dialog = PipelineWizardDialog(_mw(tmp_path))

        for key in ("markup", "context", "glossary", "text"):
            assert dialog._item_for(key).parent() is None, key
        dialog.deleteLater()

    def test_a_child_step_is_still_selectable_and_runnable(self, tmp_path):
        mw = _mw(tmp_path)
        dialog = PipelineWizardDialog(mw)

        dialog.select_step("speakers")
        dialog._run_current()

        assert dialog._current_key() == "speakers"
        mw.merge_speakers_action.trigger.assert_called_once()
        dialog.deleteLater()

    def test_collecting_terms_hosts_the_build_form_itself(self, tmp_path):
        """A step whose only content is a button to open the step is a door."""
        dialog = PipelineWizardDialog(_mw(tmp_path))

        assert dialog._step_for("glossary").embed is not None
        assert dialog._step_for("glossary").run is None
        assert dialog._step_for("describe") is None
        dialog.deleteLater()
