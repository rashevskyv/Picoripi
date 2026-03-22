import sys
from PyQt5.QtWidgets import QApplication
from unittest.mock import MagicMock
from plugins.zelda_mc.rules import GameRules

app = QApplication(sys.argv)
mw = MagicMock()
mw.show_multiple_spaces_as_dots = False
mw.default_tag_mappings = {}
mw.newline_display_symbol = "↵"
try:
    print("creating rules")
    r = GameRules(mw)
    print("success")
except Exception as e:
    import traceback
    traceback.print_exc()
