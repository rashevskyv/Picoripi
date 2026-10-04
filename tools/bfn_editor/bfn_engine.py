"""BFN editor: unpack a BFN font into sheets and metrics and pack it back."""
import os
import struct
import json
from PIL import Image

from core.bfn_core import (GX_8BIT, gx8_encode as _gx8_encode, gx8_texels as _gx8_texels, map_lists_to_pairs,
                           map_pairs_to_lists)

def align_to(value, alignment):
    if value % alignment == 0:
        return value
    return value + (alignment - (value % alignment))

def extract_bfn_logic(bfn_path, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with open(bfn_path, 'rb') as f:
        file_data = f.read()
        
    if len(file_data) < 32:
        raise ValueError("File is too small to be a valid BFN file.")
        
    sig, file_size, num_chunks = struct.unpack('>8sII', file_data[:16])
    sig_str = sig.decode('ascii', errors='ignore')
    
    metadata = {
        "header": {
            "signature": sig_str,
            "num_chunks": num_chunks,
            # Wind Waker files keep WID1 and MAP1 before GLY1; repacking keeps the order.
            "chunk_order": []
        },
        "INF1": [],
        "GLY1": [],
        "MAP1": [],
        "WID1": []
    }

    offset = 32
    for chunk_idx in range(num_chunks):
        offset = align_to(offset, 32)
        if offset >= len(file_data):
            break

        chunk_start = offset
        if chunk_start + 8 > len(file_data):
            break

        chunk_sig, chunk_size = struct.unpack('>4sI', file_data[chunk_start:chunk_start+8])
        chunk_sig_str = chunk_sig.decode('ascii', errors='ignore')
        chunk_data_end = chunk_start + chunk_size

        chunk_body = file_data[chunk_start+8:chunk_data_end]
        if chunk_sig_str in ('INF1', 'GLY1', 'MAP1', 'WID1'):
            metadata["header"]["chunk_order"].append(chunk_sig_str)

        if chunk_sig_str == 'INF1':
            if len(chunk_body) < 12:
                raise ValueError("INF1 chunk body is too small.")
            encoding, ascent, descent, width, leading, fallback_code = struct.unpack('>HHHHHH', chunk_body[:12])
            unk1 = 0
            if len(chunk_body) >= 16:
                unk1 = struct.unpack('>I', chunk_body[12:16])[0]

            inf1 = {
                "encoding": int(encoding),
                "ascent": int(ascent),
                "descent": int(descent),
                "width": int(width),
                "leading": int(leading),
                "fallback_code": int(fallback_code),
                "unk1": int(unk1)
            }
            tail = chunk_body[16:24]
            if any(tail):
                inf1["tail"] = tail.hex()  # padding that is not zero in some files
            metadata["INF1"].append(inf1)
            
        elif chunk_sig_str == 'GLY1':
            if len(chunk_body) < 22:
                raise ValueError("GLY1 chunk body is too small.")
            start_glyph, end_glyph, cell_width, cell_height, page_data_size, texture_format, h_count, v_count, texture_width, texture_height = struct.unpack('>HHHHIHHHHH', chunk_body[:22])
            
            gly1_meta = {
                "start_glyph": int(start_glyph),
                "end_glyph": int(end_glyph),
                "cell_width": int(cell_width),
                "cell_height": int(cell_height),
                "page_data_size": int(page_data_size),
                "texture_format": int(texture_format),
                "glyph_horizontal_count": int(h_count),
                "glyph_vertical_count": int(v_count),
                "texture_width": int(texture_width),
                "texture_height": int(texture_height)
            }
            metadata["GLY1"].append(gly1_meta)
            
            sheet_count = (end_glyph - start_glyph) // (h_count * v_count) + 1
            sheet_start_offset = chunk_start + 8 + 22 + 2
            
            for s in range(sheet_count):
                sheet_offset = sheet_start_offset + s * page_data_size
                if sheet_offset + page_data_size > len(file_data):
                    break
                    
                sheet_data = file_data[sheet_offset : sheet_offset + page_data_size]
                
                img = Image.new("RGBA", (texture_width, texture_height))
                pixels = img.load()
                
                if texture_format == 0:  # I4
                    tiles_x = texture_width // 8
                    tiles_y = texture_height // 8
                    idx = 0
                    for ty in range(tiles_y):
                        for tx in range(tiles_x):
                            for y in range(8):
                                for x_byte in range(4):
                                    if idx >= len(sheet_data):
                                        break
                                    val = sheet_data[idx]
                                    idx += 1
                                    
                                    val1 = (val >> 4) & 0xF
                                    val2 = val & 0xF
                                    
                                    intensity1 = val1 * 17
                                    intensity2 = val2 * 17
                                    
                                    px1 = tx * 8 + x_byte * 2
                                    py1 = ty * 8 + y
                                    px2 = tx * 8 + x_byte * 2 + 1
                                    py2 = ty * 8 + y
                                    
                                    if px1 < texture_width and py1 < texture_height:
                                        pixels[px1, py1] = (intensity1, intensity1, intensity1, intensity1)
                                    if px2 < texture_width and py2 < texture_height:
                                        pixels[px2, py2] = (intensity2, intensity2, intensity2, intensity2)
                                        
                elif texture_format == 2:  # IA4
                    tiles_x = texture_width // 8
                    tiles_y = texture_height // 4
                    idx = 0
                    for ty in range(tiles_y):
                        for tx in range(tiles_x):
                            for y in range(4):
                                for x in range(8):
                                    if idx >= len(sheet_data):
                                        break
                                    val = sheet_data[idx]
                                    idx += 1
                                    
                                    intensity = (val & 0xF) * 17
                                    alpha = ((val >> 4) & 0xF) * 17
                                    
                                    px = tx * 8 + x
                                    py = ty * 4 + y
                                    
                                    if px < texture_width and py < texture_height:
                                        pixels[px, py] = (intensity, intensity, intensity, alpha)

                elif texture_format in GX_8BIT:  # I8 / IA8 (Twilight Princess HD)
                    for (px, py), (intensity, alpha) in _gx8_texels(texture_format, texture_width, texture_height, sheet_data):
                        pixels[px, py] = (intensity, intensity, intensity, alpha)

                img.save(os.path.join(output_dir, f"sheet_{s}.png"))
                
        elif chunk_sig_str == 'MAP1':
            if len(chunk_body) < 8:
                raise ValueError("MAP1 chunk body is too small.")
            mapping_type, first_char, last_char, entry_count = struct.unpack('>HHHH', chunk_body[:8])
            
            entries = []
            if mapping_type == 0:
                pass
            elif mapping_type == 2:
                entry_data = chunk_body[8:8+entry_count*2]
                entries = list(struct.unpack(f'>{entry_count}H', entry_data))
            elif mapping_type == 3:
                entry_data = chunk_body[8:8+entry_count*4]
                entries = map_pairs_to_lists(struct.unpack(f'>{entry_count*2}H', entry_data))

            map1 = {
                "mapping_type": int(mapping_type),
                "first_char": int(first_char),
                "last_char": int(last_char),
                "mapping_entry_count": int(entry_count),
                "entries": [int(e) for e in entries]
            }
            tail = chunk_body[8 + len(entries) * 2:]
            if mapping_type != 0 and any(tail):  # padding, or the data of a type the editor does not read
                map1["tail"] = tail.hex()
            metadata["MAP1"].append(map1)
            
        elif chunk_sig_str == 'WID1':
            if len(chunk_body) < 4:
                raise ValueError("WID1 chunk body is too small.")
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
                
            wid1 = {
                "first_code_included": int(first_code),
                "last_code_included": int(last_code),
                "packets": packets
            }
            tail = chunk_body[4 + len(packets) * 2:]
            if any(tail):
                wid1["tail"] = tail.hex()  # padding that is not zero in Wind Waker and Twilight Princess files
            metadata["WID1"].append(wid1)

        offset = chunk_data_end
        
    with open(os.path.join(output_dir, "data.json"), 'w') as json_f:
        json.dump(metadata, json_f, indent=4)

def repack_bfn_logic(input_dir, output_bfn_path):
    json_path = os.path.join(input_dir, 'data.json')
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Metadata file {json_path} not found.")
        
    with open(json_path, 'r') as json_file:
        metadata = json.load(json_file)
        
    chunks = {'INF1': [], 'GLY1': [], 'MAP1': [], 'WID1': []}
    
    # 1. WRITE INF1
    for inf in metadata.get("INF1", []):
        writer_buf = bytearray()
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
        writer_buf.extend(bytes.fromhex(inf.get("tail", "")).ljust(8, b'\x00')[:8])  # Padding
        chunks['INF1'].append(writer_buf)
        
    # 2. WRITE GLY1
    for gly in metadata.get("GLY1", []):
        writer_buf = bytearray()
        chunk_start = len(writer_buf)
        writer_buf.extend(struct.pack('>4sI', b'GLY1', 0))
        
        start_glyph = gly["start_glyph"]
        end_glyph = gly["end_glyph"]
        cell_width = gly["cell_width"]
        cell_height = gly["cell_height"]
        page_data_size = gly["page_data_size"]
        texture_format = gly["texture_format"]
        h_count = gly["glyph_horizontal_count"]
        v_count = gly["glyph_vertical_count"]
        texture_width = gly["texture_width"]
        texture_height = gly["texture_height"]
        
        writer_buf.extend(struct.pack('>HHHHIHHHHH',
            start_glyph,
            end_glyph,
            cell_width,
            cell_height,
            page_data_size,
            texture_format,
            h_count,
            v_count,
            texture_width,
            texture_height
        ))
        writer_buf.extend(b'\x00' * 2)  # Padding
        
        sheet_count = (end_glyph - start_glyph) // (h_count * v_count) + 1
        
        for s in range(sheet_count):
            png_filename = f"sheet_{s}.png"
            png_path = os.path.join(input_dir, png_filename)
            if not os.path.exists(png_path):
                raise FileNotFoundError(f"Texture sheet {png_path} not found.")
                
            img = Image.open(png_path).convert("RGBA")
            if img.size != (texture_width, texture_height):
                img = img.resize((texture_width, texture_height), Image.Resampling.LANCZOS)
                
            pixels = img.load()
            sheet_data = bytearray()
            
            if texture_format == 0:  # I4
                tiles_x = texture_width // 8
                tiles_y = texture_height // 8
                for ty in range(tiles_y):
                    for tx in range(tiles_x):
                        for y in range(8):
                            for x_byte in range(4):
                                px1 = tx * 8 + x_byte * 2
                                py1 = ty * 8 + y
                                px2 = tx * 8 + x_byte * 2 + 1
                                py2 = ty * 8 + y
                                
                                r1, g1, b1, a1 = pixels[px1, py1] if (px1 < texture_width and py1 < texture_height) else (0,0,0,0)
                                r2, g2, b2, a2 = pixels[px2, py2] if (px2 < texture_width and py2 < texture_height) else (0,0,0,0)
                                
                                val1 = min(15, max(0, int(round(r1 / 17.0))))
                                val2 = min(15, max(0, int(round(r2 / 17.0))))
                                
                                sheet_data.append((val1 << 4) | val2)
                                
            elif texture_format == 2:  # IA4
                tiles_x = texture_width // 8
                tiles_y = texture_height // 4
                for ty in range(tiles_y):
                    for tx in range(tiles_x):
                        for y in range(4):
                            for x in range(8):
                                px = tx * 8 + x
                                py = ty * 4 + y
                                
                                r, g, b, a = pixels[px, py] if (px < texture_width and py < texture_height) else (0,0,0,0)
                                
                                intensity = min(15, max(0, int(round(r / 17.0))))
                                alpha = min(15, max(0, int(round(a / 17.0))))
                                
                                sheet_data.append((alpha << 4) | intensity)
            elif texture_format in GX_8BIT:
                sheet_data = _gx8_encode(texture_format, texture_width, texture_height, pixels)
            else:
                raise ValueError(f"Unsupported texture format: {texture_format}")
                
            while len(sheet_data) < page_data_size:
                sheet_data.append(0)
                
            writer_buf.extend(sheet_data)
            
        while len(writer_buf) % 32 != 0:
            writer_buf.append(0)
            
        gly_size = len(writer_buf) - chunk_start
        struct.pack_into('>I', writer_buf, chunk_start + 4, gly_size)
        chunks['GLY1'].append(writer_buf)
        
    # 3. WRITE MAP1
    for map1 in metadata.get("MAP1", []):
        writer_buf = bytearray()
        while len(writer_buf) % 32 != 0:
            writer_buf.append(0)
            
        chunk_start = len(writer_buf)
        writer_buf.extend(struct.pack('>4sI', b'MAP1', 0))
        
        mapping_type = map1["mapping_type"]
        first_char = map1["first_char"]
        last_char = map1["last_char"]
        entry_count = map1["mapping_entry_count"]
        entries = map1.get("entries", [])
        # A linear map the editor expanded to a table goes back as written, while still linear.
        if "linear_count" in map1 and entries == list(range(last_char - first_char + 1)):
            mapping_type, entry_count = 0, map1["linear_count"]
        
        writer_buf.extend(struct.pack('>HHHH',
            mapping_type,
            first_char,
            last_char,
            entry_count
        ))
        
        if mapping_type == 0:
            writer_buf.extend(b'\x00' * 16)
        elif mapping_type == 2:
            for entry in entries:
                writer_buf.extend(struct.pack('>H', entry))
        elif mapping_type == 3:
            for entry in map_lists_to_pairs(entries):
                writer_buf.extend(struct.pack('>H', entry))
        if mapping_type != 0:
            writer_buf.extend(bytes.fromhex(map1.get("tail", ""))[:-len(writer_buf) % 32])

        while len(writer_buf) % 32 != 0:
            writer_buf.append(0)

        map_size = len(writer_buf) - chunk_start
        struct.pack_into('>I', writer_buf, chunk_start + 4, map_size)
        chunks['MAP1'].append(writer_buf)
        
    # 4. WRITE WID1
    for wid in metadata.get("WID1", []):
        writer_buf = bytearray()
        while len(writer_buf) % 32 != 0:
            writer_buf.append(0)
            
        chunk_start = len(writer_buf)
        writer_buf.extend(struct.pack('>4sI', b'WID1', 0))
        
        first_code = wid["first_code_included"]
        last_code = wid["last_code_included"]
        packets = wid.get("packets", [])
        
        writer_buf.extend(struct.pack('>HH', first_code, last_code))
        
        for pack in packets:
            k = pack["kerning"]
            if k < 0:
                k = (k + 256) & 0xFF
            writer_buf.append(k)
            writer_buf.append(pack["width"])

        writer_buf.extend(bytes.fromhex(wid.get("tail", ""))[:-len(writer_buf) % 32])
        while len(writer_buf) % 32 != 0:
            writer_buf.append(0)

        wid_size = len(writer_buf) - chunk_start
        struct.pack_into('>I', writer_buf, chunk_start + 4, wid_size)
        chunks['WID1'].append(writer_buf)

    order = metadata.get("header", {}).get("chunk_order") or []
    order = order + [kind for kind in ('INF1', 'GLY1', 'MAP1', 'WID1') for _ in range(len(chunks[kind]) - order.count(kind))]
    writer_buf = bytearray()
    chunk_counts = 0
    for kind in order:
        if chunks.get(kind):
            writer_buf.extend(chunks[kind].pop(0))
            chunk_counts += 1
        
    while len(writer_buf) % 32 != 0:
        writer_buf.append(0)
        
    final_buf = bytearray()
    sig = metadata["header"]["signature"].encode('ascii')
    if len(sig) < 8:
        sig = sig + b'\x00' * (8 - len(sig))
    elif len(sig) > 8:
        sig = sig[:8]
        
    file_size = len(writer_buf) + 32
    final_buf.extend(struct.pack('>8sII', sig, file_size, chunk_counts))
    final_buf.extend(b'\x00' * 16)
    final_buf.extend(writer_buf)
    
    with open(output_bfn_path, 'wb') as f:
        f.write(final_buf)
