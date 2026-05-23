"""
Diagnostic script to check if translation archive contains saved changes.
Reads bmgres.arc from translation path and extracts zel_00.bmg to inspect its content.
"""
import struct
import json
from pathlib import Path
from core.containers import ContainerManager
from bmg_tool import BMGFile

TRANS_ARC_PATH = "E:/Emulators/RomHacking/ZELDA/TP_UA/ISO/UA/root/res/Msgus/bmgres.arc"
ENG_ARC_PATH = "E:/Emulators/RomHacking/ZELDA/TP_UA/ISO/ENG/root/res/Msgus/bmgres.arc"


def load_bmg_messages(arc_path: str, filename: str) -> list:
    """Open arc, extract filename, parse BMG, return list of text strings (first 20)."""
    raw = Path(arc_path).read_bytes()
    container = ContainerManager.open(raw)
    bmg_bytes = container.read_file(filename)
    bmg = BMGFile()
    bmg.load(bmg_bytes)
    texts = []
    for msg in bmg.messages[:20]:
        parts_text = []
        for p in msg.parts:
            if isinstance(p, str):
                parts_text.append(p)
            elif isinstance(p, dict):
                parts_text.append(f"<ESC:{p.get('escape_type', '?')}>")
        texts.append("".join(parts_text) if parts_text else "<empty>")
    return texts, len(bmg.messages)


def main():
    print("=== Translation Archive Content Check ===\n")

    for label, arc_path in [("ENG (source)", ENG_ARC_PATH), ("UA (translation)", TRANS_ARC_PATH)]:
        if not Path(arc_path).exists():
            print(f"[{label}] NOT FOUND: {arc_path}")
            continue

        arc_mtime = Path(arc_path).stat().st_mtime
        import datetime
        mtime_str = datetime.datetime.fromtimestamp(arc_mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{label}] {arc_path}")
        print(f"  Modified: {mtime_str}, Size: {Path(arc_path).stat().st_size} bytes")

        try:
            raw = Path(arc_path).read_bytes()
            container = ContainerManager.open(raw)
            files = container.list_files()
            print(f"  Files in archive: {files}")

            for fname in files:
                if fname.endswith('.bmg'):
                    bmg_bytes = container.read_file(fname)
                    bmg = BMGFile()
                    bmg.load(bmg_bytes)
                    print(f"\n  {fname}: {len(bmg.messages)} messages, sections={bmg.section_order}")
                    print(f"  First 5 messages:")
                    for i, msg in enumerate(bmg.messages[:5]):
                        parts_text = []
                        for p in msg.parts:
                            if isinstance(p, str):
                                parts_text.append(repr(p[:50]))
                            elif isinstance(p, dict):
                                parts_text.append(f"<ESC>")
                        msg_id = getattr(msg, 'id', 'N/A')
                        print(f"    [{i}] id={msg_id}: {''.join(parts_text)}")
        except Exception as e:
            import traceback
            print(f"  ERROR: {e}")
            traceback.print_exc()

        print()


if __name__ == "__main__":
    main()
