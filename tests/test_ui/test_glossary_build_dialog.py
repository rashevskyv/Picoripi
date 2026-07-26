"""Tests for the Build-Glossary-from-Text launch dialog."""
from core.glossary_build.pipeline_coordinator import MODE_AUGMENT, MODE_DRAFT, MODE_THOROUGH
from ui.glossary_build_dialog import (
    AREA_CURRENT,
    AREA_PROJECT,
    AREA_SELECTED,
    GlossaryBuildDialog,
)


def test_defaults_without_selection(qtbot):
    dialog = GlossaryBuildDialog(has_selection=False, current_block_label="msg.bmg")
    qtbot.addWidget(dialog)

    options = dialog.options()
    assert options["area"] == AREA_CURRENT  # falls back to current block
    assert options["mode"] == MODE_THOROUGH  # thorough is the default depth
    assert options["chunk_size"] == "balanced"
    assert options["translate"] is False


def test_selected_area_preferred_when_available(qtbot):
    dialog = GlossaryBuildDialog(has_selection=True)
    qtbot.addWidget(dialog)
    assert dialog.options()["area"] == AREA_SELECTED


def test_selected_radio_disabled_without_selection(qtbot):
    dialog = GlossaryBuildDialog(has_selection=False)
    qtbot.addWidget(dialog)
    assert dialog._area_selected.isEnabled() is False


def test_area_and_mode_switches(qtbot):
    dialog = GlossaryBuildDialog(has_selection=False)
    qtbot.addWidget(dialog)

    dialog._area_project.setChecked(True)
    dialog._mode_draft.setChecked(True)
    options = dialog.options()
    assert options["area"] == AREA_PROJECT
    assert options["mode"] == MODE_DRAFT

    dialog._mode_augment.setChecked(True)
    assert dialog.options()["mode"] == MODE_AUGMENT


def test_chunk_and_translate_options(qtbot):
    dialog = GlossaryBuildDialog(has_selection=False)
    qtbot.addWidget(dialog)

    dialog._chunk_combo.setCurrentIndex(0)
    dialog._translate_check.setChecked(True)
    options = dialog.options()
    assert options["chunk_size"] == "local"
    assert options["translate"] is True


def test_current_block_label_shown(qtbot):
    dialog = GlossaryBuildDialog(has_selection=False, current_block_label="msg.bmg")
    qtbot.addWidget(dialog)
    assert "msg.bmg" in dialog._area_current.text()
