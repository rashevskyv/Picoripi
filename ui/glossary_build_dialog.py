"""Launch dialog for building the glossary from project text.

Collects the options the pipeline needs -- area, depth mode, chunk-size preset,
and whether to translate right away -- and hands them back as a plain dict.
The build itself runs in GlossaryBuildWorker; this dialog only gathers input.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

from PyQt6.QtCore import Qt

from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QRadioButton,
    QVBoxLayout,
)

from core.glossary_build.pipeline_coordinator import (
    MODE_AUGMENT,
    MODE_AUTO,
    MODE_DRAFT,
    MODE_SEED,
    MODE_THOROUGH,
    MODE_TRANSLATE,
)


AREA_PROJECT = "project"
AREA_SELECTED = "selected"
AREA_CURRENT = "current"


class GlossaryBuildDialog(QDialog):
    """Ask for glossary build options."""

    def __init__(
        self,
        parent=None,
        *,
        has_selection: bool = False,
        current_block_label: str = "",
        can_seed_structurally: bool = True,
        existing_entries: int = 0,
        on_build=None,
        target_step: Optional[str] = None,
        block_labels: Sequence[Tuple[int, str]] = (),
    ):
        super().__init__(parent)
        self._target_step = target_step
        self._existing_entries = existing_entries

        if target_step == "auto":
            self.setWindowTitle("Prepare Glossary")
        elif target_step == "seed":
            self.setWindowTitle("Sweep Text with AI")
        elif target_step == "describe":
            self.setWindowTitle("Describe Glossary Terms")
        else:
            self.setWindowTitle("Build Glossary from Text")

        self.setModal(on_build is None)
        self.setMinimumWidth(460)
        self._on_build = on_build

        layout = QVBoxLayout(self)

        if target_step == "auto":
            intro_text = (
                "One automatic pass seeds terms from game data and Script Markup, "
                "finds additional terms in the selected text, builds descriptions, "
                "and proposes translation variants. It never pauses for review; "
                "all unresolved choices remain in the glossary backlog."
            )
        elif target_step == "seed":
            intro_text = (
                "Sweeps project dialogue text with AI to find character nicknames, "
                "lore terms, magic spells, and items that do not appear in system tables, "
                "then describes each term."
            )
        elif target_step == "describe":
            intro_text = (
                "Reads context from project text around where existing glossary terms appear, "
                "synthesizing detailed descriptions for each term."
            )
        else:
            intro_text = (
                "Sweeps project text with AI to collect glossary terms, then describes "
                "each term from the context around every place it appears."
            )
        intro = QLabel(intro_text)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        if target_step == "describe" and existing_entries == 0:
            warn = QLabel(
                "⚠️ <b>Glossary is empty</b>: there are no terms to describe yet.<br>"
                "Run <i>Seed terms from game data</i> or <i>Sweep text with AI</i> first."
            )
            warn.setStyleSheet("color: #d9534f; margin-top: 4px; margin-bottom: 4px;")
            warn.setWordWrap(True)
            layout.addWidget(warn)

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

        self._has_selection = has_selection
        self._area_selected.setEnabled(has_selection)
        if has_selection:
            self._area_selected.setChecked(True)
        else:
            self._area_current.setChecked(True)
        layout.addWidget(area_box)

        self._block_list = None
        self._all_blocks_check = None
        self._full_rescan_check = None
        if target_step == "auto":
            area_box.hide()
            blocks_box = QGroupBox("Project blocks")
            blocks_layout = QVBoxLayout(blocks_box)
            self._all_blocks_check = QCheckBox("Whole project")
            self._all_blocks_check.setChecked(True)
            self._all_blocks_check.toggled.connect(self._toggle_all_blocks)
            blocks_layout.addWidget(self._all_blocks_check)
            self._block_list = QListWidget()
            self._block_list.setMaximumHeight(180)
            self._syncing_blocks = True
            for block_idx, block_label in block_labels:
                item = QListWidgetItem(block_label)
                item.setData(Qt.ItemDataRole.UserRole, int(block_idx))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                self._block_list.addItem(item)
            self._syncing_blocks = False
            self._block_list.itemChanged.connect(self._sync_block_selection)
            blocks_layout.addWidget(self._block_list)
            layout.addWidget(blocks_box)

        # -- build passes ----------------------------------------------------
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
        self._mode_seed = QRadioButton("Structural seed only (no AI)")
        self._mode_seed.setToolTip(
            "Take only the terms already written down somewhere -- the game's own "
            "item windows, location plates and boss cards, and the characters a "
            "marked-up script names. Makes no AI request at all, and fills only "
            "gaps, so it is safe to run first and safe to repeat."
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
            (self._mode_seed, MODE_SEED),
            (self._mode_augment, MODE_AUGMENT),
            (self._mode_translate, MODE_TRANSLATE),
        ):
            self._mode_group.addButton(button)
            button.setProperty("mode_key", key)

        if target_step == "auto":
            self._mode_thorough.setChecked(True)
        elif target_step == "seed":
            mode_box = QGroupBox("Sweep Depth")
            mode_layout = QVBoxLayout(mode_box)
            mode_layout.addWidget(self._mode_thorough)
            mode_layout.addWidget(self._mode_draft)
            layout.addWidget(mode_box)
            self._mode_thorough.setChecked(True)
        elif target_step == "describe":
            self._mode_augment.setChecked(True)
        else:
            mode_box = QGroupBox("Depth")
            mode_layout = QVBoxLayout(mode_box)
            mode_layout.addWidget(self._mode_thorough)
            mode_layout.addWidget(self._mode_draft)
            mode_layout.addWidget(self._mode_seed)

            follow_box = QGroupBox("Follow-up passes")
            follow_layout = QVBoxLayout(follow_box)
            follow_layout.addWidget(self._mode_augment)
            follow_layout.addWidget(self._mode_translate)

            layout.addWidget(mode_box)
            layout.addWidget(follow_box)

            self._set_available(
                self._mode_seed,
                can_seed_structurally,
                "Nothing to seed from: this game's plugin reads no terms out of its "
                "data files, and no marked-up Script Markup Studio project was found. "
                "Mark a script up, or use a depth that sweeps the text with AI.",
            )
            for button in (self._mode_augment, self._mode_translate):
                self._set_available(
                    button,
                    existing_entries > 0,
                    "The glossary is empty, so there are no entries to work on. Run a "
                    "depth first -- Thorough, Draft, or Structural seed only -- then "
                    "come back to this pass.",
                )
            self._mode_thorough.setChecked(True)

        # -- options -------------------------------------------------------
        options = QFormLayout()
        self._chunk_combo = QComboBox()
        self._chunk_combo.addItem("Local / small model (2000)", "local")
        self._chunk_combo.addItem("Balanced (4000)", "balanced")
        self._chunk_combo.addItem("Cloud / large model (8000)", "cloud")
        self._chunk_combo.setCurrentIndex(1)
        options.addRow("Chunk size:", self._chunk_combo)
        layout.addLayout(options)

        self._translate_check = None
        if target_step != "describe":
            self._translate_check = QCheckBox("Also propose translations now")
            self._translate_check.setToolTip(
                "Runs the translation pass right after describing. You can also run it later."
            )
            layout.addWidget(self._translate_check)

            self._mode_translate.toggled.connect(self._sync_translate_check)
            self._sync_translate_check(self._mode_translate.isChecked())
            self._mode_seed.toggled.connect(self._sync_seed_mode)
            self._sync_seed_mode(self._mode_seed.isChecked())
            if target_step == "auto":
                self._translate_check.setChecked(True)
                self._translate_check.hide()

                self._full_rescan_check = QCheckBox("Re-scan every selected block with AI")
                self._full_rescan_check.setToolTip(
                    "Normally only new or changed blocks are swept. Enable this for a "
                    "deliberate full evidence rebuild; existing confirmed choices stay protected."
                )
                layout.addWidget(self._full_rescan_check)

        standard = QDialogButtonBox.StandardButton.Ok
        if on_build is None:
            standard |= QDialogButtonBox.StandardButton.Cancel
        buttons = QDialogButtonBox(standard)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)

        self._ok_button = ok_btn
        if target_step == "auto":
            ok_btn.setText("Run automatic glossary pass")
        elif target_step == "seed":
            ok_btn.setText("Sweep text with AI")
        elif target_step == "describe":
            ok_btn.setText("Describe terms")
            if existing_entries == 0:
                ok_btn.setEnabled(False)
                ok_btn.setToolTip(
                    "The glossary is empty. Run structural seed or text sweep first to collect terms."
                )
        else:
            ok_btn.setText("Build")

        buttons.accepted.connect(on_build if on_build is not None else self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if target_step == "auto":
            self._sync_block_selection()

    @staticmethod
    def _set_available(button, available: bool, why: str) -> None:
        """Disable a choice and let its tooltip say what would enable it."""
        button.setEnabled(available)
        if not available:
            button.setToolTip(why)

    def _sync_translate_check(self, translate_only: bool) -> None:
        """Force the translate option on (and lock it) in translate-only mode."""
        if self._translate_check is not None:
            if translate_only:
                self._translate_check.setChecked(True)
            self._translate_check.setEnabled(not translate_only)

    def _sync_seed_mode(self, seed_only: bool) -> None:
        """Structural seeding reads game data, not text: hide the text options."""
        if self._translate_check is not None:
            if seed_only:
                self._translate_check.setChecked(False)
            self._translate_check.setEnabled(not seed_only)
        self._chunk_combo.setEnabled(not seed_only)
        for button in (self._area_project, self._area_selected, self._area_current):
            button.setEnabled(not seed_only and self._area_enabled(button))

    def _area_enabled(self, button) -> bool:
        """Selected-blocks stays disabled without a selection."""
        return self._has_selection if button is self._area_selected else True

    def selected_area(self) -> str:
        button = self._area_group.checkedButton()
        return button.property("area_key") if button else AREA_CURRENT

    def selected_mode(self) -> str:
        if self._target_step == "auto":
            return MODE_AUTO
        if self._target_step == "describe":
            return MODE_AUGMENT
        button = self._mode_group.checkedButton()
        return button.property("mode_key") if button else MODE_THOROUGH

    def options(self) -> Dict[str, Any]:
        """Return the chosen options."""
        translate_checked = (
            self._translate_check.isChecked()
            if self._translate_check is not None
            else False
        )
        options = {
            "area": self.selected_area(),
            "mode": self.selected_mode(),
            "chunk_size": self._chunk_combo.currentData(),
            "translate": translate_checked or self._target_step == "auto",
        }
        if self._target_step == "auto":
            selected = self.selected_block_indices()
            total = self._block_list.count() if self._block_list is not None else 0
            options["block_indices"] = None if len(selected) == total else selected
            options["full_rescan"] = bool(
                self._full_rescan_check and self._full_rescan_check.isChecked()
            )
        return options

    def selected_block_indices(self) -> list[int]:
        """Checked physical blocks, in project order."""
        if self._block_list is None:
            return []
        return [
            int(self._block_list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self._block_list.count())
            if self._block_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _toggle_all_blocks(self, checked: bool) -> None:
        if self._block_list is None or self._syncing_blocks:
            return
        self._syncing_blocks = True
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for index in range(self._block_list.count()):
            self._block_list.item(index).setCheckState(state)
        self._syncing_blocks = False
        self._sync_block_selection()

    def _sync_block_selection(self, _item=None) -> None:
        if self._block_list is None or self._syncing_blocks:
            return
        selected = len(self.selected_block_indices())
        total = self._block_list.count()
        if self._all_blocks_check is not None:
            self._all_blocks_check.blockSignals(True)
            self._all_blocks_check.setChecked(selected == total)
            self._all_blocks_check.setText(
                "Whole project" if selected == total else f"Selected blocks: {selected} of {total}"
            )
            self._all_blocks_check.blockSignals(False)
        if hasattr(self, "_ok_button"):
            self._ok_button.setEnabled(selected > 0)
