# --- START OF FILE tests/test_project_dialogs_manual.py ---
# --- START OF FILE test_project_dialogs_manual.py ---
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manual test for project dialogs.
Run this to visually test the dialog UI.

Usage:
    python test_project_dialogs_manual.py
"""

import sys
import io
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt5.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget, QLabel
from components.project_dialogs import NewProjectDialog, OpenProjectDialog, ImportBlockDialog


class TestWindow(QWidget):
    """Main test window with buttons to launch each dialog."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Dialogs Test")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Click buttons to test dialogs:", self)
        title.setStyleSheet("font-weight: bold; font-size: 14pt;")
        layout.addWidget(title)

        # Button: Test New Project Dialog
        btn_new = QPushButton("Test: New Project Dialog", self)
        btn_new.clicked.connect(self.test_new_project_dialog)
        layout.addWidget(btn_new)

        # Button: Test Open Project Dialog
        btn_open = QPushButton("Test: Open Project Dialog", self)
        btn_open.clicked.connect(self.test_open_project_dialog)
        layout.addWidget(btn_open)

        # Button: Test Import Block Dialog
        btn_import = QPushButton("Test: Import Block Dialog", self)
        btn_import.clicked.connect(self.test_import_block_dialog)
        layout.addWidget(btn_import)

        layout.addStretch()

    def test_new_project_dialog(self):
        """Test NewProjectDialog."""
        print("\n=== Testing NewProjectDialog ===")

        # Example plugins data
        available_plugins = {
            "Zelda: Minish Cap": "zelda_mc",
            "Zelda: Wind Waker": "zelda_ww",
            "Pokemon FireRed": "pokemon_fr"
        }

        dialog = NewProjectDialog(self, available_plugins=available_plugins)
        result = dialog.exec_()

        if result == dialog.Accepted:
            info = dialog.get_project_info()
            print("Dialog accepted!")
            print(f"  Name: {info['name']}")
            print(f"  Directory: {info['directory']}")
            print(f"  Plugin: {info['plugin']}")
            print(f"  Description: {info['description']}")
        else:
            print("Dialog cancelled")

    def test_open_project_dialog(self):
        """Test OpenProjectDialog."""
        print("\n=== Testing OpenProjectDialog ===")

        dialog = OpenProjectDialog(self)
        result = dialog.exec_()

        if result == dialog.Accepted:
            path = dialog.get_project_path()
            print("Dialog accepted!")
            print(f"  Project path: {path}")
        else:
            print("Dialog cancelled")

    def test_import_block_dialog(self):
        """Test ImportBlockDialog."""
        print("\n=== Testing ImportBlockDialog ===")

        # For realistic test, could create a mock ProjectManager
        # For now, just test without it
        dialog = ImportBlockDialog(self, project_manager=None)
        result = dialog.exec_()

        if result == dialog.Accepted:
            info = dialog.get_block_info()
            print("Dialog accepted!")
            print(f"  Source file: {info['source_file']}")
            print(f"  Block name: {info['name']}")
            print(f"  Description: {info['description']}")
        else:
            print("Dialog cancelled")


def main():
    print("=" * 60)
    print("Project Dialogs Manual Test")
    print("=" * 60)
    print()
    print("This will open a window with buttons to test each dialog.")
    print("Interact with the dialogs and check the console output.")
    print()

    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
