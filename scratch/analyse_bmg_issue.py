import os
import struct as _s
import traceback
from pathlib import Path
from core.containers import ContainerManager
from bmg_tool import BMGFile


def extract_sections(data, endianness='>'):
    """Extract sections from raw BMG bytes, returning dict of name -> (offset, size, raw_bytes)."""
    sections = {}
    order = []
    off = 0x20
    while off + 8 <= len(data):
        mag, slen = _s.unpack_from(endianness + '4sI', data, off)
        if slen == 0 or off + slen > len(data):
            break
        name = mag.decode('ascii', errors='replace')
        sections[name] = (off, slen, data[off:off + slen])
        order.append(name)
        off += slen
    return sections, order


def main():
    eng_arc_path = "E:/Emulators/RomHacking/ZELDA/TP_UA/ISO/ENG/root/res/Msgus/bmgres.arc"

    print("=== Diagnostic BMG Analysis ===")

    if not os.path.exists(eng_arc_path):
        print(f"Error: Original archive not found at {eng_arc_path}")
        return

    raw_eng = Path(eng_arc_path).read_bytes()
    container_eng = ContainerManager.open(raw_eng)

    for filename in container_eng.list_files():
        if not filename.endswith(".bmg"):
            continue

        bmg_bytes = container_eng.read_file(filename)
        print(f"\n{'='*60}")
        print(f"Processing original {filename} (size: {len(bmg_bytes)} bytes)")

        try:
            bmg = BMGFile()
            bmg.load(bmg_bytes)
            print(f"  Loaded OK. Sections: {bmg.section_order}")
            print(f"  messages={len(bmg.messages)}, mid1_entry_len={bmg.mid1_entry_len}")
            has_int_ids = any(hasattr(m, 'id') and isinstance(getattr(m, 'id'), int)
                              for m in bmg.messages)
            print(f"  has_integer_ids={has_int_ids}")
            if bmg.messages:
                m0 = bmg.messages[0]
                print(f"  messages[0].id={repr(getattr(m0, 'id', 'N/A'))}")

            repacked_bytes = bmg.save()
            print(f"  Repacked size: {len(repacked_bytes)} (orig: {len(bmg_bytes)})")

            # Section-level comparison
            se = bmg.endianness
            orig_secs, orig_order = extract_sections(bmg_bytes, se)
            rep_secs, rep_order = extract_sections(repacked_bytes, se)

            all_names = list(dict.fromkeys(orig_order + rep_order))  # preserve order
            print(f"  Section breakdown:")
            total_diff = 0
            for name in all_names:
                o = orig_secs.get(name)
                r = rep_secs.get(name)
                o_sz = o[1] if o else 'MISSING'
                r_sz = r[1] if r else 'MISSING'
                same = (o is not None and r is not None and o[2] == r[2])
                flag = '[OK]' if same else '[DIFF]'
                size_diff = ''
                if isinstance(o_sz, int) and isinstance(r_sz, int) and o_sz != r_sz:
                    size_diff = f' (diff={r_sz - o_sz:+d})'
                    total_diff += (r_sz - o_sz)
                print(f"    {name}: orig={o_sz}, repacked={r_sz}{size_diff} {flag}")

            # Overall comparison
            if repacked_bytes == bmg_bytes:
                print(f"  [OK] Perfect roundtrip byte match!")
            else:
                if len(repacked_bytes) != len(bmg_bytes):
                    print(f"  [SIZE MISMATCH] {len(repacked_bytes)} vs {len(bmg_bytes)} (diff={len(repacked_bytes)-len(bmg_bytes):+d})")
                # Find first byte diff
                min_len = min(len(repacked_bytes), len(bmg_bytes))
                for i in range(min_len):
                    if repacked_bytes[i] != bmg_bytes[i]:
                        ctx_s = max(0, i - 4)
                        ctx_e = min(min_len, i + 12)
                        print(f"  [FAIL] First diff @ offset {i} (0x{i:X}):")
                        print(f"    orig[{ctx_s}:{ctx_e}]    = {bmg_bytes[ctx_s:ctx_e].hex()}")
                        print(f"    repacked[{ctx_s}:{ctx_e}] = {repacked_bytes[ctx_s:ctx_e].hex()}")
                        break

        except Exception as e:
            print(f"  EXCEPTION: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
