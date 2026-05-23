import sys
import os
import json

sys.path.append(os.getcwd())
from core.containers import ContainerManager
from core.bfn_core import BfnCore

edited_arc_path = r"E:\Emulators\RomHacking\ZELDA\TP_UA\ISO\UA\root\res\Fontus\fontres.arc"
trans_map_path = r"E:\Emulators\RomHacking\ZELDA\TP_UA\TwilightPrincess\translation_map.json"

with open(trans_map_path, "r", encoding="utf-8") as f:
    translation_map = json.load(f)

# Reconstruct translation map
unicode_to_cp1252 = {}
for ukr_char, cp1252_char in translation_map.items():
    if len(ukr_char) == 1 and len(cp1252_char) == 1:
        unicode_to_cp1252[ord(ukr_char)] = ord(cp1252_char)

with open(edited_arc_path, "rb") as f:
    container = ContainerManager.open(f.read())
bfn_data = container.read_file("rodan_b_24_22.bfn")

bfn = BfnCore()
bfn.load(bfn_data)

# Test encoding and then laying out in game (Dolphin)
text = "a reliable ally"
print(f"Original Text: '{text}'")

# How it encodes into BMG
encoded_bytes = []
for char in text:
    if ord(char) in unicode_to_cp1252:
        encoded_bytes.append(unicode_to_cp1252[ord(char)])
    else:
        encoded_bytes.append(ord(char))
print(f"Encoded BMG bytes: {encoded_bytes}")

# How game lays it out using MAP1
entries = bfn.map1[0]["entries"]
first_char = bfn.map1[0]["first_char"]
rendered_glyphs = []
for b in encoded_bytes:
    if first_char <= b < first_char + len(entries):
        glyph_idx = entries[b - first_char]
    else:
        glyph_idx = b
    rendered_glyphs.append(glyph_idx)

print(f"Rendered BFN Glyph indices in Dolphin: {rendered_glyphs}")

# Map glyph indices to standard character representations for display
def glyph_to_char(g):
    if g == 32: return " "
    if g == 65: return "A"
    if g == 97: return "a"
    if g == 82: return "R"
    if g == 114: return "r"
    # fallback
    try:
        return bytes([g]).decode('cp1252')
    except:
        return chr(g)

chars = [glyph_to_char(g) for g in rendered_glyphs]
print(f"What Dolphin displays: '{''.join(chars)}'")
