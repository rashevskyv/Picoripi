"""Launch dialog for building the glossary from project text.

Collects the options the pipeline needs -- area, depth mode, chunk-size preset,
and whether to translate right away -- and hands them back as a plain dict.
The build itself runs in GlossaryBuildWorker; this dialog only gathers input.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from core.glossary_build.pipeline_coordinator import (
    MODE_AUGMENT,
    MODE_DRAFT,
    MODE_THOROUGH,
    MODE_TRANSLATE,
)


AREA_PROJECT = "project"
AREA_SELECTED = "selected"
AREA_CURRENT = "current"


class GlossaryBuildDialog(QDialog):
    """Ask for glossary build options."""

    def __init__(self, parent=None, *, has_selection: bool = False, current_block_label: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Build Glossary from Text")
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Sweeps project text with AI to collect glossary terms, then describes "
            "each term from the context around every place it appears."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # -- area ----------------------------------------------------------
        area_box = QGroupBox("Area")
        area_layout = QVBoxLayout(area_box)
        self._area_group = QButtonGroup(self)

        self._area_project = QRadioButton("Whole project")
        self._area_selected = QRadioButton("Selected blocks")
        label = f"Current block ({current_block_label})" if current_block_label else "Current block"
        self._area_current = QRadioButton(label)

        for button, key in (
            (self._area_project, AREA_PROJECT),
            (self._area_selected, AREA_SELECTED),
            (self._area_current, AREA_CURRENT),
        ):
            self._area_group.addButton(button)
            button.setProperty("area_key", key)
            area_layout.addWidget(button)

        self._area_selected.setEnabled(has_selection)
        if has_selection:
            self._area_selected.setChecked(True)
        else:
            self._area_current.setChecked(True)
        layout.addWidget(area_box)

        # -- mode ----------------------------------------------------------
        mode_box = QGroupBox("Depth")
        mode_layout = QVBoxLayout(mode_box)
        self._mode_group = QButtonGroup(self)

        self._mode_thorough = QRadioButton("Thorough (recommended)")
        self._mode_thorough.setToolTip(
            "Sweep for terms, then describe each one from every place it appears."
        )
        self._mode_draft = QRadioButton("Draft (fast, rough)")
        self._mode_draft.setToolTip(
            "One sweep only. Descriptions come from wherever a term was first seen, "
            "so entries are marked unconfirmed."
        )
        self._mode_augment = QRadioButton("Augment existing entries")
        self._mode_augment.setToolTip(
            "Skip the sweep. Describe glossary entries that already exist, using the project text."
        )
        self._mode_translate = QRadioButton("Translate existing entries only")
        self._mode_translate.setToolTip(
            "No sweep, no describing. Propose translations for entries that already have a "
            "description but no translation. Entries that are already translated are left alone."
        )

        for button, key in (
            (self._mode_thorough, MODE_THOROUGH),
            (self._mode_draft, MODE_DRAFT),
            (self._mode_augment, MODE_AUGMENT),
            (self._mode_translate, MODE_TRANSLATE),
        ):
            self._mode_group.addButton(button)
            button.setProperty("mode_key", key)
            mode_layout.addWidget(button)

        self._mode_thorough.setChecked(True)
        layout.addWidget(mode_box)

        # -- options -------------------------------------------------------
        options = QFormLayout()
        self._chunk_combo = QComboBox()
        self._chunk_combo.addItem("Local / small model (2000)", "local")
        self._chunk_combo.addItem("Balanced (4000)", "balanced")
        self._chunk_combo.addItem("Cloud / large model (8000)", "cloud")
        self._chunk_combo.setCurrentIndex(1)
        options.addRow("Chunk size:", self._chunk_combo)
        layout.addLayout(options)

        self._translate_check = QCheckBox("Also propose translations now")
        self._translate_check.setToolTip(
            "Runs the translation pass right after describing. You can also run it later."
        )
        layout.addWidget(self._translate_check)

        # In translate-only mode the translation pass IS the run, so the choice
        # is not the user's to make — show it as on and locked.
        self._mode_translate.toggled.connect(self._sync_translate_check)
        self._sync_translate_check(self._mode_translate.isChecked())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Build")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _sync_translate_check(self, translate_only: bool) -> None:
        """Force the translate option on (and lock it) in translate-only mode."""
        if translate_only:
            self._translate_check.setChecked(True)
        self._translate_check.setEnabled(not translate_only)

    def selected_area(self) -> str:
        button = self._area_group.checkedButton()
        return button.property("area_key") if button else AREA_CURRENT

    def selected_mode(self) -> str:
        button = self._mode_group.checkedButton()
        return button.property("mode_key") if button else MODE_THOROUGH

    def options(self) -> Dict[str, Any]:
        """Return the chosen options."""
        return {
            "area": self.selected_area(),
            "mode": self.selected_mode(),
            "chunk_size": self._chunk_combo.currentData(),
            "translate": self._translate_check.isChecked(),
        }
