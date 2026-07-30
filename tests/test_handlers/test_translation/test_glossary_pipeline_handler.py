"""Tests for GlossaryPipelineHandler wiring (dialog -> provider -> worker)."""
from unittest.mock import MagicMock, patch

from core.glossary_manager import GlossaryManager
from handlers.translation.glossary_pipeline_handler import GlossaryPipelineHandler
from ui.glossary_build_dialog import AREA_CURRENT, AREA_PROJECT, AREA_SELECTED


def _mw(dataset=None, current_idx=0, selected=None):
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
    manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
    mw.translation_handler.glossary_handler.glossary_manager = manager

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
