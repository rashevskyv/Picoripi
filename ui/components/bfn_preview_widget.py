import json
from pathlib import Path
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QImage
from PyQt5.QtCore import Qt, QRect

class BfnPreviewWidget(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self.text = ""
        self.active_font_name = None
        self.translation_map = None
        
        self.setFixedHeight(130) # standard height matching dialogue UI box
        self.setStyleSheet("background-color: #111111; border: 1px solid #333333; border-radius: 6px;")
        
        # Load translation map if available
        self.load_translation_map()

    def load_translation_map(self):
        plugin_name = getattr(self.mw, 'active_game_plugin', None)
        if plugin_name:
            mapping_path = Path("plugins") / plugin_name / 'translation_map.json'
            if mapping_path.exists():
                try:
                    with mapping_path.open('r', encoding='utf-8') as f:
                        self.translation_map = json.load(f)
                except Exception:
                    self.translation_map = None

    def update_preview_text(self, text: str):
        """Update the text and request redraw."""
        self.text = text
        self.update()

    def get_active_bfn_font(self):
        """Find the active BFN font for the current string."""
        # 1. Check if a custom font is set for the current string metadata
        block_idx = getattr(self.mw.data_store, 'current_block_idx', -1)
        string_idx = getattr(self.mw.data_store, 'current_string_idx', -1)
        
        font_file = None
        if block_idx != -1 and string_idx != -1:
            string_meta = self.mw.string_metadata.get((block_idx, string_idx), {})
            font_file = string_meta.get("font_file")

        # 2. If not, use default font
        if not font_file or font_file == "default":
            font_file = getattr(self.mw, 'default_font_file', None)

        if not font_file:
            return None

        # 3. Retrieve from core settings
        all_bfn_fonts = getattr(self.mw, 'all_bfn_fonts', {})
        return all_bfn_fonts.get(font_file)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        
        # Draw background inside border
        painter.fillRect(self.rect(), QColor("#121212"))
        
        bfn = self.get_active_bfn_font()
        if not bfn or not self.text:
            painter.setPen(QColor("#777777"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No BFN font loaded or text is empty")
            return
            
        sheets = bfn.get_sheets_qimages()
        if not sheets:
            painter.setPen(QColor("#ffaa00"))
            painter.drawText(self.rect(), Qt.AlignCenter, "BFN sheets not loaded")
            return

        # Reload translation map to ensure dynamic updates
        self.load_translation_map()

        # Translate Ukranian text to CP1252 mapped counterparts (e.g. 'і' to 'ì')
        encoded_text = self.text
        if self.translation_map:
            for ukr_char, cp1252_char in self.translation_map.items():
                encoded_text = encoded_text.replace(ukr_char, cp1252_char)

        # Extract glyph metrics
        gly = bfn.gly1[0]
        cell_w = gly["cell_width"]
        cell_h = gly["cell_height"]
        cols = gly["glyph_horizontal_count"]
        rows = gly["glyph_vertical_count"]
        start_glyph = gly["start_glyph"]
        end_glyph = gly["end_glyph"]

        # Parse MAP1 map
        char_to_glyph = {}
        if bfn.map1:
            m1 = bfn.map1[0]
            m_type = m1["mapping_type"]
            m_first = m1["first_char"]
            m_last = m1["last_char"]
            entries = m1["entries"]
            
            if m_type == 0:
                for idx in range(m_first, m_last + 1):
                    char_to_glyph[chr(idx)] = idx
            elif m_type == 2:
                for idx, code in enumerate(entries):
                    char_to_glyph[chr(m_first + idx)] = code
            elif m_type == 3:
                half = len(entries) // 2
                for k in range(half):
                    code = entries[k]
                    g_idx = entries[half + k]
                    char_to_glyph[chr(code)] = g_idx

        # Extract width packets
        wid = bfn.wid1[0]
        first_code = wid["first_code_included"]
        packets = wid["packets"]

        # Visual rendering offset settings
        current_y = 15
        lines = encoded_text.split('\n')

        for line in lines:
            current_x = 15
            for char in line:
                if char == ' ':
                    current_x += cell_w // 2
                    continue
                elif char == '\t':
                    current_x += cell_w * 2
                    continue

                glyph_idx = char_to_glyph.get(char, -1)
                if glyph_idx == -1 or glyph_idx > end_glyph:
                    # Draw fallback dark gray outline box for missing glyphs
                    painter.setPen(QColor("#444444"))
                    painter.drawRect(current_x, current_y, cell_w - 2, cell_h - 2)
                    current_x += cell_w // 2
                    continue

                rem = glyph_idx - start_glyph
                sheet_idx = rem // (rows * cols)
                cell_idx = rem % (rows * cols)

                if sheet_idx < 0 or sheet_idx >= len(sheets):
                    current_x += cell_w // 2
                    continue

                gx = cell_idx % rows
                gy = cell_idx // rows

                cell_x = gx * cell_w
                cell_y = gy * cell_h

                # Metrics width
                kerning = 0
                width = cell_w
                wid_idx = glyph_idx - first_code
                if 0 <= wid_idx < len(packets):
                    kerning = packets[wid_idx]["kerning"]
                    width = packets[wid_idx]["width"]

                crop_x = cell_x + kerning
                crop_w = width
                if crop_w <= 0:
                    crop_w = 1

                # Render decoded white/rgba glyph
                sheet_img = sheets[sheet_idx]
                painter.drawImage(current_x, current_y, sheet_img, crop_x, cell_y, crop_w, cell_h)

                # Move spacing cursor by character visual width
                current_x += width

            current_y += cell_h + 10
