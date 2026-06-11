import pytest
from PyQt6.QtWidgets import QApplication
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
