#!/usr/bin/env python3
import os
import sys
import struct
import json

# Supported encodings
ENCODINGS = {
    1: 'cp1252',
    2: 'utf-16',
    3: 'shift_jis',
    4: 'utf-8'
}

ENCODINGS_REV = {v: k for k, v in ENCODINGS.items()}

class BMGMessage:
    def __init__(self, info=b'', parts=None, is_null=False):
        self.info = info
        self.parts = parts if parts is not None else []
        self.is_null = is_null

    def to_dict(self):
        parts_json = []
        for part in self.parts:
            if isinstance(part, str):
                parts_json.append({"type": "text", "value": part})
            elif isinstance(part, dict):  # escape tag
                parts_json.append(part)
        return {
            "info": self.info.hex(),
            "is_null": self.is_null,
            "parts": parts_json
        }

    @classmethod
    def from_dict(cls, d):
        parts = []
        for p in d.get("parts", []):
            if p.get("type") == "text":
                parts.append(p["value"])
            elif p.get("type") == "escape":
                parts.append({
                    "type": "escape",
                    "escape_type": p["escape_type"],
                    "data": p["data"]
                })
        return cls(
            info=bytes.fromhex(d.get("info", "")),
            parts=parts,
            is_null=d.get("is_null", False)
        )

class BMGFile:
    def __init__(self):
        self.endianness = '>'  # Big endian by default for GameCube
        self.encoding = 'utf-16'
        self.id = 0
        self.unk14 = 0
        self.unk18 = 0
        self.unk1C = 0
        self.messages = []
        self.section_order = []
        self.other_sections = {}
        self.mid1_entry_len = 4   # bytes per MID1 entry (0 = packed, computed at load)
        self.mid1_unk = 0         # unknown field in MID1 header

    def get_full_encoding(self):
        if self.encoding.lower() == 'utf-16':
            return 'utf-16-le' if self.endianness == '<' else 'utf-16-be'
        return self.encoding

    def load(self, data: bytes):
        if data[:8] != b'MESGbmg1':
            raise ValueError("Invalid magic header. Not a BMG file!")

        # Determine endianness based on total file size field
        size_le, = struct.unpack_from('<I', data, 8)
        size_be, = struct.unpack_from('>I', data, 8)
        self.endianness = se = '<' if size_le < size_be else '>'

        # Header fields
        magic, total_size, num_sections, enc_val, self.unk14, self.unk18, self.unk1C = \
            struct.unpack_from(se + '8sIIB3I', data, 0)

        if enc_val in ENCODINGS:
            self.encoding = ENCODINGS[enc_val]
        else:
            raise ValueError(f"Unknown encoding ID: {enc_val}")

        # Parse sections
        offset = 0x20
        inf_entries = []
        dat_data = b''
        mid_entries = []
        self.section_order = []
        self.other_sections = {}
        self.original_num_sections = num_sections
        self.original_total_size = total_size  # preserve for exact roundtrip

        while offset < len(data):
            if offset + 8 > len(data):
                break
            sec_magic, sec_len = struct.unpack_from(se + '4sI', data, offset)
            if sec_len == 0 or offset + sec_len > len(data):
                break
            sec_data = data[offset : offset + sec_len]
            
            try:
                magic_str = sec_magic.decode('ascii', errors='ignore')
            except Exception:
                magic_str = f"SEC{len(self.section_order)}"
                
            self.section_order.append(magic_str)

            if sec_magic == b'INF1':
                count, entry_len, self.id = struct.unpack_from(se + 'HHI', sec_data, 8)
                for i in range(count):
                    entry_offset = 16 + i * entry_len
                    str_offset, = struct.unpack_from(se + 'I', sec_data, entry_offset)
                    attribs = sec_data[entry_offset + 4 : entry_offset + entry_len]
                    inf_entries.append((str_offset, attribs))

            elif sec_magic == b'DAT1':
                dat_data = sec_data[8:]

            elif sec_magic == b'MID1':
                count, entry_len, unk = struct.unpack_from(se + 'HHI', sec_data, 8)
                self.mid1_unk = unk
                # entry_len == 0 is a Twilight Princess quirk: IDs are stored
                # contiguously after the 16-byte header. Compute real stride.
                if entry_len == 0 and count > 0:
                    data_bytes = len(sec_data) - 16
                    computed = data_bytes // count
                    # Only trust if it divides cleanly into a sensible size
                    real_entry_len = computed if computed in (4, 8) else 4
                else:
                    real_entry_len = entry_len if entry_len > 0 else 4
                self.mid1_entry_len = real_entry_len
                # Also preserve the original header value for exact roundtrip
                self._mid1_entry_len_header = entry_len
                for i in range(count):
                    entry_offset = 16 + i * real_entry_len
                    if real_entry_len == 4:
                        msg_id, = struct.unpack_from(se + 'I', sec_data, entry_offset)
                        mid_entries.append(msg_id)
                    else:
                        mid_entries.append(sec_data[entry_offset : entry_offset + real_entry_len].hex())
            else:
                self.other_sections[magic_str] = bytes(sec_data)

            offset += sec_len

        # Preserve any trailing bytes after the last known section for exact roundtrip
        self.trailing_data = bytes(data[offset:]) if offset < len(data) else b''

        # Parse messages
        full_enc = self.get_full_encoding()
        null_char = '\0'.encode(full_enc)
        esc_char = '\x1A'.encode(full_enc)

        self.messages = []
        for idx, (str_offset, attribs) in enumerate(inf_entries):
            if str_offset >= len(dat_data):
                self.messages.append(BMGMessage(attribs, is_null=True))
                continue

            parts = []
            curr_pos = str_offset
            curr_str_start = str_offset

            while curr_pos < len(dat_data):
                next_bytes = dat_data[curr_pos : curr_pos + len(null_char)]
                if next_bytes == null_char:
                    break

                if next_bytes == esc_char:
                    # Flush previous string
                    if curr_str_start < curr_pos:
                        parts.append(dat_data[curr_str_start:curr_pos].decode(full_enc))

                    # Parse escape tag
                    esc_start_pos = curr_pos
                    esc_len = dat_data[curr_pos + len(esc_char)]
                    esc_type = dat_data[curr_pos + len(esc_char) + 1]
                    esc_data = dat_data[curr_pos + len(esc_char) + 2 : curr_pos + esc_len]

                    parts.append({
                        "type": "escape",
                        "escape_type": esc_type,
                        "data": esc_data.hex()
                    })

                    curr_pos += esc_len
                    curr_str_start = curr_pos
                else:
                    curr_pos += len(null_char)

            if curr_str_start < curr_pos:
                parts.append(dat_data[curr_str_start:curr_pos].decode(full_enc))

            msg = BMGMessage(attribs, parts)
            # Associate ID if MID1 section exists
            if idx < len(mid_entries):
                msg.id = mid_entries[idx]
            self.messages.append(msg)

    def save(self) -> bytes:
        se = self.endianness
        full_enc = self.get_full_encoding()
        null_char = '\0'.encode(full_enc)
        esc_char = '\x1A'.encode(full_enc)

        inf1 = bytearray(16)
        dat1 = bytearray(8)
        mid1 = bytearray(16)

        # First entry in DAT1 is always a null character
        dat1.extend(null_char)

        entry_len = 4
        if self.messages:
            entry_len += len(self.messages[0].info)

        has_ids = any(hasattr(m, 'id') and isinstance(getattr(m, 'id'), int) for m in self.messages)
        mid1_entry_len = getattr(self, 'mid1_entry_len', 4)
        mid1_unk = getattr(self, 'mid1_unk', 0)
        # Preserve original MID1 header entry_len value for exact roundtrip
        mid1_entry_len_header = getattr(self, '_mid1_entry_len_header', mid1_entry_len)

        for idx, msg in enumerate(self.messages):
            if msg.is_null:
                inf1.extend(struct.pack(se + 'I', 0))
                inf1.extend(msg.info)
                if has_ids:
                    # Write a zero ID for null messages to maintain index alignment
                    mid1.extend(struct.pack(se + 'I', 0))
                continue

            # Offset is relative to the start of DAT1 data section (after its 8-byte header)
            str_offset = len(dat1) - 8
            inf1.extend(struct.pack(se + 'I', str_offset))
            inf1.extend(msg.info)

            # Build and append message string with escape tags
            for part in msg.parts:
                if isinstance(part, str):
                    dat1.extend(part.encode(full_enc))
                elif isinstance(part, dict) and part.get("type") == "escape":
                    esc_type = part["escape_type"]
                    esc_data = bytes.fromhex(part["data"])
                    esc_len = len(esc_char) + 2 + len(esc_data)

                    dat1.extend(esc_char)
                    dat1.append(esc_len)
                    dat1.append(esc_type)
                    dat1.extend(esc_data)

            dat1.extend(null_char)

            # Build MID1 entry if file has message IDs
            if has_ids:
                msg_id = getattr(msg, 'id', idx)
                if isinstance(msg_id, int):
                    mid1.extend(struct.pack(se + 'I', msg_id))
                else:
                    # Fallback: pad with zeros
                    mid1.extend(b'\x00' * mid1_entry_len)

        # Pad sections to 32 bytes
        while len(inf1) % 32 != 0:
            inf1.append(0)
        while len(dat1) % 32 != 0:
            dat1.append(0)
        while len(mid1) % 32 != 0:
            mid1.append(0)

        # Fill headers
        struct.pack_into(se + '4sIHHI', inf1, 0, b'INF1', len(inf1), len(self.messages), entry_len, self.id)
        struct.pack_into(se + '4sI', dat1, 0, b'DAT1', len(dat1))

        # Assemble file
        num_sections = 0
        out_data = bytearray(0x20)

        # Decide order of sections
        sections_to_write = list(self.section_order) if getattr(self, 'section_order', None) else ['INF1', 'DAT1', 'MID1']
        
        # Ensure we always write INF1 and DAT1
        if 'INF1' not in sections_to_write:
            sections_to_write.append('INF1')
        if 'DAT1' not in sections_to_write:
            sections_to_write.append('DAT1')
        
        # MID1 check
        if has_ids:
            if 'MID1' not in sections_to_write:
                # Insert after DAT1
                try:
                    idx = sections_to_write.index('DAT1')
                    sections_to_write.insert(idx + 1, 'MID1')
                except ValueError:
                    sections_to_write.append('MID1')
        else:
            if 'MID1' in sections_to_write:
                sections_to_write.remove('MID1')

        for sec_name in sections_to_write:
            if sec_name == 'INF1':
                out_data.extend(inf1)
                num_sections += 1
            elif sec_name == 'DAT1':
                out_data.extend(dat1)
                num_sections += 1
            elif sec_name == 'MID1':
                struct.pack_into(se + '4sIHHI', mid1, 0, b'MID1', len(mid1), len(self.messages),
                                 mid1_entry_len_header, mid1_unk)
                out_data.extend(mid1)
                num_sections += 1
            elif sec_name in getattr(self, 'other_sections', {}):
                out_data.extend(self.other_sections[sec_name])
                num_sections += 1

        # Pad total file to 32-byte alignment
        real_total_size = len(out_data)
        while real_total_size % 32 != 0:
            out_data.append(0)
            real_total_size += 1

        # Append any trailing bytes preserved from the original file
        trailing = getattr(self, 'trailing_data', b'')
        if trailing:
            out_data.extend(trailing)

        # Write global file header
        # Use original total_size if it was preserved, for exact roundtrip.
        # NOTE: In Twilight Princess BMGs the total_size field does not always
        # reflect the on-disk size (e.g. it may exclude padding/FLW1 sections).
        # We preserve the original value to avoid corrupting the header.
        enc_id = ENCODINGS_REV.get(self.encoding, 2)
        header_sections_count = getattr(self, 'original_num_sections', num_sections)
        orig_total = getattr(self, 'original_total_size', None)
        header_total_size = orig_total if orig_total is not None else real_total_size
        struct.pack_into(se + '8sIIB3I', out_data, 0, b'MESGbmg1', header_total_size, header_sections_count, enc_id, self.unk14, self.unk18, self.unk1C)

        return bytes(out_data)

def main():
    if len(sys.argv) < 4:
        print("Nintendo BMG Tool - Proof of Concept Unpacker/Repacker")
        print("Usage:")
        print("  python bmg_tool.py extract <input.bmg> <output.json>")
        print("  python bmg_tool.py repack <input.json> <output.bmg>")
        sys.exit(1)

    mode = sys.argv[1]
    input_path = sys.argv[2]
    output_path = sys.argv[3]

    if mode == "extract":
        print(f"Extracting {input_path} to {output_path}...")
        with open(input_path, 'rb') as f:
            data = f.read()

        bmg = BMGFile()
        bmg.load(data)

        # Prepare JSON structure
        out_dict = {
            "endianness": bmg.endianness,
            "encoding": bmg.encoding,
            "id": bmg.id,
            "unk14": bmg.unk14,
            "unk18": bmg.unk18,
            "unk1C": bmg.unk1C,
            "messages": [msg.to_dict() for msg in bmg.messages]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(out_dict, f, ensure_ascii=False, indent=2)
        print("Extraction completed successfully!")

    elif mode == "repack":
        print(f"Repacking {input_path} to {output_path}...")
        with open(input_path, 'r', encoding='utf-8') as f:
            in_dict = json.load(f)

        bmg = BMGFile()
        bmg.endianness = in_dict.get("endianness", ">")
        bmg.encoding = in_dict.get("encoding", "utf-16")
        bmg.id = in_dict.get("id", 0)
        bmg.unk14 = in_dict.get("unk14", 0)
        bmg.unk18 = in_dict.get("unk18", 0)
        bmg.unk1C = in_dict.get("unk1C", 0)

        for m_dict in in_dict.get("messages", []):
            msg = BMGMessage.from_dict(m_dict)
            if "id" in m_dict:
                msg.id = m_dict["id"]
            bmg.messages.append(msg)

        out_data = bmg.save()
        with open(output_path, 'wb') as f:
            f.write(out_data)
        print("Repacking completed successfully!")

    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)

if __name__ == '__main__':
    main()
