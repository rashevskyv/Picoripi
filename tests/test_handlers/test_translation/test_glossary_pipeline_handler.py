"""Tests for GlossaryPipelineHandler wiring (dialog -> provider -> worker)."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.glossary_manager import GlossaryManager
from handlers.translation.glossary_pipeline_handler import GlossaryPipelineHandler
from ui.glossary_build_dialog import AREA_CURRENT, AREA_PROJECT, AREA_SELECTED


def _mw(dataset=None, current_idx=0, selected=None, bind_glossary=True):
    mw = MagicMock()
    mw.data_store.data = dataset if dataset is not None else [["a line"], ["another"]]
    # physical_block_idx is what the handler reads: current_block_idx is a
    # negative view marker while a virtual folder view is active.
    mw.data_store.physical_block_idx = current_idx
    mw.data_store.current_block_idx = current_idx
    mw.block_names = {}
    mw.target_language = "Ukrainian"
    mw.glossary_ai = {"provider": "Gemini", "api_key": "k"}

    manager = GlossaryManager()
    # The handler refuses to build against an unbound glossary, since seeded
    # entries would be discarded on the next reload. Nothing writes the file
    # here: the worker is mocked in these tests.
    path = Path(tempfile.gettempdir()) / "picoripi_test_project" / "glossary.json"
    manager.load_from_text(
        plugin_name=None, glossary_path=path if bind_glossary else None, raw_text=""
    )
    mw.translation_handler.glossary_handler.glossary_manager = manager
    # The handler binds through glossary_handler.bind_glossary_for_write, which
    # returns the bound path or None when there is no project.
    mw.translation_handler.glossary_handler.bind_glossary_for_write = MagicMock(
        return_value=path if bind_glossary else None
    )

    mw.get_selected_block_indices = MagicMock(return_value=selected or [])
    return mw


@patch("handlers.translation.glossary_pipeline_handler.QMessageBox")
def test_no_project_shows_message(mock_box):
    mw = _mw(dataset=[])
    GlossaryPipelineHandler(mw).build_from_text()
    mock_box.information.assert_called_once()


@patch("handlers.translation.glossary_pipeline_handler.QMessageBox")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildDialog")
def test_cancelled_dialog_starts_nothing(mock_dialog, mock_box):
    mock_dialog.return_value.exec.return_value = False
    handler = GlossaryPipelineHandler(_mw())
    handler.build_from_text()
    assert handler._worker is None


@patch("handlers.translation.glossary_pipeline_handler.AIStatusDialog")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildWorker")
@patch("handlers.translation.glossary_pipeline_handler.get_provider_for_config")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildDialog")
def test_worker_started_with_dialog_options(mock_dialog, mock_provider, mock_worker, mock_status):
    mock_dialog.return_value.exec.return_value = True
    mock_dialog.return_value.options.return_value = {
        "area": AREA_PROJECT,
        "mode": "draft",
        "chunk_size": "local",
        "translate": True,
    }
    handler = GlossaryPipelineHandler(_mw())
    handler.build_from_text()

    kwargs = mock_worker.call_args.kwargs
    assert kwargs["mode"] == "draft"
    assert kwargs["chunk_size"] == "local"
    assert kwargs["translate"] is True
    assert kwargs["block_indices"] is None  # whole project
    mock_worker.return_value.start.assert_called_once()


@patch("handlers.translation.glossary_pipeline_handler.AIStatusDialog")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildWorker")
@patch("handlers.translation.glossary_pipeline_handler.get_provider_for_config")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildDialog")
def test_current_block_area_limits_indices(mock_dialog, mock_provider, mock_worker, mock_status):
    mock_dialog.return_value.exec.return_value = True
    mock_dialog.return_value.options.return_value = {
        "area": AREA_CURRENT,
        "mode": "thorough",
        "chunk_size": "balanced",
        "translate": False,
    }
    handler = GlossaryPipelineHandler(_mw(current_idx=1))
    handler.build_from_text()
    assert mock_worker.call_args.kwargs["block_indices"] == [1]


@patch("handlers.translation.glossary_pipeline_handler.AIStatusDialog")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildWorker")
@patch("handlers.translation.glossary_pipeline_handler.get_provider_for_config")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildDialog")
def test_selected_area_uses_selection(mock_dialog, mock_provider, mock_worker, mock_status):
    mock_dialog.return_value.exec.return_value = True
    mock_dialog.return_value.options.return_value = {
        "area": AREA_SELECTED,
        "mode": "thorough",
        "chunk_size": "balanced",
        "translate": False,
    }
    handler = GlossaryPipelineHandler(_mw(selected=[0, 2]))
    handler.build_from_text()
    assert mock_worker.call_args.kwargs["block_indices"] == [0, 2]


@patch("handlers.translation.glossary_pipeline_handler.QMessageBox")
@patch("handlers.translation.glossary_pipeline_handler.get_provider_for_config")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildDialog")
def test_provider_failure_aborts(mock_dialog, mock_provider, mock_box):
    mock_dialog.return_value.exec.return_value = True
    mock_dialog.return_value.options.return_value = {
        "area": AREA_PROJECT, "mode": "thorough", "chunk_size": "balanced", "translate": False,
    }
    mock_provider.side_effect = RuntimeError("no key")
    handler = GlossaryPipelineHandler(_mw())
    handler.build_from_text()

    mock_box.critical.assert_called_once()
    assert handler._worker is None


@patch("handlers.translation.glossary_pipeline_handler.QMessageBox")
def test_finished_reports_and_refreshes(mock_box):
    mw = _mw()
    handler = GlossaryPipelineHandler(mw)
    handler._on_finished(True, "seeded 3, described 3, translated 0")

    mock_box.information.assert_called_once()
    mw.translation_handler.glossary_handler._update_glossary_highlighting.assert_called_once()


@patch("handlers.translation.glossary_pipeline_handler.QMessageBox")
def test_finished_failure_warns(mock_box):
    handler = GlossaryPipelineHandler(_mw())
    handler._on_finished(False, "provider exploded")
    mock_box.warning.assert_called_once()


@patch("handlers.translation.glossary_pipeline_handler.AIStatusDialog")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildWorker")
@patch("handlers.translation.glossary_pipeline_handler.get_provider_for_config")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildDialog")
def test_current_block_in_a_virtual_view_uses_the_physical_block(
    mock_dialog, mock_provider, mock_worker, mock_status
):
    """In a speaker/chapter view current_block_idx is -3; sweeping must not
    fall through to the whole project."""
    mock_dialog.return_value.exec.return_value = True
    mock_dialog.return_value.options.return_value = {
        "area": AREA_CURRENT,
        "mode": "draft",
        "chunk_size": "balanced",
        "translate": False,
    }
    mw = _mw(current_idx=1)
    mw.data_store.current_block_idx = -3  # ViewKind.SPEAKER marker
    handler = GlossaryPipelineHandler(mw)
    handler.build_from_text()

    assert mock_worker.call_args.kwargs["block_indices"] == [1]


@patch("handlers.translation.glossary_pipeline_handler.QMessageBox")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildDialog")
def test_build_refuses_to_run_with_no_project_to_store_the_glossary(mock_dialog, mock_box):
    """Nowhere to persist means the run would be discarded on the next reload."""
    mw = _mw(bind_glossary=False)
    handler = GlossaryPipelineHandler(mw)

    handler.build_from_text()

    mock_box.warning.assert_called_once()
    mock_dialog.assert_not_called()
    assert handler._worker is None


@patch("handlers.translation.glossary_pipeline_handler.AIStatusDialog")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildWorker")
@patch("handlers.translation.glossary_pipeline_handler.get_provider_for_config")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildDialog")
def test_build_binds_the_glossary_file_before_starting(
    mock_dialog, mock_provider, mock_worker, mock_status
):
    """The build must not start until the glossary has somewhere to persist."""
    mock_dialog.return_value.exec.return_value = True
    mock_dialog.return_value.options.return_value = {
        "area": AREA_PROJECT, "mode": "draft", "chunk_size": "local", "translate": False,
    }
    # Unbound at the start, exactly as a session that has not opened the
    # glossary yet: the build has to resolve the path itself.
    mw = _mw(bind_glossary=False)
    binder = mw.translation_handler.glossary_handler.bind_glossary_for_write
    binder.return_value = Path(tempfile.gettempdir()) / "picoripi_test_project" / "glossary.json"
    handler = GlossaryPipelineHandler(mw)

    handler.build_from_text()

    binder.assert_called_once()
    mock_worker.return_value.start.assert_called_once()


@patch("handlers.translation.glossary_pipeline_handler.AIStatusDialog")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildWorker")
@patch("handlers.translation.glossary_pipeline_handler.get_provider_for_config")
def test_a_build_can_start_from_options_without_showing_the_dialog(
    mock_provider, mock_worker, mock_status
):
    """The wizard hosts the form itself and starts the run from it."""
    handler = GlossaryPipelineHandler(_mw())

    handler.start_build(
        {"area": AREA_PROJECT, "mode": "draft", "chunk_size": "local", "translate": False}
    )

    mock_worker.return_value.start.assert_called_once()


class TestSeedSources:
    """Everything already written down, gathered before a single AI call."""

    def _handler(self, tmp_path, *, plugin_seeds=(), aliases=None):
        import json

        mw = _mw()
        mw.project_manager.project_dir = str(tmp_path)
        mw.current_game_rules.get_glossary_seed_entries.return_value = list(plugin_seeds)
        mw.translation_handler.prompt_composer._find_script_path.return_value = str(
            tmp_path / "script.txt"
        )
        if aliases:
            (tmp_path / "speaker_aliases.json").write_text(
                json.dumps(aliases), encoding="utf-8"
            )
        handler = GlossaryPipelineHandler(mw)
        handler.mw = mw
        return handler

    def test_a_decided_name_replaces_the_identifier_the_game_uses(self, tmp_path):
        """Merge Speakers worked out Bou is MAYOR BO; the glossary must know."""
        handler = self._handler(
            tmp_path,
            plugin_seeds=[{"term": "Bou", "section": "Characters", "description": "ev"}],
            aliases={"Bou": "MAYOR BO"},
        )

        seeds = handler._structural_seeds()

        assert [s["term"] for s in seeds] == ["MAYOR BO"]
        assert seeds[0]["description"] == "ev"   # the evidence follows the name

    def test_terms_that_are_not_speaker_codes_are_untouched(self, tmp_path):
        handler = self._handler(
            tmp_path,
            plugin_seeds=[{"term": "Lantern", "section": "Items"}],
            aliases={"Bou": "MAYOR BO"},
        )

        assert [s["term"] for s in handler._structural_seeds()] == ["Lantern"]

    def test_no_decisions_yet_changes_nothing(self, tmp_path):
        handler = self._handler(
            tmp_path, plugin_seeds=[{"term": "Bou", "section": "Characters"}]
        )

        assert [s["term"] for s in handler._structural_seeds()] == ["Bou"]

    def test_a_plugin_that_seeds_nothing_still_gets_the_script(self, tmp_path):
        """A game with no readable data files is not a game with no glossary."""
        handler = self._handler(tmp_path)
        handler._markup_seeds = lambda: [{"term": "RENADO", "section": "Characters"}]

        assert [s["term"] for s in handler._structural_seeds()] == ["RENADO"]

    def test_an_undecided_identifier_is_seeded_as_provisional(self, tmp_path):
        """"CLERK_B" is not a name, and the glossary must not present it as one."""
        handler = self._handler(
            tmp_path, plugin_seeds=[{"term": "CLERK_B", "section": "Characters"}]
        )
        handler.mw.current_game_rules.is_placeholder_speaker = lambda n: n == "CLERK_B"

        seeds = handler._structural_seeds()

        assert seeds[0]["provisional"] is True

    def test_deciding_the_name_clears_the_provisional_flag(self, tmp_path):
        handler = self._handler(
            tmp_path,
            plugin_seeds=[{"term": "CLERK_B", "section": "Characters"}],
            aliases={"CLERK_B": "BARNES"},
        )
        handler.mw.current_game_rules.is_placeholder_speaker = lambda n: n == "CLERK_B"

        seeds = handler._structural_seeds()

        assert seeds[0]["term"] == "BARNES"
        assert seeds[0]["provisional"] is False

    def test_a_real_name_is_never_flagged(self, tmp_path):
        handler = self._handler(
            tmp_path, plugin_seeds=[{"term": "Lantern", "section": "Items"}]
        )
        handler.mw.current_game_rules.is_placeholder_speaker = lambda n: False

        assert not handler._structural_seeds()[0].get("provisional")
