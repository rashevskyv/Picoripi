import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QDialog
from ui.autofix_selection_dialog import AutofixSelectionDialog

def test_AutofixSelectionDialog_init(mock_mw):
    mock_mw.align_sentences_to_original_pages = True
    mock_mw.prevent_empty_lines_in_autofix = True
    problem_defs = {"prob1": {"name": "Problem 1", "description": "Desc 1", "priority": 1}}
    active_autofixes = {"prob1": True}

    dialog = AutofixSelectionDialog(problem_defs, active_autofixes, mock_mw)
    
    assert dialog.align_sentences_checkbox.isChecked() is True
    assert dialog.prevent_empty_lines_checkbox.isChecked() is True
    assert "prob1" in dialog.checkboxes
    assert dialog.checkboxes["prob1"].isChecked() is True

def test_AutofixSelectionDialog_accept(mock_mw):
    mock_mw.align_sentences_to_original_pages = False
    mock_mw.prevent_empty_lines_in_autofix = False
    mock_mw.settings_manager = MagicMock()
    problem_defs = {"prob1": {"name": "Problem 1", "description": "Desc 1", "priority": 1}}
    active_autofixes = {"prob1": True}

    dialog = AutofixSelectionDialog(problem_defs, active_autofixes, mock_mw)
    dialog.align_sentences_checkbox.setChecked(True)
    dialog.prevent_empty_lines_checkbox.setChecked(True)
    
    dialog.accept()
    
    assert mock_mw.align_sentences_to_original_pages is True
    assert mock_mw.prevent_empty_lines_in_autofix is True
    mock_mw.settings_manager.plugin_settings.save.assert_called_once()
