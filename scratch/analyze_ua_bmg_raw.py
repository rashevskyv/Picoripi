"""
Low-level BMG structure analyzer - does not use BMGFile.load(), reads sections directly.
"""
import struct
from pathlib import Path
from core.containers import ContainerManager

UA_ARC_PATH = "E:/Emulators/RomHacking/ZELDA/TP_UA/ISO/UA/root/res/Msgus/bmgres.arc"


def analyze_bmg_raw(data: bytes, label: str):
    print(f"\n  --- {label} BMG raw analysis ---")
    if data[:8] != b'MESGbmg1':
        print(f"  INVALID magic: {data[:8]!r}")
        return

    # Detect endianness
    size_le = struct.unpack_from('<I', data, 8)[0]
    size_be = struct.unpack_from('>I', data, 8)[0]
    se = '<' if size_le < size_be else '>'

    magic, total_size, num_sections, enc_val = struct.unpack_from(se + '8sIIB', data, 0)
    print(f"  total_size={total_size} (0x{total_size:X}), file_size={len(data)} (0x{len(data):X})")
    print(f"  num_sections={num_sections}, enc_val={enc_val}, endian={'BE' if se=='>' else 'LE'}")

    # Parse sections
    offset = 0x20
    sections = []
    while offset + 8 <= len(data):
        sec_magic, sec_len = struct.unpack_from(se + '4sI', data, offset)
        if sec_len == 0 or offset + sec_len > len(data):
            print(f"  Section at 0x{offset:X}: BAD sec_len={sec_len}")
            break
        name = sec_magic.decode('ascii', errors='replace')
        sections.append((name, offset, sec_len))
        print(f"  Section {name}: offset=0x{offset:X}, size={sec_len}")

        if name == 'INF1':
            count, entry_len, file_id = struct.unpack_from(se + 'HHI', data, offset + 8)
            print(f"    INF1: count={count}, entry_len={entry_len}, file_id={file_id}")
            # Compute expected INF1 size
            expected_sz = 16 + count * entry_len
            print(f"    Expected data size (without header): {count}*{entry_len}={count*entry_len}, actual sec payload={sec_len-8}")
        elif name == 'MID1':
            count, entry_len, unk = struct.unpack_from(se + 'HHI', data, offset + 8)
            print(f"    MID1: count={count}, entry_len={entry_len}, unk={unk}")
            # Compute expected
            data_bytes = sec_len - 16
            if count > 0:
                stride = data_bytes / count
                print(f"    Computed stride from section: {stride:.2f}")

        offset += sec_len


def main():
    print("=== UA Translation Archive Low-Level BMG Analysis ===")

    if not Path(UA_ARC_PATH).exists():
        print(f"Not found: {UA_ARC_PATH}")
        return

    raw = Path(UA_ARC_PATH).read_bytes()
    container = ContainerManager.open(raw)
    files = container.list_files()
    print(f"Files in archive: {files}")

    for fname in files:
        if fname.endswith('.bmg'):
            bmg_bytes = container.read_file(fname)
            print(f"\n=== {fname} (size={len(bmg_bytes)}) ===")
            analyze_bmg_raw(bmg_bytes, fname)


if __name__ == "__main__":
    main()
