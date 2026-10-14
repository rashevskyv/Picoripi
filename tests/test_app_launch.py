from main import MainWindow

def test_app_launch(qtbot):
    """Smoke test to verify that MainWindow launches, renders and closes without crashes."""
    mw = MainWindow()
    mw.is_testing = True
    qtbot.addWidget(mw)
    mw.show()
    # Wait for the widget to be visible
    qtbot.waitExposed(mw)
    assert mw.isVisible()
    mw.close()


def test_qt_message_handler(capsys):
    from main import qt_message_handler
    from PyQt6.QtCore import QtMsgType
    
    # Test case 1: Message contains GetDesignGlyphMetrics failed -> should be ignored (no output to stderr)
    qt_message_handler(QtMsgType.QtWarningMsg, None, "QWindowsFontEngineDirectWrite::recalcAdvances: GetDesignGlyphMetrics failed (The operation completed successfully.)")
    captured = capsys.readouterr()
    assert captured.err == ""
    
    # Test case 2: Normal Qt warning -> should be written to stderr
    qt_message_handler(QtMsgType.QtWarningMsg, None, "Some other warning message")
    captured = capsys.readouterr()
    assert "Some other warning message" in captured.err



def test_closing_the_project_manager_with_no_project_closes_the_main_window(qtbot):
    """The start-up path: the manager opens with no project; closing it goes through the main window's close."""
    mw = MainWindow()
    mw.is_testing = True
    qtbot.addWidget(mw)
    mw.show()
    qtbot.waitExposed(mw)
    mw.project_action_handler.open_project_manager_if_none()
    dialog = mw.project_manager_dialog
    qtbot.waitUntil(lambda: dialog.isVisible(), timeout=5000)

    dialog.close()

    qtbot.waitUntil(lambda: not mw.isVisible(), timeout=5000)
    assert not dialog.isVisible()
