import sys
import os
import json

sys.path.append(os.getcwd())
from core.containers import ContainerManager
from core.bfn_core import BfnCore

orig_arc_path = r"E:\Emulators\RomHacking\ZELDA\TP_UA\ISO\ENG\root\res\Fontus\fontres.arc"
edited_arc_path = r"E:\Emulators\RomHacking\ZELDA\TP_UA\ISO\UA\root\res\Fontus\fontres.arc"
trans_map_path = r"E:\Emulators\RomHacking\ZELDA\TP_UA\TwilightPrincess\translation_map.json"

if not os.path.exists(orig_arc_path):
    print(f"Original archive not found: {orig_arc_path}")
    sys.exit(1)
if not os.path.exists(edited_arc_path):
    print(f"Edited archive not found: {edited_arc_path}")
    sys.exit(1)

with open(trans_map_path, "r", encoding="utf-8") as f:
    translation_map = json.load(f)

# Build map: cp1252_code -> unicode_char_code
cp1252_to_unicode = {}
for ukr_char, cp1252_char in translation_map.items():
    if len(ukr_char) == 1 and len(cp1252_char) == 1:
        cp1252_to_unicode[ord(cp1252_char)] = ord(ukr_char)

# 1. Load original BFN to have a perfect clean BFN structure
with open(orig_arc_path, "rb") as f:
    container_orig = ContainerManager.open(f.read())
bfn_data_orig = None
for name in container_orig.list_files():
    if "rodan_b_24_22.bfn" in name:
        bfn_data_orig = container_orig.read_file(name)
        break
bfn_orig = BfnCore()
bfn_orig.load(bfn_data_orig)
orig_packets = bfn_orig.wid1[0]["packets"]

# 2. Load edited BFN to extract sheets (user's drawn letters)
with open(edited_arc_path, "rb") as f:
    container_edit = ContainerManager.open(f.read())

bfn_file_path_in_arc = None
bfn_data_edit = None
for name in container_edit.list_files():
    if "rodan_b_24_22.bfn" in name:
        bfn_file_path_in_arc = name
        bfn_data_edit = container_edit.read_file(name)
        break

if not bfn_data_edit:
    print("BFN file not found in edited archive!")
    sys.exit(1)

bfn_edit = BfnCore()
bfn_edit.load(bfn_data_edit)

# Static correct Cyrillic assignments we verified
cyrillic_assignments = {
    # UPPERCASE Cyrillic (А-Я)
    1040: 127, 1041: 128, 1042: 129, 1043: 130, 1168: 131, 1044: 132, 1045: 133, 1028: 134,
    1046: 135, 1047: 136, 1048: 137, 1030: 138, 1031: 139, 1049: 140, 1050: 141, 1051: 142,
    1052: 143, 1053: 144, 1054: 145, 1055: 146, 1056: 147, 1057: 148, 1058: 149, 1059: 150,
    1060: 151, 1061: 152, 1062: 153, 1063: 154, 1064: 155, 1065: 156, 1068: 157, 1070: 158,
    1071: 191,
    # LOWERCASE Cyrillic (а-я)
    1072: 192, 1073: 193, 1074: 194, 1075: 195, 1169: 196, 1076: 197, 1077: 198, 1108: 199,
    1078: 200, 1079: 201, 1080: 202, 1110: 203, 1111: 204, 1081: 205, 1082: 206, 1083: 207,
    1084: 208, 1085: 209, 1086: 210, 1087: 211, 1088: 212, 1089: 213, 1090: 214, 1091: 215,
    1092: 216, 1093: 217, 1094: 218, 1095: 219, 1096: 220, 1097: 221, 1100: 222, 1102: 223,
    1103: 224
}

# Rebuild clean BFN based on original
bfn_clean = BfnCore()
bfn_clean.load(bfn_data_orig)

# Copy the edited texture sheet images from the user's BFN
bfn_clean.gly1[0]["sheets_binary"] = bfn_edit.gly1[0].get("sheets_binary", [])
if hasattr(bfn_edit, "sheet_images") and bfn_edit.sheet_images:
    bfn_clean.sheet_images = bfn_edit.sheet_images

# Build correct MAP1 mapping of length 224 (last_char = 255)
correct_entries = [i + 32 for i in range(224)] # Default CP1252 sequentially increasing

# Reconstruct shifting using the golden law of BFN mapping
for cp1252_code in range(32, 256):
    idx_in_entries = cp1252_code - 32
    if cp1252_code in cp1252_to_unicode:
        unicode_char_code = cp1252_to_unicode[cp1252_code]
        if unicode_char_code >= 1000:
            # Cyrillic: map to its custom glyph index from our verified table
            if unicode_char_code in cyrillic_assignments:
                glyph_idx = cyrillic_assignments[unicode_char_code]
                correct_entries[idx_in_entries] = glyph_idx
                print(f"Mapping Cyrillic: CP1252 {cp1252_code} (Unicode {unicode_char_code}) -> glyph_idx {glyph_idx}")
        else:
            # Shifted Latin/Special: map to its standard Unicode character code
            correct_entries[idx_in_entries] = unicode_char_code
            print(f"Mapping Shifted Latin: CP1252 {cp1252_code} (Unicode {unicode_char_code}) -> glyph_idx {unicode_char_code}")

# Update MAP1 chunk
bfn_clean.map1[0]["mapping_type"] = 2
bfn_clean.map1[0]["first_char"] = 32
bfn_clean.map1[0]["last_char"] = 255
bfn_clean.map1[0]["mapping_entry_count"] = 224
bfn_clean.map1[0]["entries"] = correct_entries

# Expand WID1 packets to cover all glyphs up to 255
max_glyph_idx_used = max(correct_entries)
print(f"\nMax glyph_idx used: {max_glyph_idx_used}")

wid = bfn_clean.wid1[0]
packets = wid["packets"]
first_code = wid["first_code_included"]

required_packets_count = max_glyph_idx_used - first_code + 1
if len(packets) < required_packets_count:
    padding_needed = required_packets_count - len(packets)
    print(f"Expanding WID1 packets from {len(packets)} to {required_packets_count} (adding {padding_needed} packets)")
    for i in range(len(packets), required_packets_count):
        glyph_idx = first_code + i
        orig_width = 12
        orig_kern = 0
        orig_idx = glyph_idx - bfn_orig.wid1[0]["first_code_included"]
        if 0 <= orig_idx < len(orig_packets):
            orig_width = orig_packets[orig_idx]["width"]
            orig_kern = orig_packets[orig_idx]["kerning"]
        packets.append({"kerning": orig_kern, "width": orig_width})

wid["last_code_included"] = first_code + len(packets)

# Copy the metrics from edited BFN's WID1 for Cyrillic and Shifted Latin glyphs
edited_packets = bfn_edit.wid1[0]["packets"]
edited_first = bfn_edit.wid1[0]["first_code_included"]

# Build inverse map of correct_entries to find which CP1252 codes map to which glyph index.
# This helps us copy the metrics exactly as edited by the user!
glyph_to_cp1252_codes = {}
for idx_in_entries, glyph_idx in enumerate(correct_entries):
    cp1252_code = 32 + idx_in_entries
    if glyph_idx not in glyph_to_cp1252_codes:
        glyph_to_cp1252_codes[glyph_idx] = []
    glyph_to_cp1252_codes[glyph_idx].append(cp1252_code)

for i in range(len(packets)):
    glyph_idx = first_code + i
    edit_idx = glyph_idx - edited_first
    
    # We want to preserve user-customized widths.
    # In edited BFN, user customized widths at position edit_idx.
    if 0 <= edit_idx < len(edited_packets):
        w = edited_packets[edit_idx]["width"]
        k = edited_packets[edit_idx]["kerning"]
        # Copy the customized metrics
        packets[i]["width"] = w
        packets[i]["kerning"] = k
    else:
        # Fallback to original metrics
        orig_idx = glyph_idx - bfn_orig.wid1[0]["first_code_included"]
        if 0 <= orig_idx < len(orig_packets):
            packets[i]["width"] = orig_packets[orig_idx]["width"]
            packets[i]["kerning"] = orig_packets[orig_idx]["kerning"]

# 5. Compile BFN and save back into RARC
new_bfn_bytes = bfn_clean.save()

# Update archive
container_edit.write_file(bfn_file_path_in_arc, new_bfn_bytes)
new_arc_bytes = container_edit.pack()

with open(edited_arc_path, "wb") as f:
    f.write(new_arc_bytes)
    
print("\nSuccessfully reconstructed BFN with PERFECT Shifted Latin and Cyrillic mappings restored!")
