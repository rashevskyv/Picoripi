from PyQt5.QtWidgets import QMenu, QStyle, QMainWindow
from PyQt5.QtGui import QIcon

def prettify_standard_context_menu(menu: QMenu, style: QStyle):
    """
    Finds standard actions like Undo, Redo, Cut, Copy, Paste, etc. 
    in a QMenu and assigns them standard icons from QStyle if they are missing.
    """
    # Mapping common action names to icons
    icon_map = {
        "Undo": QStyle.SP_ArrowBack,
        "Redo": QStyle.SP_ArrowForward,
        "Cut": None, # No good SP for Cut
        "Copy": QStyle.SP_FileIcon,
        "Paste": QStyle.SP_DialogOpenButton,
        "Delete": QStyle.SP_TrashIcon,
        "Select All": QStyle.SP_DialogApplyButton,
    }
    
    for action in menu.actions():
        if action.isSeparator() or not action.text():
            continue
        
        # Action text might have accelerators like "&Copy"
        clean_text = action.text().replace("&", "")
        for key, sp_code in icon_map.items():
            if key in clean_text and sp_code is not None:
                if action.icon().isNull(): # Only set if it doesn't have an icon yet
                     action.setIcon(style.standardIcon(sp_code))
                break
