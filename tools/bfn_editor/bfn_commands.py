from PyQt5 import QtCore, QtGui, QtWidgets

class EditMetricsCommand(QtWidgets.QUndoCommand):
    def __init__(self, viewer, glyph_idx, old_kern, new_kern, old_width, new_width, description="Edit Metrics"):
        super().__init__(description)
        self.viewer = viewer
        self.glyph_idx = int(glyph_idx)
        self.old_kern = int(old_kern)
        self.new_kern = int(new_kern)
        self.old_width = int(old_width)
        self.new_width = int(new_width)

    def undo(self):
        wid = self.viewer.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        wid_idx = self.glyph_idx - self.viewer.first_code
        if 0 <= wid_idx < len(packets):
            packets[wid_idx]["kerning"] = self.old_kern
            packets[wid_idx]["width"] = self.old_width
        
        if self.viewer.get_selected_glyph_index() == self.glyph_idx:
            self.viewer.spin_kerning.blockSignals(True)
            self.viewer.spin_width.blockSignals(True)
            self.viewer.spin_kerning.setValue(self.old_kern)
            self.viewer.spin_width.setValue(self.old_width)
            self.viewer.spin_kerning.blockSignals(False)
            self.viewer.spin_width.blockSignals(False)
            self.viewer.update_overlays()
            
        QtCore.QTimer.singleShot(0, self.viewer.update_simulation)
        self.viewer.refresh_table_row(self.glyph_idx)

    def redo(self):
        wid = self.viewer.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        wid_idx = self.glyph_idx - self.viewer.first_code
        if 0 <= wid_idx < len(packets):
            packets[wid_idx]["kerning"] = self.new_kern
            packets[wid_idx]["width"] = self.new_width
            
        if self.viewer.get_selected_glyph_index() == self.glyph_idx:
            self.viewer.spin_kerning.blockSignals(True)
            self.viewer.spin_width.blockSignals(True)
            self.viewer.spin_kerning.setValue(self.new_kern)
            self.viewer.spin_width.setValue(self.new_width)
            self.viewer.spin_kerning.blockSignals(False)
            self.viewer.spin_width.blockSignals(False)
            self.viewer.update_overlays()
            
        QtCore.QTimer.singleShot(0, self.viewer.update_simulation)
        self.viewer.refresh_table_row(self.glyph_idx)

    def id(self):
        return 1234

    def mergeWith(self, other):
        if other.id() != self.id() or other.glyph_idx != self.glyph_idx:
            return False
        self.new_kern = other.new_kern
        self.new_width = other.new_width
        return True


class EditMapCommand(QtWidgets.QUndoCommand):
    def __init__(self, viewer, glyph_idx, old_code, new_code, description="Edit Character Mapping"):
        super().__init__(description)
        self.viewer = viewer
        self.glyph_idx = int(glyph_idx)
        self.old_code = int(old_code)
        self.new_code = int(new_code)

    def undo(self):
        self.viewer.update_char_mapping(self.glyph_idx, self.old_code)
        if self.viewer.get_selected_glyph_index() == self.glyph_idx:
            self.viewer.populate_info_panel(*self.viewer.selected_cell)
        self.viewer.update_simulation()
        self.viewer.refresh_table_row(self.glyph_idx)

    def redo(self):
        self.viewer.update_char_mapping(self.glyph_idx, self.new_code)
        if self.viewer.get_selected_glyph_index() == self.glyph_idx:
            self.viewer.populate_info_panel(*self.viewer.selected_cell)
        self.viewer.update_simulation()
        self.viewer.refresh_table_row(self.glyph_idx)


class BatchMappingCommand(QtWidgets.QUndoCommand):
    def __init__(self, viewer, changes, description="Modify Mappings"):
        super().__init__(description)
        self.viewer = viewer
        self.changes = changes

    def undo(self):
        for glyph_idx, old_code, _ in self.changes:
            self.viewer.update_char_mapping(glyph_idx, old_code)
            
        if self.viewer.selected_cell:
            self.viewer.populate_info_panel(*self.viewer.selected_cell)
        self.viewer.update_simulation()
        self.viewer.populate_glyph_table()

    def redo(self):
        for glyph_idx, _, new_code in self.changes:
            self.viewer.update_char_mapping(glyph_idx, new_code)
            
        if self.viewer.selected_cell:
            self.viewer.populate_info_panel(*self.viewer.selected_cell)
        self.viewer.update_simulation()
        self.viewer.populate_glyph_table()


class ImportSheetCommand(QtWidgets.QUndoCommand):
    def __init__(self, viewer, sheet_idx, old_img, new_img, description="Import Sheet PNG"):
        super().__init__(description)
        self.viewer = viewer
        self.sheet_idx = int(sheet_idx)
        self.old_img = old_img.copy()
        self.new_img = new_img.copy()

    def undo(self):
        self.viewer.sheet_images[self.sheet_idx] = self.old_img.copy()
        if self.viewer.current_sheet_index == self.sheet_idx:
            self.viewer.display_current_sheet()
        self.viewer.update_simulation()
        self.viewer.populate_glyph_table()

    def redo(self):
        self.viewer.sheet_images[self.sheet_idx] = self.new_img.copy()
        if self.viewer.current_sheet_index == self.sheet_idx:
            self.viewer.display_current_sheet()
        self.viewer.update_simulation()
        self.viewer.populate_glyph_table()


class ImportGlyphCommand(QtWidgets.QUndoCommand):
    def __init__(self, viewer, sheet_idx, cell_x, cell_y, old_glyph_img, new_glyph_img, description="Import Glyph PNG"):
        super().__init__(description)
        self.viewer = viewer
        self.sheet_idx = int(sheet_idx)
        self.cell_x = int(cell_x)
        self.cell_y = int(cell_y)
        self.old_glyph_img = old_glyph_img.copy()
        self.new_glyph_img = new_glyph_img.copy()

    def undo(self):
        sheet_qimg = self.viewer.sheet_images[self.sheet_idx]
        painter = QtGui.QPainter(sheet_qimg)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_Source)
        painter.drawImage(self.cell_x, self.cell_y, self.old_glyph_img)
        painter.end()
        
        if self.viewer.current_sheet_index == self.sheet_idx:
            self.viewer.display_current_sheet()
        self.viewer.update_simulation()
        self.viewer.populate_glyph_table()

    def redo(self):
        sheet_qimg = self.viewer.sheet_images[self.sheet_idx]
        painter = QtGui.QPainter(sheet_qimg)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_Source)
        painter.drawImage(self.cell_x, self.cell_y, self.new_glyph_img)
        painter.end()
        
        if self.viewer.current_sheet_index == self.sheet_idx:
            self.viewer.display_current_sheet()
        self.viewer.update_simulation()
        self.viewer.populate_glyph_table()
