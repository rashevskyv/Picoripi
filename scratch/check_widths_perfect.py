import sys
import os
import json

sys.path.append(os.getcwd())
from core.containers import ContainerManager
from core.bfn_core import BfnCore

edited_arc_path = r"E:\Emulators\RomHacking\ZELDA\TP_UA\ISO\UA\root\res\Fontus\fontres.arc"
trans_map_path = r"E:\Emulators\RomHacking\ZELDA\TP_UA\TwilightPrincess\translation_map.json"

if not os.path.exists(edited_arc_path):
    print(f"Edited archive not found: {edited_arc_path}")
    sys.exit(1)

with open(trans_map_path, "r", encoding="utf-8") as f:
    translation_map = json.load(f)

unicode_to_cp1252 = {}
for ukr_char, cp1252_char in translation_map.items():
    if len(ukr_char) == 1 and len(cp1252_char) == 1:
        unicode_to_cp1252[ord(ukr_char)] = ord(cp1252_char)

with open(edited_arc_path, "rb") as f:
    container = ContainerManager.open(f.read())

bfn_data = None
for name in container.list_files():
    if "rodan_b_24_22.bfn" in name:
        bfn_data = container.read_file(name)
        break

bfn = BfnCore()
bfn.load(bfn_data)

wid = bfn.wid1[0]
packets = wid["packets"]
first_code = wid["first_code_included"]
entries = bfn.map1[0]["entries"]
first_char = bfn.map1[0]["first_char"]

print(f"MAP1: first_char={first_char}, last_char={bfn.map1[0]['last_char']}, entry_count={bfn.map1[0]['mapping_entry_count']}")
print(f"WID1: first_code={first_code}, last_code={wid['last_code_included']}, packet_count={len(packets)}")

def get_char_metrics(char):
    unicode_code = ord(char)
    # Convert to cp1252 code
    if unicode_code in unicode_to_cp1252:
        code = unicode_to_cp1252[unicode_code]
    else:
        code = unicode_code
    
    # Check map1
    if first_char <= code < first_char + len(entries):
        glyph_idx = entries[code - first_char]
    else:
        glyph_idx = code
    
    # Check wid1
    wid_idx = glyph_idx - first_code
    if 0 <= wid_idx < len(packets):
        return glyph_idx, packets[wid_idx]["width"], packets[wid_idx]["kerning"]
    return glyph_idx, None, None

# Test some characters
chars_to_test = [' ', 'a', 'o', 'A', 'O', 'А', 'Я', 'а', 'я', 'і', 'І', 'є', 'Є', 'ї', 'Ї', 'ґ', 'Ґ']
for c in chars_to_test:
    glyph_idx, w, k = get_char_metrics(c)
    cp_code = unicode_to_cp1252.get(ord(c), ord(c))
    print(f"Char: '{c}' (Unicode {ord(c)}) -> CP1252 Code: {cp_code} -> GlyphIdx: {glyph_idx}, Width: {w}, Kerning: {k}")
