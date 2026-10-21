"""A font descriptor's ``copies``: a save writes the font's block into the other game files that hold it."""
from core.font_formats import sources


def _page(fill: int) -> bytes:
    return bytes([fill]) * 0x42000


def test_save_writes_the_block_into_the_copy_and_nothing_else(tmp_path):
    source_root, translation_root = tmp_path / "source", tmp_path / "mod"
    (source_root / "BIN").mkdir(parents=True)
    (source_root / "BIN" / "F_GAME.BIN.pic").write_bytes(_page(0x11))
    (source_root / "BIN" / "F_GAME2.BIN.pic").write_bytes(_page(0x22))
    descriptors = [{"label": "Font", "format": "raw", "path": "BIN/F_GAME.BIN.pic",
                    "copies": [{"path": "BIN/F_GAME2.BIN.pic", "offset": "0x10000", "size": "0x2000"}]}]
    metadata = {"source_path": str(source_root), "translation_path": str(translation_root), "is_directory_mode": True}
    (found,) = sources.resolve(descriptors, metadata)
    assert len(found.copies) == 1

    edited = bytearray(_page(0x11))
    edited[0x10000:0x12000] = bytes([0x33]) * 0x2000
    found.write(bytes(edited))

    copy = (translation_root / "BIN" / "F_GAME2.BIN.pic").read_bytes()
    assert copy[0x10000:0x12000] == bytes([0x33]) * 0x2000
    assert copy[:0x10000] == _page(0x22)[:0x10000] and copy[0x12000:] == _page(0x22)[0x12000:]
    assert (translation_root / "BIN" / "F_GAME.BIN.pic").read_bytes() == bytes(edited)
    assert (source_root / "BIN" / "F_GAME2.BIN.pic").read_bytes() == _page(0x22)


def test_save_keeps_the_copy_edits_made_elsewhere_in_the_copy(tmp_path):
    source_root, translation_root = tmp_path / "source", tmp_path / "mod"
    (source_root / "BIN").mkdir(parents=True)
    (source_root / "BIN" / "F_GAME.BIN.pic").write_bytes(_page(0x11))
    (source_root / "BIN" / "F_GAME2.BIN.pic").write_bytes(_page(0x22))
    (translation_root / "BIN").mkdir(parents=True)
    other_edit = bytearray(_page(0x22))
    other_edit[0x30000] = 0x77                      # an earlier edit of the copy, outside the block
    (translation_root / "BIN" / "F_GAME2.BIN.pic").write_bytes(bytes(other_edit))
    descriptors = [{"label": "Font", "format": "raw", "path": "BIN/F_GAME.BIN.pic",
                    "copies": [{"path": "BIN/F_GAME2.BIN.pic", "offset": 0x10000, "size": 0x2000}]}]
    metadata = {"source_path": str(source_root), "translation_path": str(translation_root), "is_directory_mode": True}
    (found,) = sources.resolve(descriptors, metadata)
    found.write(_page(0x44))

    copy = (translation_root / "BIN" / "F_GAME2.BIN.pic").read_bytes()
    assert copy[0x30000] == 0x77
    assert copy[0x10000:0x12000] == bytes([0x44]) * 0x2000


def test_a_missing_copy_file_is_skipped(tmp_path):
    source_root, translation_root = tmp_path / "source", tmp_path / "mod"
    (source_root / "BIN").mkdir(parents=True)
    (source_root / "BIN" / "F_GAME.BIN.pic").write_bytes(_page(0x11))
    descriptors = [{"label": "Font", "format": "raw", "path": "BIN/F_GAME.BIN.pic",
                    "copies": [{"path": "BIN/F_GAME2.BIN.pic", "offset": "0x10000", "size": "0x2000"}]}]
    metadata = {"source_path": str(source_root), "translation_path": str(translation_root), "is_directory_mode": True}
    (found,) = sources.resolve(descriptors, metadata)
    assert found.copies == []
    found.write(_page(0x55))
    assert not (translation_root / "BIN" / "F_GAME2.BIN.pic").exists()
