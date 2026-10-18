"""Subprocess probe for the first start: no QApplication exists, no data folder is chosen yet, the chooser is built.

Run by test_data_location_dialog.py. The dialog never opens (exec is replaced); only its construction matters, because
Qt aborts the process when a widget is built without a live QApplication.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PyQt6.QtWidgets import QApplication, QDialog

from dialogs import data_location_dialog as dld
from utils import app_mode

app_mode.headless = False
dld.resolve_data_location = lambda: SimpleNamespace(needs_choice=True, problem=None, path=None)
dld.DataLocationDialog.exec = lambda self: QDialog.DialogCode.Accepted.value
assert QApplication.instance() is None
print("RESULT", dld.ensure_data_location_chosen(), QApplication.instance() is not None)
