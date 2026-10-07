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


def test_yaz0_run_that_overlaps_itself_and_is_cut_by_the_size():
    # Two literals "AB", then a run of 19 bytes at distance 2 into a 12-byte output.
    header = b"Yaz0" + struct.pack(">I", 12) + b"\x00" * 8
    assert decompress(header + b"\xC0" + b"AB" + b"\x00\x01\x01") == b"AB" * 6


def test_yaz0_group_of_eight_literals():
    header = b"Yaz0" + struct.pack(">I", 9) + b"\x00" * 8
    assert decompress(header + b"\xFF" + b"ABCDEFGH" + b"\x80" + b"I") == b"ABCDEFGHI"

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
    original_path = Path(r"E:\Emulators\RomHacking\Zelda\Twilight Princess\GC + Wii\ISO\ENG\root\res\Msgus\bmgres.arc")
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


def test_yaz0_limit_decompresses_only_the_first_bytes():
    data = b"RARC" + bytes(range(256)) * 40
    assert decompress(compress(data), limit=4) == b"RARC"
    assert RarcContainer.can_handle(compress(data)) is True
    assert U8Container.can_handle(compress(data)) is False


def test_u8_directories_hold_the_nodes_after_them():
    # root (0) -> dir "arc" (1, parent 0) -> dir "timg" (2, parent 1) -> file "a.tpl" (3); file "b.bin" (4) in root.
    names = b"\x00arc\x00timg\x00a.tpl\x00b.bin\x00"
    nodes = [(0x0100, 0, 0, 5), (0x0100, 1, 0, 4), (0x0100, 5, 1, 4), (0x0000, 10, 0, 3), (0x0000, 16, 0, 2)]
    header_size = 12 * len(nodes) + len(names)
    data_off = (0x20 + header_size + 31) & ~31
    contents = {3: b"AAA", 4: b"BB"}
    blob, offsets = b"", {}
    for index in (3, 4):
        offsets[index] = data_off + len(blob)
        blob += contents[index] + bytes(-len(contents[index]) % 32)
    table = b"".join(struct.pack(">HHII", typ | 0, name, offsets.get(i, start), size)
                     for i, (typ, name, start, size) in enumerate(nodes))
    head = struct.pack(">IIII", 0x55AA382D, 0x20, header_size, data_off) + bytes(16) + table + names
    archive = U8Container(head + bytes(data_off - len(head)) + blob)
    assert sorted(archive.list_files()) == ["arc/timg/a.tpl", "b.bin"]
    assert archive.read_file("arc/timg/a.tpl") == b"AAA"


def test_u8_folders_list_their_children_and_an_unedited_repack_keeps_every_byte():
    # As Nintendo writes it: a folder's data_off is its parent index, its children follow it; no padding
    # after the last file (Skyward Sword's archives).
    names = b"\x00dir\x00a.txt\x00b.txt\x00"
    nodes = struct.pack(">III", 0x01000000, 0, 4)                   # root, 4 nodes
    nodes += struct.pack(">III", 0x01000000 | 1, 0, 4)              # dir/ (parent 0, ends at 4)
    nodes += struct.pack(">III", 5, 0x80, 3)                        # dir/a.txt
    nodes += struct.pack(">III", 11, 0xA0, 2)                       # dir/b.txt
    head = struct.pack(">IIII", 0x55AA382D, 0x20, len(nodes) + len(names), 0x80) + b"\x00" * 16
    data = head + nodes + names
    data += b"\x00" * (0x80 - len(data)) + b"one" + b"\x00" * 29 + b"tw"
    container = U8Container(data)
    assert container.list_files() == ["dir/a.txt", "dir/b.txt"]
    container.write_file("dir/a.txt", b"one")
    assert container.pack() == data
    container.write_file("dir/a.txt", b"longer than one")
    again = U8Container(container.pack())
    assert again.read_file("dir/a.txt") == b"longer than one" and again.read_file("dir/b.txt") == b"tw"
