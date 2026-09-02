import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QWidget

from core.script_markup import HierarchyMark, HierarchyType
from ui.script_markup_studio_dialog import ScriptMarkupStudioDialog


def _fresh_autosave_path():
    return Path(tempfile.gettempdir()) / f"picoripi_sms_test_{uuid.uuid4().hex}.json"


def _make_dialog(qapp):
    mock_mw = MagicMock()
    # current_game_rules=None → "Picoripi rules" mode uses the real BaseGameRules.
    mock_mw.current_game_rules = None
    mock_mw.script_markup_studio_autosave_path = _fresh_autosave_path()
    parent = QWidget()
    dialog = ScriptMarkupStudioDialog(mock_mw, parent=parent)
    dialog._test_parent = parent  # keep parent alive (WA_DeleteOnClose)
    return dialog


def _use_custom_mode(dialog):
    dialog.mode = "custom"
    dialog._update_mode_controls()


def _use_hierarchy_mode(dialog):
    dialog.mode = "hierarchy"
    dialog._update_mode_controls()


def _use_picoripi_mode(dialog):
    dialog.mode = "picoripi"
    dialog._update_mode_controls()


def _set_hierarchy_type(dialog, type_id):
    for idx in range(dialog.hierarchy_type_combo.count()):
        if dialog.hierarchy_type_combo.itemData(idx) == type_id:
            dialog.hierarchy_type_combo.setCurrentIndex(idx)
            return
    raise AssertionError(f"Missing hierarchy type {type_id}")


def _select_lines(dialog, first_line, last_line):
    doc = dialog.raw_edit.document()
    start_block = doc.findBlockByNumber(first_line)
    end_block = doc.findBlockByNumber(last_line)
    cursor = dialog.raw_edit.textCursor()
    cursor.setPosition(start_block.position())
    cursor.setPosition(
        end_block.position() + len(end_block.text()),
        QTextCursor.MoveMode.KeepAnchor,
    )
    dialog.raw_edit.setTextCursor(cursor)


def _tree_item_count(tree):
    def count_item(item):
        return 1 + sum(count_item(item.child(i)) for i in range(item.childCount()))

    return sum(count_item(tree.topLevelItem(i)) for i in range(tree.topLevelItemCount()))


def _find_tree_item(tree, text):
    def walk(item):
        if text in item.text(0):
            return item
        for idx in range(item.childCount()):
            found = walk(item.child(idx))
            if found is not None:
                return found
        return None

    for idx in range(tree.topLevelItemCount()):
        found = walk(tree.topLevelItem(idx))
        if found is not None:
            return found
    raise AssertionError(f"Missing tree item containing {text!r}")


def _large_hierarchy_script(line_count=1200):
    lines = []
    marks = []
    order = 1

    for section in range((line_count + 11) // 12):
        base = len(lines)
        if base >= line_count:
            break

        lines.append(f"Scene {section}")
        scene_end = min(base + 11, line_count - 1)
        marks.append(
            HierarchyMark(
                base,
                scene_end,
                0,
                HierarchyType.STRUCTURE,
                text=f"Scene {section}",
                order=order,
            )
        )
        order += 1

        if len(lines) >= line_count:
            break

        speaker_line = len(lines)
        lines.append(f"Speaker {section}")
        marks.append(
            HierarchyMark(
                speaker_line,
                speaker_line,
                1,
                HierarchyType.SPEAKER,
                text=f"Speaker {section}",
                order=order,
            )
        )
        order += 1

        for offset in range(2, 12):
            if len(lines) >= line_count:
                break
            line_no = len(lines)
            lines.append(f"Dialogue line {section}-{offset}")
            marks.append(
                HierarchyMark(
                    line_no,
                    line_no,
                    2,
                    HierarchyType.TEXT,
                    order=order,
                )
            )
            order += 1

    return "\n".join(lines), marks
