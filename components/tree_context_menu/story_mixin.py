"""MemPalace / story assignment context-menu helpers."""
from PyQt6.QtWidgets import (
    QDialog, QInputDialog, QStyle, QTreeWidgetItemIterator,
)

from utils.logging_utils import log_debug
from core.i18n import tr


class StoryMixin:
    """Story / MemPalace context-menu actions."""

    def _mempalace_assignment_targets(self):
        """Return unique editable Memory Palace targets currently shown in the tree."""
        targets = {"story": [], "speaker": [], "item": [], "all": []}
        seen = set()
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            target = self._story_assignment_target(item)
            if target and target[0] in targets:
                facet, value, path = target
                key = (facet, str(value), tuple(path))
                if key not in seen:
                    seen.add(key)
                    targets[facet].append((value, tuple(path), item))
            iterator += 1
        return targets

    def _add_mempalace_context_menu(
        self, menu, selected_rows, preserve_tree_selection=False
    ):
        """Add an explicit choose-operation-then-target Memory Palace menu."""
        targets = self._mempalace_assignment_targets()
        if not any(targets.values()):
            return False

        count = len(selected_rows)
        palace_menu = menu.addMenu(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton),
            f"MemPalace Context ({count} selected)",
        )
        palace_menu.setEnabled(bool(selected_rows))
        preserved_locator = (
            self._virtual_item_locator(self.currentItem())
            if preserve_tree_selection and self.currentItem() is not None
            else None
        )

        definitions = (
            ("story", "Change Chapter / Scene", "None", "story:none"),
            ("speaker", "Change Speaker", "None", "None"),
            ("item", "Change Item", "None", "None"),
        )
        for facet, title, none_label, none_value in definitions:
            entries = list(targets[facet])
            if facet == "story":
                action = palace_menu.addAction(title + "…")
                action.triggered.connect(
                    lambda checked=False, rows=tuple(selected_rows),
                    story_entries=tuple(entries), restore_locator=preserved_locator:
                    self._open_story_assignment_dialog(
                        rows, story_entries, restore_locator
                    )
                )
                continue

            if facet == "speaker":
                action = palace_menu.addAction(title + "…")
                action.triggered.connect(
                    lambda checked=False, rows=tuple(selected_rows),
                    speaker_entries=tuple(entries), restore_locator=preserved_locator:
                    self._open_speaker_assignment_dialog(
                        rows, speaker_entries, restore_locator
                    )
                )
                continue

            facet_menu = palace_menu.addMenu(title)
            if not any(str(value) == none_value for value, _path, _item in entries):
                entries.append((none_value, (), None))

            def sort_key(entry):
                value, path, _target_item = entry
                label = " › ".join(path) if facet == "story" and path else str(value)
                return (str(value) != none_value, label.casefold())

            for value, path, target_item in sorted(entries, key=sort_key):
                label = (
                    " › ".join(path)
                    if facet == "story" and path
                    else (none_label if str(value) == none_value else str(value))
                )
                action = facet_menu.addAction(label)
                locator = preserved_locator or (
                    self._virtual_item_locator(target_item) if target_item else None
                )
                action.triggered.connect(
                    lambda checked=False, rows=tuple(selected_rows), target_facet=facet,
                    target_value=value, target_path=path, target_label=label,
                    target_locator=locator: self._assign_rows_to_story_context(
                        rows,
                        target_facet,
                        target_value,
                        target_path,
                        target_label,
                        target_locator,
                    )
                )

        palace_menu.addSeparator()
        notes_menu = palace_menu.addMenu(tr('Notes'))
        note_action = notes_menu.addAction(tr('Add / Edit Notes...'))
        note_action.triggered.connect(
            lambda checked=False, rows=tuple(selected_rows),
            restore_locator=preserved_locator:
                self._open_note_assignment_dialog(rows, restore_locator)
        )
        from core.story_context_overrides import get_story_context_override
        has_notes = any(
            str(get_story_context_override(self.window(), *row).get("translator_note") or "").strip()
            for row in selected_rows
        )
        clear_note_action = notes_menu.addAction(tr('Remove Notes'))
        clear_note_action.setEnabled(has_notes)
        clear_note_action.triggered.connect(
            lambda checked=False, rows=tuple(selected_rows),
            restore_locator=preserved_locator:
                self._set_notes_for_rows(rows, "", restore_locator)
        )
        palace_menu.addSeparator()
        clear_action = palace_menu.addAction(tr('Clear All Context'))
        clear_action.triggered.connect(
            lambda checked=False, rows=tuple(selected_rows),
            restore_locator=preserved_locator:
                self._assign_rows_to_story_context(
                    rows, "all", "None", (), "None", restore_locator
                )
        )
        return True

    def _open_speaker_in_glossary(self, display_name: str) -> None:
        """Open the glossary at the entry for a speaker folder.

        The folder shows the glossary-*translated* speaker name, but the glossary
        is keyed by the source original (``_select_initial_term`` matches
        ``entry.original``). Map the displayed translation back to its original so
        the right row is selected; for an untranslated speaker the displayed name
        already is the original (so the glossary opens ready to add its entry).
        """
        main_window = self.window()
        translator = getattr(main_window, 'translation_handler', None)
        if not translator or not hasattr(translator, 'show_glossary_dialog'):
            return
        original = str(display_name).strip()
        glossary_manager = (
            getattr(translator, '_glossary_manager', None)
            or getattr(getattr(translator, 'glossary_handler', None), 'glossary_manager', None)
        )
        try:
            for entry in (glossary_manager.get_entries() if glossary_manager else []):
                translation = str(getattr(entry, 'translation', '') or '').split(';')[0].strip()
                if translation and translation.casefold() == original.casefold():
                    original = str(getattr(entry, 'original', '') or '').strip() or original
                    break
        except Exception as exc:
            log_debug(f"_open_speaker_in_glossary: reverse lookup failed: {exc}")
        translator.show_glossary_dialog(original)

    def _open_note_assignment_dialog(self, selected_rows, restore_locator=None):
        """Collect one translator note and attach it to all selected rows."""
        if not selected_rows:
            return False
        from core.story_context_overrides import get_story_context_override

        notes = {
            str(get_story_context_override(self.window(), *row).get("translator_note") or "")
            for row in selected_rows
        }
        initial = notes.pop() if len(notes) == 1 else ""
        text, accepted = QInputDialog.getMultiLineText(
            self,
            "Translator Note",
            f"Note for {len(selected_rows)} selected string(s):",
            initial,
        )
        if not accepted:
            return False
        return self._set_notes_for_rows(selected_rows, text, restore_locator)

    def _open_story_assignment_dialog(
        self, selected_rows, entries, restore_locator=None
    ):
        """Choose a nested Story target in a searchable dialog."""
        from components.chapter_picker import ChapterSelectionDialog

        choices = [
            (value, path)
            for value, path, _item in entries
            if str(value) != "story:none" and path
        ]
        dialog = ChapterSelectionDialog(
            choices=choices,
            parent=self.window(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False

        structure_id, path = dialog.selection()
        value = structure_id if structure_id is not None else "story:none"
        target_item = next(
            (
                item
                for entry_value, entry_path, item in entries
                if entry_value == structure_id and tuple(entry_path) == tuple(path)
            ),
            None,
        )
        label = " › ".join(path) if path else "None"
        locator = restore_locator or (
            self._virtual_item_locator(target_item) if target_item else None
        )
        return self._assign_rows_to_story_context(
            tuple(selected_rows),
            "story",
            value,
            tuple(path),
            label,
            locator,
        )

    def _open_speaker_assignment_dialog(
        self, selected_rows, entries, restore_locator=None
    ):
        """Choose a speaker in a compact searchable dialog."""
        from components.name_picker import SpeakerSelectionDialog

        dialog = SpeakerSelectionDialog(
            [value for value, _path, _item in entries],
            parent=self.window(),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False

        name = dialog.selection()
        target_item = next(
            (item for value, _path, item in entries if str(value) == name),
            None,
        )
        locator = restore_locator or (
            self._virtual_item_locator(target_item) if target_item else None
        )
        return self._assign_rows_to_story_context(
            tuple(selected_rows),
            "speaker",
            name,
            (),
            name,
            locator,
        )

