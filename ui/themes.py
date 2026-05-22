# --- START OF FILE ui/themes.py ---
DARK_THEME_STYLESHEET = """
QWidget {
    background-color: #2E2E2E;
    color: #E0E0E0;
    border: 0px;
}
QMainWindow, QDialog, QStatusBar {
    background-color: #2E2E2E;
}
QMenuBar {
    background-color: #383838;
    color: #E0E0E0;
}
QMenuBar::item:selected {
    background-color: #505050;
}
QMenuBar::item:disabled {
    color: #707070;
}
QMenu {
    background-color: #383838;
    color: #E0E0E0;
    border: 1px solid #505050;
}
QMenu::item:selected {
    background-color: #505050;
}
QMenu::item:disabled {
    color: #707070;
}
QPlainTextEdit, QTextEdit {
    background-color: #252525;
    color: #E0E0E0;
    border: 1px solid #505050;
    selection-background-color: #005A9E;
    selection-color: #FFFFFF;
}
QListWidget {
    background-color: #252525;
    color: #E0E0E0;
    border: 1px solid #505050;
    selection-color: #FFFFFF;
}
QListWidget::item:selected {
    background-color: #004A7E;
    color: #FFFFFF;
}
QLineEdit#PathLineEdit {
    background-color: #252525;
    border: 1px solid #5A5A5A;
    padding: 2px;
    color: #E0E0E0;
}
QPushButton {
    background-color: #4A4A4A;
    color: #E0E0E0;
    border: 1px solid #5A5A5A;
    padding: 5px;
    border-radius: 3px;
}
QPushButton:hover {
    background-color: #5A5A5A;
}
QPushButton:pressed {
    background-color: #3A3A3A;
}
QPushButton:disabled {
    background-color: #353535;
    color: #707070;
    border: 1px solid #444444;
}
QPushButton#close_search_panel_button {
    font-weight: bold;
    font-size: 14px;
    padding: 0px;
}
QComboBox {
    background-color: #383838;
    color: #E0E0E0;
    border: 1px solid #5A5A5A;
    padding: 3px;
    border-radius: 3px;
}
QComboBox::drop-down {
    border: none;
    background-color: #4A4A4A;
}
QComboBox QAbstractItemView {
    background-color: #383838;
    color: #E0E0E0;
    selection-background-color: #505050;
    border: 1px solid #5A5A5A;
}
QCheckBox, QLabel {
    color: #E0E0E0;
}
QSpinBox {
    background-color: #383838;
    color: #E0E0E0;
    border: 1px solid #5A5A5A;
    padding: 3px;
    border-radius: 3px;
}
QToolBar {
    background-color: #383838;
    border: none;
    spacing: 5px;
}
QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    padding: 4px;
}
QToolButton:hover {
    background-color: #5A5A5A;
    border: 1px solid #5A5A5A;
}
QToolButton:pressed {
    background-color: #3A3A3A;
}
QToolButton:disabled {
    color: #707070;
}
QSplitter::handle {
    background-color: #383838;
}
QSplitter::handle:hover {
    background-color: #505050;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #555555;
    min-height: 25px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #777777;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 10px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #555555;
    min-width: 25px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #777777;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
    width: 0px;
}
QTabWidget::pane {
    border: 1px solid #505050;
    top: -1px; 
    background-color: #2E2E2E;
}
QTabBar::tab {
    background-color: #383838;
    color: #B0B0B0;
    border: 1px solid #505050;
    border-bottom-color: #505050; 
    padding: 5px 10px;
    margin-right: -1px;
}
QTabBar::tab:selected {
    background-color: #2E2E2E;
    color: #FFFFFF;
    border-bottom-color: #2E2E2E;
}
QTabBar::tab:!selected:hover {
    background-color: #4A4A4A;
}
"""

LIGHT_THEME_STYLESHEET = """
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #BBBBBB;
    min-height: 25px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #999999;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 10px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #BBBBBB;
    min-width: 25px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #999999;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
    width: 0px;
}
QMenuBar {
    background-color: #F0F0F0;
    color: #000000;
}
QMenuBar::item:selected {
    background-color: #E0E0E0;
}
QMenuBar::item:disabled {
    color: #888888;
}
QMenu {
    background-color: #F0F0F0;
    color: #000000;
    border: 1px solid #CCCCCC;
}
QMenu::item:selected {
    background-color: #E0E0E0;
    color: #000000;
}
QMenu::item:disabled {
    color: #888888;
}
"""