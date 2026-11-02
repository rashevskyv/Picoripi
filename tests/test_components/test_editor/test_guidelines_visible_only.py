from PyQt6.QtWidgets import QApplication

from components.editor.line_numbered_text_edit import LineNumberedTextEdit


def test_recalculate_guidelines_measures_only_the_visible_lines(qapp):
    editor = LineNumberedTextEdit(None)
    editor.resize(520, 300)
    editor.setPlainText("\n".join(f"Line {i} with some text" for i in range(3000)))
    editor.show()
    QApplication.processEvents()

    editor.recalculate_guidelines()

    measured = {block for block, _line in editor.guideline_positions}
    first = editor.firstVisibleBlock().blockNumber()
    assert first in measured
    # A 300 px viewport shows a few dozen lines: the other ~3000 wait for the paint to scroll them in.
    assert 0 < len(measured) < 100
