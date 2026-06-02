import pytest
import struct
from pathlib import Path
from core.containers import ContainerManager
from core.containers.yaz0 import compress, decompress
from core.containers.rarc_container import RarcContainer
from core.containers.u8_container import U8Container

def test_yaz0_roundtrip():
    # Test simple compression and decompression
    data = b"Hello world! This is a test string to check Yaz0 compression and decompression."
    compressed = compress(data)
    assert compressed.startswith(b"Yaz0")
    decompressed = decompress(compressed)
    assert decompressed == data

def test_yaz0_back_reference_decompression():
    # Construct a custom Yaz0 stream that uses a back-reference
    # We want to decompress: b"A" * 20
    # Uncompressed size: 20
    # Header: "Yaz0", size=20, padding=8 zeros
    # Group header: 0x80 (10000000 binary)
    # bit 0: literal -> b"A"
    # bit 1: back-reference -> distance=1 (DDSS = 0x0000 -> dist=((0&0x0F)<<8|0)+1 = 1)
    #                          count: high nibble of D is 0, so count is read from next byte
    #                          Let's use D high nibble != 0 for simplicity.
    #                          For DDSS = 0x1000 (D=0x10, S=0x00), high nibble of D is 1.
    #                          count = 1 + 2 = 3.
    #                          If we want count=19, we can use D=0x00, S=0x00, count_byte=1.
    #                          Wait, D=0x00, S=0x00, count_byte = 19 - 18 = 1.
    #                          So back-ref bytes: 0x00, 0x00, 0x01.
    #                          Let's check: DDSS = 0x0000. dist = 1. High nibble is 0. Next byte is 0x01. count = 1 + 18 = 19.
    #                          This will repeat b"A" 19 times. Total size = 1 + 19 = 20.
    # Group header: 0x80 (bit 0 = 1, bit 1 = 0, others don't matter since dst_pos reaches uncompressed_size)
    header = b"Yaz0" + struct.pack(">I", 20) + b"\x00" * 8
    compressed_data = header + b"\x80" + b"A" + b"\x00\x00\x01"
    
    decompressed = decompress(compressed_data)
    assert decompressed == b"A" * 20

def test_container_manager_autodetect():
    # Test RARC detection
    rarc_data = b"RARC" + b"\x00" * 28
    assert ContainerManager.is_supported(rarc_data) is True
    
    # Test U8 detection
    u8_data = b"\x55\xaa\x38\x2d" + b"\x00" * 28
    assert ContainerManager.is_supported(u8_data) is True
    
    # Test Yaz0-wrapped RARC detection
    wrapped_rarc = compress(rarc_data)
    assert ContainerManager.is_supported(wrapped_rarc) is True
    
    # Test unsupported
    assert ContainerManager.is_supported(b"MZ\x00\x00") is False

def test_rarc_container():
    test_arc_path = Path("scratch/test.arc")
    if not test_arc_path.exists():
        pytest.skip("scratch/test.arc not found")
        
    raw = test_arc_path.read_bytes()
    container = ContainerManager.open(raw)
    assert isinstance(container, RarcContainer)
    
    files = container.list_files()
    assert len(files) > 0
    
    # Test read_file
    first_file = files[0]
    content = container.read_file(first_file)
    assert len(content) >= 0
    
    # Test write_file overlay
    new_content = b"TEST OVERLAY CONTENT"
    container.write_file(first_file, new_content)
    assert container.read_file(first_file) == new_content
    
    # Test pack roundtrip
    packed = container.pack()
    assert len(packed) > 0
    
    # Parse packed again
    new_container = ContainerManager.open(packed)
    assert new_container.read_file(first_file) == new_content

def test_u8_container_pack_empty():
    # Create a minimal valid U8 archive in memory
    # Header: magic (0x55AA382D), root_off (0x20), hdr_size (12 nodes + 1 byte str table), data_off (0x40)
    # Root node: typ=0x0100 (dir), name_off=0, first_child=1, last_child=1 (no children, only root node)
    header = struct.pack(">I I I I", 0x55AA382D, 0x20, 12 + 1, 0x40) + b"\x00" * 16
    root_node = struct.pack(">H H I I", 0x0100, 0, 1, 1)
    str_table = b"\x00"
    data = header + root_node + str_table + b"\x00" * 0x13 # pad to 0x40
    
    container = U8Container(data)
    assert container.list_files() == []
    
    # Test pack without overlay
    packed = container.pack()
    assert packed[:4] == b"\x55\xaa\x38\x2d"

def test_u8_container_with_files():
    # Let's build a mock U8 container with one file
    # Root node (idx 0): dir, name_off=0, first_child=1, last_child=2
    # File node (idx 1): file, name_off=1 (name "test.txt"), data_off=0x40 (offset of data), size=5
    # Str table: \x00 (root name) + "test.txt" + \x00
    # Header size: 2 * 12 (nodes) + 10 (string table) = 34 bytes
    # data_off: 0x20 (header) + 34 (hdr) = 66 -> pad to 32 boundary -> 96 (0x60)
    
    nodes_data = struct.pack(">H H I I", 0x0100, 0, 1, 2)  # Root
    nodes_data += struct.pack(">H H I I", 0x0000, 1, 0x60, 5) # File test.txt, offset 0x60, size 5
    str_table = b"\x00test.txt\x00"
    
    header = struct.pack(">I I I I", 0x55AA382D, 0x20, len(nodes_data) + len(str_table), 0x60) + b"\x00" * 16
    
    data = bytearray(header + nodes_data + str_table)
    pad = (32 - len(data) % 32) % 32
    data += b"\x00" * pad  # Should reach 0x60 (96 bytes)
    assert len(data) == 0x60
    
    data += b"HELLO" # File data
    data += b"\x00" * 27 # Alignment padding
    
    container = U8Container(bytes(data))
    assert container.list_files() == ["test.txt"]
    assert container.read_file("test.txt") == b"HELLO"
    
    # Test modify file
    container.write_file("test.txt", b"WORLD")
    assert container.read_file("test.txt") == b"WORLD"
    
    packed = container.pack()
    new_container = U8Container(packed)
    assert new_container.list_files() == ["test.txt"]
    assert new_container.read_file("test.txt") == b"WORLD"


def test_yaz0_compression_ratio_against_original():
    # If the original file exists, let's check our compression ratio.
    original_path = Path(r"e:\Emulators\RomHacking\ZELDA\TP_UA\ISO\ENG\root\res\Msgus\bmgres.arc")
    if not original_path.exists():
        pytest.skip("Original ENG bmgres.arc not found. Skipping ratio test.")

    raw_original = original_path.read_bytes()
    decompressed = decompress(raw_original)

    compressed_new = compress(decompressed)

    # Size should be extremely close (within 3% of the original highly optimized size)
    ratio = len(compressed_new) / len(raw_original)
    assert ratio < 1.03, f"Compression ratio is too high: {ratio:.2%}. Size was {len(compressed_new)} instead of {len(raw_original)}"

    # Ensure it is 100% losslessly decompressible back to the same data
    decompressed_new = decompress(compressed_new)
    assert decompressed_new == decompressed
