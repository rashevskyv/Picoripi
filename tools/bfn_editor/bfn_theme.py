from PyQt5 import QtCore, QtGui, QtWidgets

def apply_premium_dark_theme(widget):
    dark_palette = QtGui.QPalette()
    dark_palette.setColor(QtGui.QPalette.Window, QtGui.QColor('#1e1e24'))
    dark_palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor('#f8f9fa'))
    dark_palette.setColor(QtGui.QPalette.Base, QtGui.QColor('#141419'))
    dark_palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor('#1e1e24'))
    dark_palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor('#f8f9fa'))
    dark_palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor('#1e1e24'))
    dark_palette.setColor(QtGui.QPalette.Text, QtGui.QColor('#f8f9fa'))
    dark_palette.setColor(QtGui.QPalette.Button, QtGui.QColor('#2b2d42'))
    dark_palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor('#f8f9fa'))
    dark_palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor('#e63946'))
    dark_palette.setColor(QtGui.QPalette.Link, QtGui.QColor('#00b4d8'))
    dark_palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor('#00b4d8'))
    dark_palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor('#1e1e24'))
    widget.setPalette(dark_palette)
    
    widget.setStyleSheet("""
        QMainWindow, QDialog, QMessageBox {
            background-color: #1e1e24;
            color: #f8f9fa;
        }
        QMessageBox QLabel {
            color: #f8f9fa;
        }
        QPushButton {
            background-color: #2b2d42;
            border: 1px solid #3d405b;
            border-radius: 4px;
            padding: 6px;
            color: #f8f9fa;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #3d405b;
            border-color: #00b4d8;
        }
        QPushButton:pressed {
            background-color: #00b4d8;
            color: #141419;
        }
        QPushButton:disabled {
            background-color: #141419;
            color: #555558;
            border-color: #222225;
        }
        QListWidget {
            background-color: #141419;
            border: 1px solid #2b2d42;
            border-radius: 4px;
            padding: 4px;
        }
        QListWidget::item:selected {
            background-color: #00b4d8;
            color: #141419;
            font-weight: bold;
            border-radius: 2px;
        }
        QSpinBox, QDoubleSpinBox {
            background-color: #141419;
            border: 1px solid #2b2d42;
            border-radius: 4px;
            padding: 4px;
            color: #f8f9fa;
        }
        QSpinBox:focus, QDoubleSpinBox:focus {
            border-color: #00b4d8;
        }
        QTextEdit {
            background-color: #141419;
            border: 1px solid #2b2d42;
            border-radius: 4px;
            color: #f8f9fa;
        }
        QScrollBar:vertical {
            border: none;
            background: #141419;
            width: 10px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: #2b2d42;
            min-height: 20px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical:hover {
            background: #00b4d8;
        }
        QScrollBar:horizontal {
            border: none;
            background: #141419;
            height: 10px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:horizontal {
            background: #2b2d42;
            min-width: 20px;
            border-radius: 5px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #00b4d8;
        }
        QTabWidget::pane {
            border: 1px solid #2b2d42;
            background-color: #1e1e24;
            border-radius: 4px;
            top: -1px;
        }
        QTabBar::tab {
            background-color: #141419;
            color: #f8f9fa;
            border: 1px solid #2b2d42;
            border-bottom: 1px solid #2b2d42;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 8px 16px;
            margin-right: 2px;
        }
        QTabBar::tab:hover {
            background-color: #2b2d42;
            border-color: #00b4d8;
        }
        QTabBar::tab:selected {
            background-color: #1e1e24;
            color: #00b4d8;
            border-bottom: 1px solid #1e1e24;
        }
        QTableWidget {
            background-color: #141419;
            color: #f8f9fa;
            gridline-color: #2b2d42;
            border: 1px solid #2b2d42;
            border-radius: 4px;
        }
        QTableWidget::item:selected {
            background-color: #00b4d8;
            color: #141419;
            font-weight: bold;
        }
        QHeaderView::section {
            background-color: #2b2d42;
            color: #f8f9fa;
            padding: 6px 12px;
            border: 1px solid #1e1e24;
            font-weight: bold;
        }
        QLineEdit {
            background-color: #141419;
            border: 1px solid #2b2d42;
            border-radius: 4px;
            padding: 6px;
            color: #f8f9fa;
        }
        QLineEdit:focus {
            border-color: #00b4d8;
        }
        QMenu {
            background-color: #1e1e24;
            color: #f8f9fa;
            border: 1px solid #2b2d42;
            border-radius: 4px;
            padding: 4px;
        }
        QMenu::item {
            background-color: transparent;
            padding: 6px 24px 6px 20px;
            border-radius: 2px;
            color: #f8f9fa;
        }
        QMenu::item:selected {
            background-color: #00b4d8;
            color: #141419;
            font-weight: bold;
        }
        QMenu::item:disabled {
            color: #555558;
        }
        QMenu::separator {
            height: 1px;
            background-color: #2b2d42;
            margin: 4px 0px;
        }
    """)

def apply_premium_light_theme(widget):
    light_palette = QtGui.QPalette()
    light_palette.setColor(QtGui.QPalette.Window, QtGui.QColor('#f4f5f7'))
    light_palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor('#1e1e24'))
    light_palette.setColor(QtGui.QPalette.Base, QtGui.QColor('#ffffff'))
    light_palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor('#e9ecef'))
    light_palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor('#1e1e24'))
    light_palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor('#ffffff'))
    light_palette.setColor(QtGui.QPalette.Text, QtGui.QColor('#1e1e24'))
    light_palette.setColor(QtGui.QPalette.Button, QtGui.QColor('#e2e4e9'))
    light_palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor('#1e1e24'))
    light_palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor('#d90429'))
    light_palette.setColor(QtGui.QPalette.Link, QtGui.QColor('#0077b6'))
    light_palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor('#0077b6'))
    light_palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor('#ffffff'))
    widget.setPalette(light_palette)
    
    widget.setStyleSheet("""
        QMainWindow, QDialog, QMessageBox {
            background-color: #f4f5f7;
            color: #1e1e24;
        }
        QMessageBox QLabel {
            color: #1e1e24;
        }
        QPushButton {
            background-color: #e2e4e9;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 6px;
            color: #1e1e24;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #cbd5e1;
            border-color: #0077b6;
        }
        QPushButton:pressed {
            background-color: #0077b6;
            color: #ffffff;
        }
        QPushButton:disabled {
            background-color: #e9ecef;
            color: #94a3b8;
            border-color: #e2e4e9;
        }
        QListWidget {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 4px;
            color: #1e1e24;
        }
        QListWidget::item:selected {
            background-color: #0077b6;
            color: #ffffff;
            font-weight: bold;
            border-radius: 2px;
        }
        QSpinBox, QDoubleSpinBox {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 4px;
            color: #1e1e24;
        }
        QSpinBox:focus, QDoubleSpinBox:focus {
            border-color: #0077b6;
        }
        QTextEdit {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            color: #1e1e24;
        }
        QScrollBar:vertical {
            border: none;
            background: #f4f5f7;
            width: 10px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: #cbd5e1;
            min-height: 20px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical:hover {
            background: #0077b6;
        }
        QScrollBar:horizontal {
            border: none;
            background: #f4f5f7;
            height: 10px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:horizontal {
            background: #cbd5e1;
            min-width: 20px;
            border-radius: 5px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #0077b6;
        }
        QTabWidget::pane {
            border: 1px solid #cbd5e1;
            background-color: #f4f5f7;
            border-radius: 4px;
            top: -1px;
        }
        QTabBar::tab {
            background-color: #e9ecef;
            color: #1e1e24;
            border: 1px solid #cbd5e1;
            border-bottom: 1px solid #cbd5e1;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 8px 16px;
            margin-right: 2px;
        }
        QTabBar::tab:hover {
            background-color: #cbd5e1;
            border-color: #0077b6;
        }
        QTabBar::tab:selected {
            background-color: #f4f5f7;
            color: #0077b6;
            border-bottom: 1px solid #f4f5f7;
        }
        QTableWidget {
            background-color: #ffffff;
            color: #1e1e24;
            gridline-color: #cbd5e1;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
        }
        QTableWidget::item:selected {
            background-color: #0077b6;
            color: #ffffff;
            font-weight: bold;
        }
        QHeaderView::section {
            background-color: #e2e4e9;
            color: #1e1e24;
            padding: 6px 12px;
            border: 1px solid #cbd5e1;
            font-weight: bold;
        }
        QLineEdit {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 6px;
            color: #1e1e24;
        }
        QLineEdit:focus {
            border-color: #0077b6;
        }
        QMenu {
            background-color: #ffffff;
            color: #1e1e24;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 4px;
        }
        QMenu::item {
            background-color: transparent;
            padding: 6px 24px 6px 20px;
            border-radius: 2px;
            color: #1e1e24;
        }
        QMenu::item:selected {
            background-color: #0077b6;
            color: #ffffff;
            font-weight: bold;
        }
        QMenu::item:disabled {
            color: #94a3b8;
        }
        QMenu::separator {
            height: 1px;
            background-color: #cbd5e1;
            margin: 4px 0px;
        }
    """)

def apply_theme_by_settings(widget):
    import json
    import os
    theme_name = "auto"
    try:
        if os.path.exists("settings.json"):
            with open("settings.json", "r", encoding="utf-8") as f:
                settings = json.load(f)
                theme_name = settings.get("theme", "auto")
    except Exception as e:
        print(f"Error reading settings.json for BFN editor theme: {e}")

    if theme_name == "dark":
        apply_premium_dark_theme(widget)
        return True
    else:
        apply_premium_light_theme(widget)
        return False

