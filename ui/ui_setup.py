from PyQt6.QtGui import QIcon
from pathlib import Path
from ui.builders.layout_builder import LayoutBuilder
from ui.builders.statusbar_builder import StatusBarBuilder
from ui.builders.menu_builder import MenuBuilder
from ui.builders.toolbar_builder import ToolBarBuilder
from core.i18n import tr

def setup_main_window_ui(main_window):
    """
    Sets up the main window UI by delegating to specialized builders.
    This replaces the monolithic 470-line setup function.
    """
    # 1. Basic Window Setup
    main_window.setWindowTitle(tr('Picoripi'))
    icon_path = Path("assets/icon.ico")
    if icon_path.exists():
        main_window.setWindowIcon(QIcon(str(icon_path)))

    # 2. Build Layout (Splitters, Panels, Editors)
    layout_builder = LayoutBuilder(main_window)
    layout_builder.build()

    # 3. Build Status Bar
    statusbar_builder = StatusBarBuilder(main_window)
    statusbar_builder.build()

    # 4. Build Menus
    menu_builder = MenuBuilder(main_window)
    menu_builder.build_all()

    # 5. Build ToolBar
    toolbar_builder = ToolBarBuilder(main_window)
    toolbar_builder.build()
