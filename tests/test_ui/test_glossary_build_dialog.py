"""Tests for the Build-Glossary-from-Text launch dialog."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialogButtonBox

from core.glossary_build.pipeline_coordinator import (
    MODE_AUGMENT,
    MODE_AUTO,
    MODE_DRAFT,
    MODE_THOROUGH,
    MODE_TRANSLATE,
)
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


def test_translate_only_mode_forces_and_locks_translate(qtbot):
    """In translate-only mode the translation pass IS the run."""
    dialog = GlossaryBuildDialog(has_selection=False)
    qtbot.addWidget(dialog)

    dialog._mode_translate.setChecked(True)
    options = dialog.options()
    assert options["mode"] == MODE_TRANSLATE
    assert options["translate"] is True
    assert dialog._translate_check.isEnabled() is False


def test_leaving_translate_only_unlocks_the_checkbox(qtbot):
    dialog = GlossaryBuildDialog(has_selection=False)
    qtbot.addWidget(dialog)

    dialog._mode_translate.setChecked(True)
    dialog._mode_thorough.setChecked(True)
    assert dialog._translate_check.isEnabled() is True


def test_current_block_label_shown(qtbot):
    dialog = GlossaryBuildDialog(has_selection=False, current_block_label="msg.bmg")
    qtbot.addWidget(dialog)
    assert "msg.bmg" in dialog._area_current.text()


class TestWhatThisProjectCanActuallyOffer:
    """A choice that cannot work here says so instead of running and reporting zero."""

    def test_structural_seed_is_locked_without_a_source(self, qapp):
        dialog = GlossaryBuildDialog(can_seed_structurally=False)

        assert not dialog._mode_seed.isEnabled()
        assert "marked-up" in dialog._mode_seed.toolTip()

    def test_structural_seed_is_offered_when_something_can_supply_it(self, qapp):
        dialog = GlossaryBuildDialog(can_seed_structurally=True)


        assert dialog._mode_seed.isEnabled()

    def test_follow_up_passes_are_locked_on_an_empty_glossary(self, qapp):
        """They work on existing entries, so a depth has to have run first."""
        dialog = GlossaryBuildDialog(existing_entries=0)

        assert not dialog._mode_augment.isEnabled()
        assert not dialog._mode_translate.isEnabled()
        assert "empty" in dialog._mode_augment.toolTip()

    def test_follow_up_passes_open_up_once_entries_exist(self, qapp):
        dialog = GlossaryBuildDialog(existing_entries=12)

        assert dialog._mode_augment.isEnabled()
        assert dialog._mode_translate.isEnabled()

    def test_a_depth_is_always_available(self, qapp):
        """Sweeping text with AI needs nothing but the text."""
        dialog = GlossaryBuildDialog(can_seed_structurally=False, existing_entries=0)

        assert dialog._mode_thorough.isEnabled()
        assert dialog._mode_draft.isEnabled()

    def test_embedded_it_builds_in_place_instead_of_accepting(self, qapp):
        started = []
        dialog = GlossaryBuildDialog(on_build=lambda: started.append(True))

        dialog.findChild(QDialogButtonBox).button(
            QDialogButtonBox.StandardButton.Ok
        ).click()

        assert started == [True]
        assert not dialog.isModal()
        assert dialog.findChild(QDialogButtonBox).button(
            QDialogButtonBox.StandardButton.Cancel
        ) is None


class TestTargetStepViews:
    def test_auto_route_selects_all_blocks_and_all_passes(self, qtbot):
        dialog = GlossaryBuildDialog(
            target_step="auto", block_labels=[(0, "Intro"), (1, "Village")]
        )
        qtbot.addWidget(dialog)

        options = dialog.options()
        assert options["mode"] == MODE_AUTO
        assert options["block_indices"] is None
        assert options["translate"] is True
        assert options["full_rescan"] is False

    def test_auto_route_can_exclude_individual_blocks(self, qtbot):
        dialog = GlossaryBuildDialog(
            target_step="auto", block_labels=[(0, "Intro"), (1, "Village")]
        )
        qtbot.addWidget(dialog)

        dialog._block_list.item(1).setCheckState(Qt.CheckState.Unchecked)

        assert dialog.options()["block_indices"] == [0]
        assert "1 of 2" in dialog._all_blocks_check.text()

    def test_sweep_step_tailored_view(self, qtbot):
        dialog = GlossaryBuildDialog(target_step="seed")
        qtbot.addWidget(dialog)
        ok_btn = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)

        assert ok_btn.text() == "Sweep text with AI"
        assert not dialog._mode_thorough.isHidden()
        assert not dialog._mode_draft.isHidden()
        assert dialog._translate_check is not None
        assert not dialog._translate_check.isHidden()
        assert dialog.options()["mode"] == MODE_THOROUGH

    def test_describe_step_tailored_view(self, qtbot):
        dialog = GlossaryBuildDialog(target_step="describe", existing_entries=5)
        qtbot.addWidget(dialog)
        ok_btn = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)

        assert ok_btn.text() == "Describe terms"
        assert ok_btn.isEnabled()
        assert dialog._translate_check is None
        assert dialog.options()["mode"] == MODE_AUGMENT

    def test_describe_step_disabled_when_glossary_is_empty(self, qtbot):
        dialog = GlossaryBuildDialog(target_step="describe", existing_entries=0)
        qtbot.addWidget(dialog)
        ok_btn = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)

        assert ok_btn.text() == "Describe terms"
        assert not ok_btn.isEnabled()
        assert "empty" in ok_btn.toolTip().lower()
