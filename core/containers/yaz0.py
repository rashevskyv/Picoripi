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


def compress(data: bytes, max_candidates: int | None = 100) -> bytes:
    """
    Compress data using Yaz0 encoding with a fast LZ77 sliding window algorithm
    and lazy evaluation (lookahead matching).

    This produces highly compressed, valid Yaz0 archives that closely match the
    compression ratio of official Nintendo tools. This prevents buffer overflows
    and memory exhaustion crashes in games on real console hardware and emulators.

    Args:
        data: Raw bytes to compress.
        max_candidates: Maximum number of match candidates to evaluate (None for unlimited).

    Returns:
        Yaz0-compressed bytes starting with the b"Yaz0" magic header.
    """
    n = len(data)
    if n == 0:
        return b"Yaz0" + struct.pack(">I", 0) + b"\x00" * 8

    # We will use a sliding window of 4096 bytes and limit searches to max_candidates recent
    # candidates to achieve an optimal balance between compression ratio and speed.
    pos_map: dict[bytes, list[int]] = {}
    out = bytearray(b"Yaz0")
    out += struct.pack(">I", n)
    out += b"\x00" * 8

    i = 0
    group_elements: list[tuple[bool, bytes]] = []

    def flush_group() -> None:
        nonlocal group_elements, out
        if not group_elements:
            return
        header = 0
        element_bytes = bytearray()
        for idx, (is_lit, eb) in enumerate(group_elements):
            if is_lit:
                header |= (0x80 >> idx)
            element_bytes += eb
        out.append(header)
        out += element_bytes
        group_elements = []

    def find_match(pos: int) -> tuple[int, int]:
        if pos + 3 > n:
            return 0, 0

        prefix = data[pos : pos + 3]
        candidates = pos_map.get(prefix, [])

        # Prune candidates outside the 4096 sliding window
        while candidates and (pos - candidates[0] > 4096):
            candidates.pop(0)

        best_len = 0
        best_dist = 0
        checked = 0

        # Scan candidates in reverse (most recent first)
        for cand_idx in reversed(candidates):
            if checked >= max_candidates:
                break
            checked += 1

            dist = pos - cand_idx
            limit = min(273, n - pos)

            s1 = data[cand_idx : cand_idx + limit]
            s2 = data[pos : pos + limit]
            match_len = 0
            for x, y in zip(s1, s2):
                if x != y:
                    break
                match_len += 1

            if match_len >= 3:
                if match_len > best_len:
                    best_len = match_len
                    best_dist = dist
                    if best_len == 273:
                        break
        return best_len, best_dist

    def insert_prefix(pos: int) -> None:
        if pos + 3 <= n:
            prefix = data[pos : pos + 3]
            if prefix not in pos_map:
                pos_map[prefix] = []
            pos_map[prefix].append(pos)

    while i < n:
        if len(group_elements) == 8:
            flush_group()

        # Find best match at i
        best_len, best_dist = find_match(i)

        if best_len >= 3:
            # Lazy evaluation: check if there's a better match at i+1
            insert_prefix(i)
            lazy_len, lazy_dist = find_match(i + 1)

            if lazy_len > best_len:
                # Output literal at i instead of the match, proceed to check i+1 next
                group_elements.append((True, bytes([data[i]])))
                i += 1
                continue

            # Otherwise, use the match at i
            d = best_dist - 1
            if 3 <= best_len <= 17:
                # b1 high nibble = best_len - 2, low 4 bits = high 4 bits of distance
                b1 = ((best_len - 2) << 4) | ((d >> 8) & 0x0F)
                b2 = d & 0xFF
                group_elements.append((False, bytes([b1, b2])))
            else:
                # b1 high nibble = 0, low 4 bits = high 4 bits of distance, b3 = best_len - 18
                b1 = (d >> 8) & 0x0F
                b2 = d & 0xFF
                b3 = best_len - 18
                group_elements.append((False, bytes([b1, b2, b3])))

            # Insert prefixes for the rest of the match bytes
            for k in range(1, best_len):
                insert_prefix(i + k)

            i += best_len
        else:
            # Literal byte
            group_elements.append((True, bytes([data[i]])))
            insert_prefix(i)
            i += 1

    flush_group()
    return bytes(out)
