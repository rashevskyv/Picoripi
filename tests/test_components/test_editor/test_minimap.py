from PyQt6.QtWidgets import QApplication

from components.editor.line_numbered_text_edit import LineNumberedTextEdit
from components.editor.minimap import TextMinimap


def _make_editor_with_text(qapp, *, enable_minimap=True):
    editor = LineNumberedTextEdit(None)
    editor.show_minimap = enable_minimap
    editor.resize(520, 360)
    editor.setPlainText("\n".join(f"Line {i} with some text" for i in range(120)))
    editor.show()
    QApplication.processEvents()
    editor.updateLineNumberAreaWidth(0)
    return editor


def test_line_numbered_editor_minimap_is_opt_in_by_default(qapp):
    editor = _make_editor_with_text(qapp, enable_minimap=False)

    assert editor.minimapAreaWidth() == 0
    assert editor.viewportMargins().right() == 0
    assert not editor.minimap.isVisible()


def test_minimap_reserves_right_margin_when_editor_is_wide(qapp):
    editor = _make_editor_with_text(qapp)

    assert editor.minimapAreaWidth() == TextMinimap.WIDTH
    assert editor.viewportMargins().right() == TextMinimap.WIDTH
    assert editor.minimap.isVisible()


def test_minimap_hides_when_editor_is_narrow(qapp):
    editor = _make_editor_with_text(qapp)
    editor.resize(TextMinimap.MIN_EDITOR_WIDTH - 20, 360)
    QApplication.processEvents()
    editor.updateLineNumberAreaWidth(0)

    assert editor.minimapAreaWidth() == 0
    assert editor.viewportMargins().right() == 0
    assert not editor.minimap.isVisible()


def test_minimap_scroll_mapping_can_jump_to_bottom(qapp):
    editor = _make_editor_with_text(qapp)
    bar = editor.verticalScrollBar()
    assert bar.maximum() > 0

    editor.minimap._set_scroll_from_handle_top(editor.minimap.height())

    assert bar.value() == bar.maximum()


def test_minimap_sits_before_vertical_scrollbar(qapp):
    editor = _make_editor_with_text(qapp)
    bar = editor.verticalScrollBar()
    QApplication.processEvents()

    if bar.isVisible():
        bar_left = bar.mapTo(editor, bar.rect().topLeft()).x()
        assert editor.minimap.geometry().right() < bar_left


def test_minimap_reuses_cached_document_map_while_scrolling(qapp):
    editor = _make_editor_with_text(qapp)
    bar = editor.verticalScrollBar()

    editor.minimap._ensure_map_cache()
    first_cache = editor.minimap._map_cache
    assert first_cache is not None

    bar.setValue(min(bar.maximum(), bar.value() + 20))
    editor.minimap._ensure_map_cache()

    assert editor.minimap._map_cache is first_cache

    editor.minimap.invalidate()
    editor.minimap._ensure_map_cache()

    assert editor.minimap._map_cache is not first_cache


def test_minimap_text_changes_are_debounced(qapp):
    editor = _make_editor_with_text(qapp)
    editor.minimap._ensure_map_cache()
    first_cache = editor.minimap._map_cache

    editor.setPlainText("\n".join(f"Edited line {i}" for i in range(120)))
    editor.minimap._ensure_map_cache()

    assert editor.minimap._content_dirty is True
    assert editor.minimap._map_cache is first_cache

    editor.minimap.invalidate()
    editor.minimap._ensure_map_cache()

    assert editor.minimap._content_dirty is False
    assert editor.minimap._map_cache is not first_cache


def test_minimap_samples_large_documents_by_visible_height(qapp):
    editor = _make_editor_with_text(qapp)
    editor.setPlainText("\n".join(f"Long document line {i}" for i in range(5000)))
    editor.minimap.resize(TextMinimap.WIDTH, 200)

    sampled_blocks = list(editor.minimap._iter_sampled_blocks(editor.document()))

    assert len(sampled_blocks) < editor.document().blockCount()
    assert len(sampled_blocks) <= editor.minimap.height() * 3
