import pytest
import struct
import hashlib
from core.containers import ContainerManager
from bmg_tool import BMGFile, BMGMessage

@pytest.fixture(scope="module")
def original_arc_bytes():
    """Generates a valid minimal U8 .arc archive containing a BMG file with messages."""
    # 1. Create BMG with three distinct messages
    bmg = BMGFile()
    bmg.endianness = '>'
    bmg.encoding = 'cp1252'
    bmg.id = 0
    
    msg0 = BMGMessage(info=b'\x00\x00\x00\x00', parts=["Hello World"])
    msg0.id = 100
    msg1 = BMGMessage(info=b'\x00\x00\x00\x00', parts=["Original Text"])
    msg1.id = 101
    msg2 = BMGMessage(info=b'\x00\x00\x00\x00', parts=["End of Messages"])
    msg2.id = 102
    
    bmg.messages = [msg0, msg1, msg2]
    bmg_bytes = bmg.save()
    
    # 2. Build a valid U8 container structure around it
    nodes_data = struct.pack(">H H I I", 0x0100, 0, 1, 2)  # Root
    nodes_data += struct.pack(">H H I I", 0x0000, 1, 0x60, len(bmg_bytes)) # test.bmg file
    str_table = b"\x00test.bmg\x00"
    
    header = struct.pack(">I I I I", 0x55AA382D, 0x20, len(nodes_data) + len(str_table), 0x60) + b"\x00" * 16
    
    data = bytearray(header + nodes_data + str_table)
    pad = (32 - len(data) % 32) % 32
    data += b"\x00" * pad  # Align to 32 bytes (data offset 0x60)
    
    data += bmg_bytes
    
    # Pad total archive
    total_pad = (32 - len(data) % 32) % 32
    data += b"\x00" * total_pad
    
    return bytes(data)

def test_modify_verify_and_revert_bmg_inside_arc(tmp_path, original_arc_bytes):
    """
    Combines modification, verification, and reverting of BMG file inside ARC
    to avoid race conditions when executing tests in parallel using pytest-xdist.
    """
    # Write the original archive to disk for later comparison
    original_path = tmp_path / "original.arc"
    original_path.write_bytes(original_arc_bytes)
    
    # 1. Unpack ARC in memory
    container = ContainerManager.open(original_arc_bytes)
    assert container is not None
    assert "test.bmg" in container.list_files()
    
    # Extract BMG bytes
    bmg_bytes = container.read_file("test.bmg")
    
    # Parse BMG file
    bmg = BMGFile()
    bmg.load(bmg_bytes)
    assert len(bmg.messages) == 3
    assert bmg.messages[1].id == 101
    
    # Modify Message 1 from "Original Text" to "Modified Text"
    bmg.messages[1].parts = ["Modified Text"]
    
    # Save BMG bytes back
    modified_bmg_bytes = bmg.save()
    
    # Put back in archive overlay
    container.write_file("test.bmg", modified_bmg_bytes)
    
    # Pack container back
    modified_arc_bytes = container.pack()
    assert len(modified_arc_bytes) > 0
    
    # Save modified ARC to temp directory
    modified_path = tmp_path / "modified.arc"
    modified_path.write_bytes(modified_arc_bytes)

    # Helper to convert BMGFile to JSON-like dict for deep comparison
    def bmg_to_dict(bmg_obj):
        return {
            "endianness": bmg_obj.endianness,
            "encoding": bmg_obj.encoding,
            "id": bmg_obj.id,
            "unk14": bmg_obj.unk14,
            "unk18": bmg_obj.unk18,
            "unk1C": bmg_obj.unk1C,
            "messages": [
                {
                    "id": getattr(msg, 'id', None),
                    "info": msg.info.hex(),
                    "is_null": msg.is_null,
                    "parts": msg.to_dict()["parts"]
                } for msg in bmg_obj.messages
            ]
        }

    # 2. Verify: Read both archives from disk and compare BMG structures
    original_arc_bytes_read = original_path.read_bytes()
    modified_arc_bytes_read = modified_path.read_bytes()
    
    container_orig = ContainerManager.open(original_arc_bytes_read)
    bmg_bytes_orig = container_orig.read_file("test.bmg")
    bmg_orig = BMGFile()
    bmg_orig.load(bmg_bytes_orig)
    orig_dict = bmg_to_dict(bmg_orig)

    container_mod = ContainerManager.open(modified_arc_bytes_read)
    bmg_bytes_mod = container_mod.read_file("test.bmg")
    bmg_mod = BMGFile()
    bmg_mod.load(bmg_bytes_mod)
    mod_dict = bmg_to_dict(bmg_mod)
    
    # Strict dict-level assertions to verify EXACTLY what was changed:
    # - Metadata fields must be absolutely identical
    assert mod_dict["endianness"] == orig_dict["endianness"]
    assert mod_dict["encoding"] == orig_dict["encoding"]
    assert mod_dict["id"] == orig_dict["id"]
    assert mod_dict["unk14"] == orig_dict["unk14"]
    assert mod_dict["unk18"] == orig_dict["unk18"]
    assert mod_dict["unk1C"] == orig_dict["unk1C"]
    
    # - Messages count must be identical
    assert len(mod_dict["messages"]) == len(orig_dict["messages"])
    
    # - Message 0 and Message 2 must be 100% identical (untouched)
    assert mod_dict["messages"][0] == orig_dict["messages"][0]
    assert mod_dict["messages"][2] == orig_dict["messages"][2]
    
    # - Message 1 (ID 101) must have identical ID, info, and is_null fields
    assert mod_dict["messages"][1]["id"] == orig_dict["messages"][1]["id"]
    assert mod_dict["messages"][1]["info"] == orig_dict["messages"][1]["info"]
    assert mod_dict["messages"][1]["is_null"] == orig_dict["messages"][1]["is_null"]
    
    # - Message 1 parts must have only the text changed
    assert mod_dict["messages"][1]["parts"] != orig_dict["messages"][1]["parts"]
    assert mod_dict["messages"][1]["parts"] == [{"type": "text", "value": "Modified Text"}]
    assert orig_dict["messages"][1]["parts"] == [{"type": "text", "value": "Original Text"}]
    
    # 3. Revert the change by MANUAL EDITING in the text
    bmg_mod.messages[1].parts = ["Original Text"]
    
    # Convert reverted BMG to dict and assert it matches original dict 100%
    reverted_dict = bmg_to_dict(bmg_mod)
    assert reverted_dict == orig_dict
    
    # Save reverted BMG to binary
    reverted_bmg_bytes = bmg_mod.save()
    
    # Overlay in archive
    container_mod.write_file("test.bmg", reverted_bmg_bytes)
    
    # Pack archive back
    reverted_arc_bytes = container_mod.pack()
    
    # Assert byte-perfect SHA-256 hash checksum identity
    def get_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
        
    orig_hash = get_sha256(original_arc_bytes_read)
    reverted_hash = get_sha256(reverted_arc_bytes)
    
    assert reverted_hash == orig_hash
    assert reverted_arc_bytes == original_arc_bytes_read
