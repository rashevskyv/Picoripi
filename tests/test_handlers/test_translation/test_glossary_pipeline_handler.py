"""Tests for GlossaryPipelineHandler wiring (dialog -> provider -> worker)."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.glossary_manager import GlossaryManager
from core.glossary_build.pipeline_coordinator import MODE_AUGMENT, MODE_AUTO
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
    mw.current_game_rules.is_placeholder_speaker.return_value = False

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
@patch("handlers.translation.glossary_pipeline_handler.build_speaker_pool")
def test_start_build_binds_raw_speaker_pool(
    mock_build_pool, mock_provider, mock_worker, mock_status
):
    mock_build_pool.return_value = {(0, 0): "AGITHA'S STALKER"}
    mw = _mw()
    handler = GlossaryPipelineHandler(mw)
    manager = mw.translation_handler.glossary_handler.glossary_manager

    handler.start_build({
        "area": AREA_PROJECT,
        "mode": "draft",
        "chunk_size": "local",
        "translate": True,
    }, manager=manager)

    mock_build_pool.assert_called_once_with(mw, raw=True)
    assert manager._speaker_pool == {(0, 0): "AGITHA'S STALKER"}



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

    mock_box.return_value.exec.assert_called_once()
    mw.translation_handler.glossary_handler._update_glossary_highlighting.assert_called_once()


@patch("handlers.translation.glossary_pipeline_handler.GlossaryStoppedDialog")
def test_finished_failure_shows_stopped_dialog(mock_dialog):
    mock_dialog.return_value.action = "close"
    handler = GlossaryPipelineHandler(_mw())
    handler._on_finished(False, "provider exploded")
    mock_dialog.return_value.exec.assert_called_once()
    assert mock_dialog.call_args.kwargs["auto_retry_delay"] == 300


@patch("handlers.translation.glossary_pipeline_handler.GlossaryStoppedDialog")
def test_stopped_dialog_consecutive_failure_uses_600s_delay(mock_dialog):
    mock_dialog.return_value.action = "resume"
    handler = GlossaryPipelineHandler(_mw())
    handler._stopped_retry_count = 1
    handler.start_build = MagicMock()

    handler._on_finished(False, "provider exploded again")

    assert mock_dialog.call_args.kwargs["auto_retry_delay"] == 600
    assert handler._stopped_retry_count == 2
    handler.start_build.assert_called_once()


@patch("handlers.translation.glossary_pipeline_handler.QMessageBox")
def test_success_resets_stopped_retry_count(mock_box):
    mw = _mw()
    handler = GlossaryPipelineHandler(mw)
    handler._stopped_retry_count = 3
    handler._on_finished(True, "seeded 1, described 1, translated 1")
    assert handler._stopped_retry_count == 0


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


@patch("handlers.translation.glossary_pipeline_handler.AIStatusDialog")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildWorker")
@patch("handlers.translation.glossary_pipeline_handler.get_provider_for_config")
def test_auto_route_sweeps_only_changed_blocks(
    mock_provider, mock_worker, mock_status
):
    mw = _mw(dataset=[["same"], ["changed"]])
    handler = GlossaryPipelineHandler(mw)
    handler._load_scan_state = MagicMock(
        return_value={"0": handler._fingerprint_block(["same"]), "1": "old"}
    )

    handler.start_build(
        {
            "area": AREA_PROJECT,
            "mode": MODE_AUTO,
            "chunk_size": "balanced",
            "translate": True,
            "block_indices": None,
            "full_rescan": False,
        }
    )

    kwargs = mock_worker.call_args.kwargs
    assert kwargs["mode"] == MODE_AUTO
    assert kwargs["block_indices"] == [1]
    assert kwargs["translate"] is True


@patch("handlers.translation.glossary_pipeline_handler.AIStatusDialog")
@patch("handlers.translation.glossary_pipeline_handler.GlossaryBuildWorker")
@patch("handlers.translation.glossary_pipeline_handler.get_provider_for_config")
def test_resume_pending_switches_mode_to_augment(
    mock_provider, mock_worker, mock_status
):
    mw = _mw()
    handler = GlossaryPipelineHandler(mw)
    handler.start_build(
        {
            "area": AREA_PROJECT,
            "mode": MODE_AUTO,
            "resume_pending": True,
            "chunk_size": "balanced",
            "translate": True,
        }
    )
    kwargs = mock_worker.call_args.kwargs
    assert kwargs["mode"] == MODE_AUGMENT


class TestSeedSources:
    """The build seeds characters under the names decided in Merge Speakers."""

    def test_a_decided_name_replaces_the_identifier_the_game_uses(self, tmp_path):
        mw = _mw()
        mw.project_manager.project_dir = str(tmp_path)
        aliases_path = tmp_path / "speaker_aliases.json"
        aliases_path.write_text('{"Bou": "MAYOR BO"}', encoding="utf-8")

        handler = GlossaryPipelineHandler(mw)
        handler._plugin_seeds = MagicMock(return_value=[{"term": "Bou", "section": "Characters"}])
        handler._markup_seeds = MagicMock(return_value=[])

        seeded = handler._structural_seeds()
        assert seeded == [{"term": "MAYOR BO", "section": "Characters", "provisional": False}]

    def test_terms_that_are_not_speaker_codes_are_untouched(self, tmp_path):
        mw = _mw()
        mw.project_manager.project_dir = str(tmp_path)
        aliases_path = tmp_path / "speaker_aliases.json"
        aliases_path.write_text('{"Bou": "MAYOR BO"}', encoding="utf-8")

        handler = GlossaryPipelineHandler(mw)
        handler._plugin_seeds = MagicMock(return_value=[{"term": "Master Sword", "section": "Items"}])
        handler._markup_seeds = MagicMock(return_value=[])

        seeded = handler._structural_seeds()
        assert seeded == [{"term": "Master Sword", "section": "Items"}]

    def test_no_decisions_yet_changes_nothing(self, tmp_path):
        mw = _mw()
        mw.project_manager.project_dir = str(tmp_path)

        handler = GlossaryPipelineHandler(mw)
        handler._plugin_seeds = MagicMock(return_value=[{"term": "Bou"}])
        handler._markup_seeds = MagicMock(return_value=[])

        assert handler._structural_seeds() == [{"term": "Bou"}]

    def test_a_plugin_that_seeds_nothing_still_gets_the_script(self, tmp_path):
        mw = _mw()
        mw.project_manager.project_dir = str(tmp_path)

        handler = GlossaryPipelineHandler(mw)
        handler._plugin_seeds = MagicMock(return_value=[])
        handler._markup_seeds = MagicMock(return_value=[{"term": "Link"}])

        assert handler._structural_seeds() == [{"term": "Link"}]

    def test_an_undecided_identifier_is_seeded_as_provisional(self, tmp_path):
        """A placeholder speaker code needs to say so in the glossary."""
        mw = _mw()
        mw.project_manager.project_dir = str(tmp_path)
        mw.current_game_rules.is_placeholder_speaker.side_effect = lambda t: t == "CLERK_B"

        handler = GlossaryPipelineHandler(mw)
        handler._plugin_seeds = MagicMock(return_value=[{"term": "CLERK_B"}])
        handler._markup_seeds = MagicMock(return_value=[])

        seeded = handler._structural_seeds()
        assert seeded == [{"term": "CLERK_B", "provisional": True}]

    def test_deciding_the_name_clears_the_provisional_flag(self, tmp_path):
        """Once confirmed to be a real character name, the provisional mark drops."""
        mw = _mw()
        mw.project_manager.project_dir = str(tmp_path)
        mw.current_game_rules.is_placeholder_speaker.side_effect = lambda t: t == "CLERK_B"
        aliases_path = tmp_path / "speaker_aliases.json"
        aliases_path.write_text('{"CLERK_B": "BEEDLE"}', encoding="utf-8")

        handler = GlossaryPipelineHandler(mw)
        handler._plugin_seeds = MagicMock(return_value=[{"term": "CLERK_B"}])
        handler._markup_seeds = MagicMock(return_value=[])

        seeded = handler._structural_seeds()
        assert seeded == [{"term": "BEEDLE", "provisional": False}]

    def test_a_shared_voice_seeds_each_named_character(self, tmp_path):
        mw = _mw()
        mw.project_manager.project_dir = str(tmp_path)
        mw.current_game_rules.is_placeholder_speaker.side_effect = lambda t: t == "zrSPA"
        aliases_path = tmp_path / "speaker_aliases.json"
        aliases_path.write_text(
            '{"zrSPA": "SPRING ZORA #1 / SPRING ZORA #2"}', encoding="utf-8"
        )

        handler = GlossaryPipelineHandler(mw)
        handler._plugin_seeds = MagicMock(
            return_value=[{"term": "zrSPA", "section": "Characters"}]
        )
        handler._markup_seeds = MagicMock(return_value=[])

        seeded = handler._structural_seeds()
        assert seeded == [
            {"term": "SPRING ZORA #1", "section": "Characters", "provisional": False},
            {"term": "SPRING ZORA #2", "section": "Characters", "provisional": False},
        ]

    def test_a_real_name_is_never_flagged(self, tmp_path):
        mw = _mw()
        mw.project_manager.project_dir = str(tmp_path)
        mw.current_game_rules.is_placeholder_speaker.side_effect = lambda t: False

        handler = GlossaryPipelineHandler(mw)
        handler._plugin_seeds = MagicMock(return_value=[{"term": "Link"}])
        handler._markup_seeds = MagicMock(return_value=[])

        seeded = handler._structural_seeds()
        assert seeded == [{"term": "Link"}]
