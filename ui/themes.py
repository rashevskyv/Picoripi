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
    padding: 5px 14px;
    min-height: 22px;
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
    padding: 0px 4px;
    min-height: 16px;
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
    padding: 4px 8px;
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
    width: 8px;
    margin: 0px;
}
QScrollBar:vertical:hover {
    background: rgba(255, 255, 255, 18);
}
QScrollBar::handle:vertical {
    background: #555555;
    min-height: 28px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #777777;
}
QScrollBar::handle:vertical:pressed {
    background: #8A8A8A;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 8px;
    margin: 0px;
}
QScrollBar:horizontal:hover {
    background: rgba(255, 255, 255, 18);
}
QScrollBar::handle:horizontal {
    background: #555555;
    min-width: 28px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #777777;
}
QScrollBar::handle:horizontal:pressed {
    background: #8A8A8A;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
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
QPushButton {
    background-color: #F8F9FA;
    color: #212529;
    border: 1px solid #CED4DA;
    padding: 5px 14px;
    min-height: 22px;
    border-radius: 3px;
}
QPushButton:hover {
    background-color: #E9ECEF;
    border: 1px solid #ADB5BD;
}
QPushButton:pressed {
    background-color: #DEE2E6;
    border: 1px solid #6C757D;
}
QPushButton:disabled {
    background-color: #E9ECEF;
    color: #888888;
    border: 1px solid #DEE2E6;
}
QPushButton#close_search_panel_button {
    font-weight: bold;
    font-size: 14px;
    padding: 0px 4px;
    min-height: 16px;
}
QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    padding: 4px 8px;
}
QToolButton:hover {
    background-color: #E0E0E0;
    border: 1px solid #CCCCCC;
}
QToolButton:pressed {
    background-color: #D0D0D0;
}
QToolButton:disabled {
    color: #888888;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 8px;
    margin: 0px;
}
QScrollBar:vertical:hover {
    background: rgba(0, 0, 0, 18);
}
QScrollBar::handle:vertical {
    background: #BBBBBB;
    min-height: 28px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #999999;
}
QScrollBar::handle:vertical:pressed {
    background: #7E7E7E;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    border: none;
    background: transparent;
    height: 8px;
    margin: 0px;
}
QScrollBar:horizontal:hover {
    background: rgba(0, 0, 0, 18);
}
QScrollBar::handle:horizontal {
    background: #BBBBBB;
    min-width: 28px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #999999;
}
QScrollBar::handle:horizontal:pressed {
    background: #7E7E7E;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
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
QComboBox, QSpinBox {
    background-color: #FFFFFF;
    color: #000000;
    border: 1px solid #CCCCCC;
    padding: 3px;
    border-radius: 3px;
}
QComboBox:disabled, QSpinBox:disabled {
    background-color: #E1E1E1;
    color: #808080;
    border: 1px solid #C0C0C0;
}
QComboBox::drop-down {
    border: none;
    background-color: #E0E0E0;
}
QComboBox::drop-down:disabled {
    background-color: #D3D3D3;
}
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    color: #000000;
    selection-background-color: #E0E0E0;
    border: 1px solid #CCCCCC;
}
"""
