import sys
import os
import json

sys.path.append(os.getcwd())
from plugins.zelda_bmg.rules import GameRules
from core.containers import ContainerManager

bmg_arc_path = r"E:\Emulators\RomHacking\ZELDA\TP_UA\ISO\UA\root\res\Fontus\fontres.arc"

if not os.path.exists(bmg_arc_path):
    print(f"Archive not found: {bmg_arc_path}")
    sys.exit(1)

with open(bmg_arc_path, "rb") as f:
    container = ContainerManager.open(f.read())

bmg_data = None
for name in container.list_files():
    if "zel_00.bmg" in name or "zel_unit.bmg" in name:
        # Let's search for rodan or BMG
        pass
    if name.endswith(".bmg"):
        print(f"Found BMG in archive: {name}")
        bmg_data = container.read_file(name)
        bmg_name = name
        break

if not bmg_data:
    # Let's search for any bmg in Msgus or Fontus
    print("No BMG found in fontres.arc. Let's check Msgus...")
    msg_arc_path = r"E:\Emulators\RomHacking\ZELDA\TP_UA\ISO\UA\root\res\Msgus\zel_00.arc" # Or similar
    # Let's search Msgus directory
    msgus_dir = r"E:\Emulators\RomHacking\ZELDA\TP_UA\ISO\UA\root\res\Msgus"
    if os.path.exists(msgus_dir):
        for f_name in os.listdir(msgus_dir):
            if f_name.endswith(".arc"):
                print(f"Found arc in Msgus: {f_name}")
                with open(os.path.join(msgus_dir, f_name), "rb") as f:
                    c = ContainerManager.open(f.read())
                    for name in c.list_files():
                        if name.endswith(".bmg"):
                            print(f"Found BMG in {f_name}: {name}")
                            bmg_data = c.read_file(name)
                            bmg_name = name
                            break
            if bmg_data:
                break

if not bmg_data:
    print("Could not find any BMG file!")
    sys.exit(1)

# Initialize rules
rules = GameRules()
# We need mock MainWindow to load translation map from project_dir
class MockMW:
    class ProjectManager:
        project_dir = r"E:\Emulators\RomHacking\ZELDA\TP_UA\TwilightPrincess"
    project_manager = ProjectManager()
rules.mw = MockMW()
rules.load_translation_map()

strings, block_names = rules.load_data_from_json_obj(bmg_data)
print(f"Successfully loaded {len(strings[0])} strings from BMG {bmg_name}")

# Print strings around 3139 and 3151
for idx in [3139, 3151]:
    if idx < len(strings[0]):
        print(f"String {idx}: {repr(strings[0][idx])}")
    else:
        print(f"Index {idx} out of range (len={len(strings[0])})")
