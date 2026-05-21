from PyQt5 import QtCore, QtGui, QtWidgets

from tools.bfn_editor.bfn_widgets import SimGlyphItem

class BfnSimMixin:
    def update_simulation(self):
        if not self.sheet_images:
            return
            
        text = self.sim_input.toPlainText()
        self.sim_scene.clear()
        self.selected_sim_item = None
        
        if not text:
            return
            
        char_to_glyph = {}
        maps = self.metadata.get("MAP1", [])
        for m in maps:
            m_type = m.get("mapping_type", 0)
            m_first = m.get("first_char", 0)
            m_last = m.get("last_char", 0)
            entries = m.get("entries", [])
            
            if m_type == 0:
                for idx in range(m_first, m_last + 1):
                    try:
                        char_to_glyph[chr(idx)] = idx
                    except Exception:
                        pass
            elif m_type == 2:
                for idx, code in enumerate(entries):
                    try:
                        char_to_glyph[chr(code)] = idx
                    except Exception:
                        pass
            elif m_type == 3:
                half = len(entries) // 2
                for k in range(half):
                    code = entries[k]
                    g_idx = entries[half + k]
                    try:
                        char_to_glyph[chr(code)] = g_idx
                    except Exception:
                        pass
                        
        wid = self.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        
        current_y = 15
        lines = text.split('\n')
        
        active_idx = self.get_selected_glyph_index()
        char_pos_idx = 0
        
        for line in lines:
            current_x = 15
            for char in line:
                if char == ' ':
                    current_x += self.cell_w // 2
                    continue
                elif char == '\t':
                    current_x += self.cell_w * 2
                    continue
                    
                glyph_idx = char_to_glyph.get(char, -1)
                if glyph_idx == -1 or glyph_idx > self.end_glyph:
                    fallback_box = QtWidgets.QGraphicsRectItem(current_x, current_y, self.cell_w - 2, self.cell_h - 2)
                    fallback_box.setPen(QtGui.QPen(QtGui.QColor('#555558'), 1))
                    self.sim_scene.addItem(fallback_box)
                    current_x += self.cell_w // 2
                    continue
                    
                rem = glyph_idx - self.start_glyph
                sheet_idx = rem // (self.rows * self.cols)
                cell_idx = rem % (self.rows * self.cols)
                
                if sheet_idx < 0 or sheet_idx >= len(self.sheet_images):
                    current_x += self.cell_w // 2
                    continue
                    
                gx = cell_idx % self.rows
                gy = cell_idx // self.rows
                
                cell_x = gx * self.cell_w
                cell_y = gy * self.cell_h
                
                glyph_item = SimGlyphItem(
                    glyph_idx=glyph_idx,
                    char_str=char,
                    sheet_idx=sheet_idx,
                    cell_x=cell_x,
                    cell_y=cell_y,
                    x_offset=current_x,
                    y_offset=current_y,
                    char_pos_idx=char_pos_idx,
                    viewer=self
                )
                self.sim_scene.addItem(glyph_item)
                
                if self.selected_char_index == char_pos_idx:
                    self.selected_sim_item = glyph_item
                elif self.selected_char_index == -1 and active_idx == glyph_idx and self.selected_sim_item is None:
                    self.selected_sim_item = glyph_item
                    self.selected_char_index = char_pos_idx
                    
                width = self.cell_w
                wid_idx = glyph_idx - self.first_code
                if 0 <= wid_idx < len(packets):
                    width = packets[wid_idx]["width"]
                    
                current_x += width
                char_pos_idx += 1
                
            current_y += self.cell_h + 10
            
        self.sim_scene.setSceneRect(self.sim_scene.itemsBoundingRect())

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
        items.sort(key=lambda x: (x.y_offset, x.x_offset))
        
        wid = self.metadata.get("WID1", [{}])[0]
        packets = wid.get("packets", [])
        
        current_y = -1
        current_x = 15
        
        for item in items:
            if current_y == -1 or item.y_offset != current_y:
                current_y = item.y_offset
                current_x = 15
                
            item.setPos(current_x, current_y)
            
            width = self.cell_w
            wid_idx = item.glyph_idx - self.first_code
            if 0 <= wid_idx < len(packets):
                width = packets[wid_idx]["width"]
                
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
        
        action = menu.exec_(self.sim_input.mapToGlobal(pos))
        if action:
            if action in [eng_p1, eng_p2, eng_p3, ukr_p1, ukr_p2, ukr_p3, ukr_p4]:
                self.sim_input.setPlainText(action.text())
