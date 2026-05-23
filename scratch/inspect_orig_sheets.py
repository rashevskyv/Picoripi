import os
import json

json_path = "d:/git/dev/Picoripi/scratch/temp_orig/data.json"

with open(json_path, 'r') as f:
    meta = json.load(f)

# Подивимося на WID1 (ширини гліфів)
wid = meta.get("WID1", [{}])[0]
packets = wid.get("packets", [])
print(f"Total WID1 packets: {len(packets)}")
print("Width of glyph 0:", packets[0]["width"] if len(packets) > 0 else "N/A")
print("Width of glyph 32 (space):", packets[32]["width"] if len(packets) > 32 else "N/A")
print("Width of glyph 33 (!):", packets[33]["width"] if len(packets) > 33 else "N/A")
print("Width of glyph 65 (A):", packets[65]["width"] if len(packets) > 65 else "N/A")

# Перевіримо інші MAP блоки
print("\nMAP1 info:")
print(json.dumps(meta.get("MAP1", []), indent=2))
