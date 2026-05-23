import os
import sys
import json
import struct

# Додаємо поточну директорію до шляху імпорту
sys.path.append(os.path.abspath("."))

from tools.bfn_editor.bfn_engine import extract_bfn_logic
from core.containers import ContainerManager

orig_arc_path = "E:/Emulators/RomHacking/ZELDA/TP_UA/ISO/ENG/root/res/Fontus/fontres.arc"
temp_dir = "d:/git/dev/Picoripi/scratch/temp_orig"

if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

try:
    print(f"Reading archive: {orig_arc_path}")
    with open(orig_arc_path, 'rb') as f:
        arc_data = f.read()
        
    container = ContainerManager.open(arc_data)
    bfn_bytes = container.read_file("rodan_b_24_22.bfn")
    
    temp_bfn_path = os.path.join(temp_dir, "rodan_b_24_22.bfn")
    with open(temp_bfn_path, 'wb') as f:
        f.write(bfn_bytes)
        
    print("Extracting BFN...")
    extract_bfn_logic(temp_bfn_path, temp_dir)
    
    json_path = os.path.join(temp_dir, "data.json")
    with open(json_path, 'r') as f:
        meta = json.load(f)
        
    print("\n--- GLY1 Block ---")
    print(json.dumps(meta.get("GLY1", []), indent=2))
    
    print("\n--- MAP1 Block ---")
    maps = meta.get("MAP1", [])
    for m in maps:
        print(f"Type: {m.get('mapping_type')}, First: {m.get('first_char')}, Last: {m.get('last_char')}, Count: {m.get('mapping_entry_count')}")
        print("First 20 entries:", m.get("entries", [])[:20])
        
except Exception as e:
    print(f"Error: {e}")
