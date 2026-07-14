import os
import struct
import json
from typing import Dict, Any, List, Tuple, Optional
from PyQt6.QtGui import QImage, QColor
from utils.logging_utils import log_info, log_warning, log_error

def align_to(value: int, alignment: int) -> int:
    """Align to."""
    if value % alignment == 0:
        return value
    return value + (alignment - (value % alignment))

class BfnCore:
    """Bfn core implementation."""
    def __init__(self):
        """Initialize a new instance."""
        self.signature = "FFNT1bnd"
        self.num_chunks = 0
        self.inf1 = []
        self.gly1 = []
        self.map1 = []
        self.wid1 = []
        self._qimages_cache = None

    def load_file(self, path: str) -> None:
        """Load file."""
        with open(path, 'rb') as f:
            data = f.read()
        self.load(data)

    def load(self, data: bytes) -> None:
        """Load ."""
        self._qimages_cache = None
        if len(data) < 32:
            raise ValueError("File is too small to be a valid BFN file.")
            
        sig, file_size, num_chunks = struct.unpack('>8sII', data[:16])
        self.signature = sig.decode('ascii', errors='ignore')
        self.num_chunks = num_chunks
        
        self.inf1 = []
        self.gly1 = []
        self.map1 = []
        self.wid1 = []
        
        offset = 32
        for _ in range(num_chunks):
            offset = align_to(offset, 32)
            if offset >= len(data):
                break
                
            chunk_start = offset
            if chunk_start + 8 > len(data):
                break
                
            chunk_sig, chunk_size = struct.unpack('>4sI', data[chunk_start:chunk_start+8])
            chunk_sig_str = chunk_sig.decode('ascii', errors='ignore')
            chunk_data_end = chunk_start + chunk_size
            chunk_body = data[chunk_start+8:chunk_data_end]
            
            if chunk_sig_str == 'INF1':
                if len(chunk_body) < 12:
                    continue
                encoding, ascent, descent, width, leading, fallback_code = struct.unpack('>HHHHHH', chunk_body[:12])
                unk1 = 0
                if len(chunk_body) >= 16:
                    unk1 = struct.unpack('>I', chunk_body[12:16])[0]
                self.inf1.append({
                    "encoding": int(encoding),
                    "ascent": int(ascent),
                    "descent": int(descent),
                    "width": int(width),
                    "leading": int(leading),
                    "fallback_code": int(fallback_code),
                    "unk1": int(unk1)
                })
                
            elif chunk_sig_str == 'GLY1':
                if len(chunk_body) < 22:
                    continue
                start_glyph, end_glyph, cell_width, cell_height, page_data_size, texture_format, h_count, v_count, texture_width, texture_height = struct.unpack('>HHHHIHHHHH', chunk_body[:22])
                
                # GLY1 also contains sheets data starting from chunk_start + 8 + 22 + 2
                sheet_count = (end_glyph - start_glyph) // (h_count * v_count) + 1
                sheet_start_offset = chunk_start + 8 + 22 + 2
                sheets_binary = []
                
                for s in range(sheet_count):
                    sheet_offset = sheet_start_offset + s * page_data_size
                    if sheet_offset + page_data_size > len(data):
                        break
                    sheets_binary.append(data[sheet_offset : sheet_offset + page_data_size])
                
                self.gly1.append({
                    "start_glyph": int(start_glyph),
                    "end_glyph": int(end_glyph),
                    "cell_width": int(cell_width),
                    "cell_height": int(cell_height),
                    "page_data_size": int(page_data_size),
                    "texture_format": int(texture_format),
                    "glyph_horizontal_count": int(h_count),
                    "glyph_vertical_count": int(v_count),
                    "texture_width": int(texture_width),
                    "texture_height": int(texture_height),
                    "sheets_binary": sheets_binary
                })
                
            elif chunk_sig_str == 'MAP1':
                if len(chunk_body) < 8:
                    continue
                mapping_type, first_char, last_char, entry_count = struct.unpack('>HHHH', chunk_body[:8])
                
                entries = []
                if mapping_type == 0:
                    mapping_type = 2
                    entry_count = last_char - first_char + 1
                    entries = [i for i in range(entry_count)]
                elif mapping_type == 2:
                    entry_data = chunk_body[8:8+entry_count*2]
                    entries = list(struct.unpack(f'>{entry_count}H', entry_data))
                elif mapping_type == 3:
                    entry_data = chunk_body[8:8+entry_count*4]
                    entries = list(struct.unpack(f'>{entry_count*2}H', entry_data))
                    
                self.map1.append({
                    "mapping_type": int(mapping_type),
                    "first_char": int(first_char),
                    "last_char": int(last_char),
                    "mapping_entry_count": int(entry_count),
                    "entries": [int(e) for e in entries]
                })
                
            elif chunk_sig_str == 'WID1':
                if len(chunk_body) < 4:
                    continue
                first_code, last_code = struct.unpack('>HH', chunk_body[:4])
                packet_count = last_code - first_code
                
                packets = []
                packet_data = chunk_body[4:4+packet_count*2]
                for p in range(packet_count):
                    if p*2+1 >= len(packet_data):
                        break
                    kerning = packet_data[p*2]
                    if kerning >= 128:
                        kerning -= 256
                    width = packet_data[p*2+1]
                    packets.append({
                        "kerning": int(kerning),
                        "width": int(width)
                    })
                    
                self.wid1.append({
                    "first_code_included": int(first_code),
                    "last_code_included": int(last_code),
                    "packets": packets
                })
                
            offset = chunk_data_end

    def save(self) -> bytes:
        """Save ."""
        writer_buf = bytearray()
        chunk_counts = 0
        
        # 1. WRITE INF1
        for inf in self.inf1:
            chunk_start = len(writer_buf)
            writer_buf.extend(struct.pack('>4sI', b'INF1', 32))
            writer_buf.extend(struct.pack('>HHHHHH', 
                inf["encoding"], 
                inf["ascent"], 
                inf["descent"], 
                inf["width"], 
                inf["leading"], 
                inf["fallback_code"]
            ))
            writer_buf.extend(struct.pack('>I', inf.get("unk1", 0)))
            writer_buf.extend(b'\x00' * 8)
            chunk_counts += 1
            
        # 2. WRITE GLY1
        for gly in self.gly1:
            chunk_start = len(writer_buf)
            writer_buf.extend(struct.pack('>4sI', b'GLY1', 0))
            
            writer_buf.extend(struct.pack('>HHHHIHHHHH',
                gly["start_glyph"],
                gly["end_glyph"],
                gly["cell_width"],
                gly["cell_height"],
                gly["page_data_size"],
                gly["texture_format"],
                gly["glyph_horizontal_count"],
                gly["glyph_vertical_count"],
                gly["texture_width"],
                gly["texture_height"]
            ))
            writer_buf.extend(b'\x00' * 2)
            
            for sheet_bin in gly.get("sheets_binary", []):
                writer_buf.extend(sheet_bin)
                
            while len(writer_buf) % 32 != 0:
                writer_buf.append(0)
                
            gly_size = len(writer_buf) - chunk_start
            struct.pack_into('>I', writer_buf, chunk_start + 4, gly_size)
            chunk_counts += 1
            
        # 3. WRITE MAP1
        for m1 in self.map1:
            while len(writer_buf) % 32 != 0:
                writer_buf.append(0)
                
            chunk_start = len(writer_buf)
            writer_buf.extend(struct.pack('>4sI', b'MAP1', 0))
            
            writer_buf.extend(struct.pack('>HHHH',
                m1["mapping_type"],
                m1["first_char"],
                m1["last_char"],
                m1["mapping_entry_count"]
            ))
            
            mapping_type = m1["mapping_type"]
            entries = m1.get("entries", [])
            
            if mapping_type == 0:
                writer_buf.extend(b'\x00' * 16)
            elif mapping_type in (2, 3):
                for entry in entries:
                    writer_buf.extend(struct.pack('>H', entry))
                    
            while len(writer_buf) % 32 != 0:
                writer_buf.append(0)
                
            map_size = len(writer_buf) - chunk_start
            struct.pack_into('>I', writer_buf, chunk_start + 4, map_size)
            chunk_counts += 1
            
        # 4. WRITE WID1
        for w1 in self.wid1:
            while len(writer_buf) % 32 != 0:
                writer_buf.append(0)
                
            chunk_start = len(writer_buf)
            writer_buf.extend(struct.pack('>4sI', b'WID1', 0))
            
            writer_buf.extend(struct.pack('>HH', w1["first_code_included"], w1["last_code_included"]))
            
            for pack in w1.get("packets", []):
                k = pack["kerning"]
                if k < 0:
                    k = (k + 256) & 0xFF
                writer_buf.append(k)
                writer_buf.append(pack["width"])
                
            while len(writer_buf) % 32 != 0:
                writer_buf.append(0)
                
            wid_size = len(writer_buf) - chunk_start
            struct.pack_into('>I', writer_buf, chunk_start + 4, wid_size)
            chunk_counts += 1
            
        while len(writer_buf) % 32 != 0:
            writer_buf.append(0)
            
        final_buf = bytearray()
        sig_bytes = self.signature.encode('ascii')
        if len(sig_bytes) < 8:
            sig_bytes = sig_bytes + b'\x00' * (8 - len(sig_bytes))
        else:
            sig_bytes = sig_bytes[:8]
            
        file_size = len(writer_buf) + 32
        final_buf.extend(struct.pack('>8sII', sig_bytes, file_size, chunk_counts))
        final_buf.extend(b'\x00' * 16)
        final_buf.extend(writer_buf)
        
        return bytes(final_buf)

    def to_font_map(self, translation_map: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, int]]:
        """
        Convert BFN metrics to Picoripi-compatible font_map dictionary:
        { "char": { "width": width_in_pixels } }
        """
        font_map = {}
        
        if not self.wid1 or not self.map1:
            return font_map
            
        # INF1 default width
        default_width = 12
        if self.inf1:
            default_width = self.inf1[0]["width"]
            
        # Parse WID1 widths
        wid = self.wid1[0]
        first_code = wid["first_code_included"]
        last_code = wid["last_code_included"]
        packets = wid["packets"]
        
        # Parse MAP1 maps
        m1 = self.map1[0]
        mapping_type = m1["mapping_type"]
        first_char = m1["first_char"]
        last_char = m1["last_char"]
        entries = m1["entries"]
        
        # 1. Base CP1252 Mapping
        if mapping_type == 2:
            for idx, glyph_idx in enumerate(entries):
                char_code = first_char + idx
                
                # Get width for glyph_idx
                char_width = default_width
                if first_code <= glyph_idx < last_code:
                    p_idx = glyph_idx - first_code
                    if p_idx < len(packets):
                        char_width = packets[p_idx]["width"]
                        
                # Translate CP1252 char_code to Unicode character
                try:
                    char_str = bytes([char_code]).decode('cp1252')
                except Exception:
                    char_str = chr(char_code)
                    
                font_map[char_str] = {"width": char_width}
                
        # 2. Add mappings based on translation map overrides (e.g. mapping Ukrainian 'і' to CP1252 'ì')
        if translation_map:
            for ukr_char, cp1252_char in translation_map.items():
                if cp1252_char in font_map:
                    font_map[ukr_char] = {"width": font_map[cp1252_char]["width"]}
                    
        return font_map

    def get_sheets_qimages(self) -> List[QImage]:
        """
        Decode the binary sheets (texture sheets) from GLY1 chunk using I4 or IA4 formats
        directly into PyQt6 QImage objects. Results are cached.
        """
        if self._qimages_cache is not None:
            return self._qimages_cache

        self._qimages_cache = []
        if not self.gly1:
            return self._qimages_cache

        gly = self.gly1[0]
        texture_width = gly["texture_width"]
        texture_height = gly["texture_height"]
        texture_format = gly["texture_format"]
        sheets_binary = gly.get("sheets_binary", [])

        for sheet_bin in sheets_binary:
            img = QImage(texture_width, texture_height, QImage.Format.Format_ARGB32)
            img.fill(0) # Start with fully transparent transparent black

            if texture_format == 0:  # I4 (intensity 4 bits, tiles of 8x8)
                tiles_x = texture_width // 8
                tiles_y = texture_height // 8
                idx = 0
                for ty in range(tiles_y):
                    for tx in range(tiles_x):
                        for y in range(8):
                            for x_byte in range(4):
                                if idx >= len(sheet_bin):
                                    break
                                val = sheet_bin[idx]
                                idx += 1
                                
                                val1 = (val >> 4) & 0x0F
                                val2 = val & 0x0F
                                
                                c1 = val1 * 17
                                c2 = val2 * 17
                                
                                px1 = tx * 8 + x_byte * 2
                                py1 = ty * 8 + y
                                px2 = tx * 8 + x_byte * 2 + 1
                                py2 = ty * 8 + y
                                
                                if px1 < texture_width and py1 < texture_height:
                                    img.setPixel(px1, py1, QColor(c1, c1, c1, c1).rgba())
                                if px2 < texture_width and py2 < texture_height:
                                    img.setPixel(px2, py2, QColor(c2, c2, c2, c2).rgba())

            elif texture_format == 2:  # IA4 (intensity/alpha 4 bits, tiles of 8x4)
                tiles_x = texture_width // 8
                tiles_y = texture_height // 4
                idx = 0
                for ty in range(tiles_y):
                    for tx in range(tiles_x):
                        for y in range(4):
                            for x in range(8):
                                if idx >= len(sheet_bin):
                                    break
                                val = sheet_bin[idx]
                                idx += 1
                                
                                intensity = (val & 0x0F) * 17
                                alpha = ((val >> 4) & 0x0F) * 17
                                
                                px = tx * 8 + x
                                py = ty * 4 + y
                                
                                if px < texture_width and py < texture_height:
                                    img.setPixel(px, py, QColor(intensity, intensity, intensity, alpha).rgba())
            else:
                log_error(f"Unsupported BFN texture format during QImage conversion: {texture_format}")

            self._qimages_cache.append(img)

        return self._qimages_cache

    def layout_text(self, text: str, translation_map: Optional[Dict[str, str]] = None, line_spacing: int = 10,
                    char_spacing: float = 0, colors: Optional[List[Optional[str]]] = None,
                    scales: Optional[List[float]] = None,
                    icons: Optional[Dict[int, Dict[str, Any]]] = None) -> Tuple[List[Dict[str, Any]], int, int]:
        """
        Compute layout positions for each character in text based on current BFN font metrics.

        The placement algorithm is ported from the Twilight Princess message renderer
        (dusklight: J2DPrint::parse + JUTResFont::drawChar_scale/getWidthEntry,
        jmessage_tRenderingProcessor::do_character/do_scale):
          - the horizontal advance of a glyph is its WID1 width (times the active
            scale) plus char_spacing; char_spacing itself is NOT scaled, exactly
            like the game's charSpace;
          - a glyph quad is a full font cell drawn at (cursor - kerning*scale), so
            wide glyphs may overhang their advance exactly like in game;
          - lines are baseline-aligned: the first baseline sits at ascent below the
            origin and each newline advances by INF1 leading plus line_spacing;
          - a scaled glyph is vertically centered on the normal line box, matching
            the game's do_scale/do_transY half-height adjustment;
          - tab stops every (default_width * 4) pixels, as in J2DPrint.

        colors: optional per-character color list aligned with `text` (including
        newline positions); each entry is a "#rrggbb" string or None for default.
        scales: optional per-character scale list aligned like colors; each entry
        is a float (1.0 = normal size, from the game's scale tag percent/100).
        icons: optional dict mapping character index in `text` to an inline icon
        drawing spec; such characters become icon glyphs advancing by the spec's
        "width" (default 24 px, the game's do_outfont icon size) times scale.

        Returns:
            - List of dictionaries representing laid out glyphs.
            - total width of text block
            - total height of text block
        """
        try:
            line_spacing = int(line_spacing)
        except (TypeError, ValueError):
            line_spacing = 10
        try:
            char_spacing = float(char_spacing)
        except (TypeError, ValueError):
            char_spacing = 0.0

        glyphs_layout = []
        if not self.gly1 or not self.map1 or not self.wid1:
            return glyphs_layout, 0, 0

        gly = self.gly1[0]
        cell_w = gly["cell_width"]
        cell_h = gly["cell_height"]
        cols = gly["glyph_horizontal_count"]
        rows = gly["glyph_vertical_count"]
        start_glyph = gly["start_glyph"]
        end_glyph = gly["end_glyph"]

        # Font metrics from INF1 (JUTFont ascent/descent/leading semantics)
        inf = self.inf1[0] if self.inf1 else {}
        ascent = inf.get("ascent", 0) or cell_h
        descent = inf.get("descent", 0)
        leading = inf.get("leading", 0)
        default_width = inf.get("width", 0) or cell_w
        if leading <= 0:
            leading = cell_h
        tab_size = default_width * 4

        wid = self.wid1[0]
        first_code = wid["first_code_included"]
        packets = wid["packets"]

        # Parse MAP1 maps
        def code_to_char(code):
            """Code to char."""
            try:
                return bytes([code]).decode('cp1252')
            except Exception:
                return chr(code)

        char_to_glyph = {}
        m1 = self.map1[0]
        m_type = m1["mapping_type"]
        m_first = m1["first_char"]
        m_last = m1["last_char"]
        entries = m1["entries"]

        if m_type == 0:
            for idx in range(m_first, m_last + 1):
                char_to_glyph[code_to_char(idx)] = idx - m_first
        elif m_type == 2:
            for c_idx, g_idx in enumerate(entries):
                char_code = m_first + c_idx
                char_to_glyph[code_to_char(char_code)] = g_idx
        elif m_type == 3:
            half = len(entries) // 2
            for k in range(half):
                code = entries[k]
                g_idx = entries[half + k]
                char_to_glyph[code_to_char(code)] = g_idx

        pad = 15  # Match simulator's padding of 15px
        line_advance = leading + line_spacing
        baseline = pad + ascent
        total_width = 0
        char_pos_idx = 0
        abs_idx = 0  # index into `text` for color lookup

        lines = text.split('\n')
        for line_no, line in enumerate(lines):
            if line_no > 0:
                abs_idx += 1  # the '\n' consumed by split
            current_x = float(pad)
            for char in line:
                color = None
                if colors and abs_idx < len(colors):
                    color = colors[abs_idx]
                scale = 1.0
                if scales and abs_idx < len(scales):
                    try:
                        scale = float(scales[abs_idx])
                    except (TypeError, ValueError):
                        scale = 1.0
                    if scale <= 0:
                        scale = 1.0
                icon_spec = icons.get(abs_idx) if icons else None
                abs_idx += 1

                if icon_spec is not None:
                    # Inline icon (game do_outfont): 24x24 px box (times scale),
                    # vertically centered on the line, advance = width*scale
                    try:
                        icon_w = float(icon_spec.get("width", 24))
                    except (TypeError, ValueError):
                        icon_w = 24.0
                    size = icon_w * scale
                    center_y = (baseline - ascent) + cell_h / 2.0
                    glyphs_layout.append({
                        "char": char,
                        "glyph_idx": -1,
                        "sheet_idx": -1,
                        "cell_x": 0,
                        "cell_y": 0,
                        "draw_x": current_x,
                        "draw_y": center_y - size / 2.0,
                        "width": icon_w,
                        "kerning": 0,
                        "color": color,
                        "scale": scale,
                        "icon": icon_spec,
                        "is_fallback": False,
                        "char_pos_idx": char_pos_idx
                    })
                    current_x += size + char_spacing
                    char_pos_idx += 1
                    continue

                if char == '\t':
                    # J2DPrint tab: advance to the next tab stop relative to line origin
                    rel = current_x - pad
                    current_x = pad + tab_size * (int(rel / tab_size) + 1)
                    continue

                glyph_idx = char_to_glyph.get(char, -1)
                if glyph_idx == -1 and translation_map:
                    fallback_char = translation_map.get(char)
                    if fallback_char:
                        glyph_idx = char_to_glyph.get(fallback_char, -1)

                # A scaled glyph is vertically centered on the normal line box
                # (game: do_scale shifts by half the font height difference)
                draw_y = (baseline - ascent) + (1.0 - scale) * cell_h / 2.0

                if glyph_idx == -1 or glyph_idx > end_glyph:
                    # Unmapped character: advance by the INF1 default width like
                    # the game's fallback glyph. Space just advances silently.
                    width = default_width
                    if char != ' ':
                        glyphs_layout.append({
                            "char": char,
                            "glyph_idx": -1,
                            "sheet_idx": -1,
                            "cell_x": 0,
                            "cell_y": 0,
                            "draw_x": current_x,
                            "draw_y": draw_y,
                            "width": width,
                            "kerning": 0,
                            "color": color,
                            "scale": scale,
                            "is_fallback": True,
                            "char_pos_idx": char_pos_idx
                        })
                    current_x += width * scale + char_spacing
                    char_pos_idx += 1
                    continue

                rem = glyph_idx - start_glyph
                sheet_idx = rem // (rows * cols)
                cell_idx = rem % (rows * cols)

                gx = cell_idx % cols
                gy = cell_idx // cols

                cell_x = gx * cell_w
                cell_y = gy * cell_h

                kerning = 0
                width = cell_w
                wid_idx = glyph_idx - first_code
                if 0 <= wid_idx < len(packets):
                    kerning = packets[wid_idx]["kerning"]
                    width = packets[wid_idx]["width"]

                glyphs_layout.append({
                    "char": char,
                    "glyph_idx": glyph_idx,
                    "sheet_idx": sheet_idx,
                    "cell_x": cell_x,
                    "cell_y": cell_y,
                    # JUTResFont::drawChar_scale shifts the full-cell quad left by kerning
                    "draw_x": current_x - kerning * scale,
                    "draw_y": draw_y,
                    "width": width,
                    "kerning": kerning,
                    "color": color,
                    "scale": scale,
                    "is_fallback": False,
                    "char_pos_idx": char_pos_idx
                })

                # game: advance = charSpace + width * scale (charSpace unscaled)
                current_x += width * scale + char_spacing
                char_pos_idx += 1

            if current_x - pad > total_width:
                total_width = current_x - pad
            if line_no < len(lines) - 1:
                baseline += line_advance

        total_height = (baseline + max(descent, cell_h - ascent)) - pad
        if total_height < 0:
            total_height = 0

        return glyphs_layout, int(round(total_width)), int(round(total_height))
