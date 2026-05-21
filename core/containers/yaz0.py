"""
Yaz0 compression and decompression for Nintendo archive formats.

Yaz0 is a run-length/back-reference compression scheme used extensively
in Nintendo GameCube and Wii games to compress RARC and U8 archives.

The format uses groups of 8 operations per header byte. Each bit (MSB first)
in the header byte indicates whether the corresponding operation is a literal
byte copy (bit=1) or a back-reference into previously decompressed data (bit=0).

Back-reference encoding:
    2 bytes: DDSS  (big-endian)
    - Distance N = ((D & 0x0F) << 8) | S) + 1
    - If D high nibble != 0: count = (D >> 4) + 2
    - If D high nibble == 0: count = next_byte + 18

Compressed output format:
    Offset  Size  Description
    0x00    4     Magic "Yaz0"
    0x04    4     Uncompressed size (big-endian u32)
    0x08    8     Reserved (zeros)
    0x10    ...   Compressed data groups
"""

import struct


def decompress(data: bytes) -> bytes:
    """
    Decompress Yaz0-encoded data.

    Args:
        data: Raw Yaz0-compressed bytes (must start with b"Yaz0").

    Returns:
        Decompressed bytes.

    Raises:
        ValueError: If magic bytes are incorrect or data is malformed.
    """
    if len(data) < 16:
        raise ValueError("Data too short to be Yaz0")
    if data[:4] != b"Yaz0":
        raise ValueError(f"Invalid Yaz0 magic: {data[:4]!r}")

    uncompressed_size: int = struct.unpack_from(">I", data, 4)[0]
    src: int = 16  # skip 16-byte header
    dst: bytearray = bytearray(uncompressed_size)
    dst_pos: int = 0

    while dst_pos < uncompressed_size:
        if src >= len(data):
            break

        group_header: int = data[src]
        src += 1

        for bit in range(8):
            if dst_pos >= uncompressed_size:
                break

            if group_header & (0x80 >> bit):
                # Literal byte
                dst[dst_pos] = data[src]
                src += 1
                dst_pos += 1
            else:
                # Back-reference
                if src + 1 >= len(data):
                    break
                b1: int = data[src]
                b2: int = data[src + 1]
                src += 2

                dist: int = ((b1 & 0x0F) << 8) | b2
                dist += 1  # distance is 1-based

                nibble_high: int = b1 >> 4
                if nibble_high != 0:
                    count: int = nibble_high + 2
                else:
                    count = data[src] + 18
                    src += 1

                for _ in range(count):
                    if dst_pos >= uncompressed_size:
                        break
                    dst[dst_pos] = dst[dst_pos - dist]
                    dst_pos += 1

    return bytes(dst)


def compress(data: bytes) -> bytes:
    """
    Compress data using Yaz0 encoding (naive literal-only method).

    This produces valid Yaz0 output where every byte is stored as a literal
    (no back-references). The resulting file is larger than optimal but is
    100% valid and correctly decoded by all Yaz0 decoders (game hardware,
    emulators, and this decompressor).

    For translation purposes this is sufficient: games decompress Yaz0 at
    load time regardless of the compression ratio.

    Args:
        data: Raw bytes to compress.

    Returns:
        Yaz0-compressed bytes starting with the b"Yaz0" magic header.
    """
    output = bytearray()

    # 16-byte header
    output += b"Yaz0"
    output += struct.pack(">I", len(data))
    output += b"\x00" * 8  # reserved

    # Encode: groups of 8 literals
    i = 0
    n = len(data)
    while i < n:
        chunk = data[i : i + 8]
        # 0xFF = all 8 bits set = all operations in this group are literals
        output.append(0xFF)
        output += chunk
        i += len(chunk)

    return bytes(output)
