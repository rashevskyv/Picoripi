from PyQt6 import QtCore

from core.i18n import tr
from tools.bfn_editor.window_tree_mixin import ROLE_SHEET_IDX


class WindowSyncMixin:
    def get_settings_manager(self):
        curr = self.parent()
        while curr:
            if hasattr(curr, "settings_manager") and curr.settings_manager:
                return curr.settings_manager
            curr = curr.parent()
        
        from PyQt6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if hasattr(w, "settings_manager") and w.settings_manager:
                return w.settings_manager
        return None

    def save_column_widths(self):
        sm = self.get_settings_manager()
        if sm:
            widths = []
            for col in range(self.table_glyphs.columnCount()):
                widths.append(self.table_glyphs.columnWidth(col))
            sm.set("bfn_glyph_table_column_widths", widths)
            if hasattr(sm.mw, "bfn_glyph_table_column_widths"):
                sm.mw.bfn_glyph_table_column_widths = widths
            sm.save_settings()

    def showEvent(self, event):
        super().showEvent(event)
        self.scan_fonts_directories()
        sheet_count = len(self.sheet_images)
        self.rebuild_tree_widget(sheet_count)
        
        if self.current_bfn_name:
            self.set_current_sheet_row(self.current_sheet_index if self.current_sheet_index >= 0 else 0)
        else:
            # Standalone mode: auto-select first sheet of first font to avoid empty table
            def find_first_sheet(parent_item):
                if parent_item.data(0, ROLE_SHEET_IDX) is not None:
                    return parent_item
                for i in range(parent_item.childCount()):
                    res = find_first_sheet(parent_item.child(i))
                    if res:
                        return res
                return None
                
            first_sheet = None
            for i in range(self.list_sheets.topLevelItemCount()):
                first_sheet = find_first_sheet(self.list_sheets.topLevelItem(i))
                if first_sheet:
                    break
            if first_sheet:
                self.list_sheets.setCurrentItem(first_sheet)

    def on_auto_sync_toggled(self, state):
        is_checked = (state == QtCore.Qt.CheckState.Checked)
        sm = self.get_settings_manager()
        if sm:
            sm.set("bfn_auto_sync_enabled", is_checked)
            sm.save_settings()
            
        if is_checked and self._dirty:
            self.schedule_auto_sync()

    def schedule_auto_sync(self):
        self.auto_sync_timer.start(300)

    def auto_sync_and_recalculate(self):
        if self._dirty:
            self.save_changes(silent=True)

    def force_sync_and_recalculate(self):
        self.save_changes(silent=True)
        if not self._dirty and self.font_sync_callback:
            try:
                self.font_sync_callback()
            except Exception:
                pass
        self.status.showMessage(tr("Force recalculation complete. Picoripi widths updated."))

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.close()
            event.accept()
        else:
            super().keyPressEvent(event)
