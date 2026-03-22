import os
import sys
sys.path.insert(0, os.path.abspath("."))
from unittest.mock import MagicMock
from core.data_state_processor import DataStateProcessor

mw = MagicMock()
mw.data = [["original"]]
mw.edited_file_data = None
mw.edited_json_path = "test_edited.json"
mw.json_path = "test.json"
mw.current_game_rules = MagicMock()
mw.current_game_rules.save_data_to_json_obj.return_value = {"saved": "data"}
mw.block_names = {}
mw.unsaved_changes = True
mw.edited_sublines = []

mock_pm = MagicMock()
mock_pm.project = MagicMock()
mock_block = MagicMock()
mock_block.translation_file = "trans.json"
mock_pm.project.blocks = [mock_block]
mock_pm.get_absolute_path.return_value = "abs/trans.json"

mw.project_manager = mock_pm
mw.block_to_project_file_map = {0: 0} # data block 0 -> project block 0
mw.edited_data = {(0, 0): "project_edit"}

dsp = DataStateProcessor(mw)

def proxy_msg_box(*args, **kwargs):
    print(f"QMessageBox called: {args}")
    return 16384 # QMessageBox.Yes

import core.data_state_processor
core.data_state_processor.QMessageBox.question = proxy_msg_box
core.data_state_processor.QMessageBox.warning = proxy_msg_box
core.data_state_processor.QMessageBox.critical = proxy_msg_box
core.data_state_processor.QMessageBox.information = proxy_msg_box

def proxy_save(*args, **kwargs):
    print("SAVE JSON CALLED:", args)
    return True
core.data_state_processor.save_json_file = proxy_save

try:
    res = dsp.save_current_edits(ask_confirmation=False)
    print("SAVE RES:", res)
except Exception as e:
    print("EXCEPTION:", e)
