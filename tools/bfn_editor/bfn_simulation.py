from PyQt6 import QtCore, QtGui, QtWidgets

from tools.bfn_editor.bfn_widgets import SimGlyphItem

class BfnSimMixin:
    def on_sim_text_changed(self):
        if self.sim_input.hasFocus() and hasattr(self, 'chk_sync_sim_text'):
            self.chk_sync_sim_text.setChecked(False)
        self.update_simulation()

    def update_simulation(self):
        if not self.sheet_images:
            return
            
        text = self.sim_input.toPlainText()
        self.sim_scene.clear()
        self.selected_sim_item = None

        if not text:
            return

        # Strip game control tags via the active plugin (same as the preview),
        # so raw {escape:...} tags are not rendered as literal glyphs
        parent_mw = self.parent() if hasattr(self, 'parent') else None
        rules = getattr(parent_mw, 'current_game_rules', None) if parent_mw else None
        if rules is not None and hasattr(rules, 'prepare_preview_glyph_text'):
            try:
                result = rules.prepare_preview_glyph_text(text)
                if isinstance(result, tuple) and result and isinstance(result[0], str):
                    text = result[0]
            except Exception:
                pass
        if not text:
            return

        from core.bfn_core import BfnCore
        # Construct temporary BfnCore to execute layout calculations
        bfn_temp = BfnCore()
        bfn_temp.gly1 = self.metadata.get("GLY1", [])
        bfn_temp.map1 = self.metadata.get("MAP1", [])
        bfn_temp.wid1 = self.metadata.get("WID1", [])
        bfn_temp.inf1 = self.metadata.get("INF1", [])
        
        # Call unified layout engine (using line_spacing=10 like simulator does)
        trans_map = getattr(self, 'translation_map', None)
        glyphs, total_w, total_h = bfn_temp.layout_text(text, translation_map=trans_map, line_spacing=10)
        
        active_idx = self.get_selected_glyph_index()
        
        for g in glyphs:
            if g["is_fallback"]:
                fallback_box = QtWidgets.QGraphicsRectItem(g["draw_x"], g["draw_y"], self.cell_w - 2, self.cell_h - 2)
                fallback_box.setPen(QtGui.QPen(QtGui.QColor('#555558'), 1))
                self.sim_scene.addItem(fallback_box)
                continue
                
            glyph_item = SimGlyphItem(
                glyph_idx=g["glyph_idx"],
                char_str=g["char"],
                sheet_idx=g["sheet_idx"],
                cell_x=g["cell_x"],
                cell_y=g["cell_y"],
                x_offset=g["draw_x"],
                y_offset=g["draw_y"],
                char_pos_idx=g["char_pos_idx"],
                viewer=self
            )
            self.sim_scene.addItem(glyph_item)
            
            if self.selected_char_index == g["char_pos_idx"]:
                self.selected_sim_item = glyph_item
            elif self.selected_char_index == -1 and active_idx == g["glyph_idx"] and self.selected_sim_item is None:
                self.selected_sim_item = glyph_item
                self.selected_char_index = g["char_pos_idx"]
                
        self.sim_scene.setSceneRect(self.sim_scene.itemsBoundingRect())
        
        # Notify Picoripi preview widget to update in real-time
        if hasattr(self, 'parent') and self.parent():
            parent_mw = self.parent()
            if hasattr(parent_mw, 'bfn_preview_widget') and parent_mw.bfn_preview_widget:
                parent_mw.bfn_preview_widget.update()

    def select_sim_glyph(self, item):
        self.selected_sim_item = item
        self.selected_char_index = item.char_pos_idx
        
        rem = item.glyph_idx - self.start_glyph
        sheet_idx = rem // (self.rows * self.cols)
        cell_idx = rem % (self.rows * self.cols)
        
        gx = cell_idx % self.rows
        gy = cell_idx // self.rows
        
        self.set_current_sheet_row(sheet_idx)
        
        self.current_sheet_index = sheet_idx
        self.selected_cell = (gx, gy)
        
        self.display_current_sheet()
        self.populate_info_panel(gx, gy)
        self.update_overlays()
        
        self.sim_scene.update()

    def reposition_simulation_items(self):
        items = [item for item in self.sim_scene.items() if isinstance(item, SimGlyphItem)]
        items.sort(key=lambda x: (x.y_offset, x.char_pos_idx))
        
        wid = self.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        
        current_y = -1
        current_x = 15

        for item in items:
            if current_y == -1 or item.y_offset != current_y:
                current_y = item.y_offset
                current_x = 15

            kerning = 0
            width = self.cell_w
            wid_idx = item.glyph_idx - self.first_code
            if 0 <= wid_idx < len(packets):
                kerning = packets[wid_idx]["kerning"]
                width = packets[wid_idx]["width"]

            # Full cell is drawn shifted left by kerning; cursor advances by width
            item.setPos(current_x - kerning, current_y)
            current_x += width

        self.sim_scene.setSceneRect(self.sim_scene.itemsBoundingRect())

    def show_sim_input_context_menu(self, pos):
        menu = self.sim_input.createStandardContextMenu(pos)
        menu.addSeparator()
        
        eng_menu = menu.addMenu("Insert English Pangram (Риба)...")
        eng_p1 = eng_menu.addAction("The quick brown fox jumps over the lazy dog.")
        eng_p2 = eng_menu.addAction("Jackdaws love my big sphinx of quartz.")
        eng_p3 = eng_menu.addAction("Pack my box with five dozen liquor jugs.")
        
        ukr_menu = menu.addMenu("Вставити українську панграму (Рибу)...")
        ukr_p1 = ukr_menu.addAction("Чуєш їх, доцю, за цими вербами? Женихи приїхали!")
        ukr_p2 = ukr_menu.addAction("Женихи імпортують дешеві хутра, але не знають української фонетики.")
        ukr_p3 = ukr_menu.addAction("Фабрикують дещо за формою, але без глибинного вмісту.")
        ukr_p4 = ukr_menu.addAction("Гей, хлопці, побережіться, якийсь свинячий хвостик в болоті застряг!")
        
        action = menu.exec(self.sim_input.mapToGlobal(pos))
        if action:
            if action in [eng_p1, eng_p2, eng_p3, ukr_p1, ukr_p2, ukr_p3, ukr_p4]:
                if hasattr(self, 'chk_sync_sim_text'):
                    self.chk_sync_sim_text.setChecked(False)
                self.sim_input.setPlainText(action.text())
