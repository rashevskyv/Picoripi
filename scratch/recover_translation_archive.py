"""
Recovery script: copies the original ENG bmgres.arc to the UA translation folder
so the next app startup loads valid BMG data. The old (corrupted) translation archive
is backed up with .bak extension.
"""
import shutil
from pathlib import Path

ENG_SRC = Path("E:/Emulators/RomHacking/ZELDA/TP_UA/ISO/ENG/root/res/Msgus/bmgres.arc")
UA_TRANS = Path("E:/Emulators/RomHacking/ZELDA/TP_UA/ISO/UA/root/res/Msgus/bmgres.arc")

print(f"ENG source: {ENG_SRC} (exists={ENG_SRC.exists()}, size={ENG_SRC.stat().st_size if ENG_SRC.exists() else 'N/A'})")
print(f"UA target:  {UA_TRANS} (exists={UA_TRANS.exists()}, size={UA_TRANS.stat().st_size if UA_TRANS.exists() else 'N/A'})")

if not ENG_SRC.exists():
    print("ERROR: ENG source does not exist!")
else:
    bak_path = UA_TRANS.with_suffix('.arc.bak')
    if UA_TRANS.exists():
        shutil.copy2(UA_TRANS, bak_path)
        print(f"Backed up old UA archive to: {bak_path}")

    shutil.copy2(ENG_SRC, UA_TRANS)
    print(f"Copied ENG source -> UA translation. New size: {UA_TRANS.stat().st_size}")
    print("Recovery complete. The app will now load English source text as translation baseline.")
    print("NOTE: Any previously translated strings are lost (they were in the corrupted file).")
