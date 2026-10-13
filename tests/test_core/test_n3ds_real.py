"""Decrypted Nintendo 3DS programs of the owner's RomHacking workspace: no key is needed, and every workspace file of the
program equals the file the image holds (same size and sha256).

Needs ``PICORIPI_ROMHACKING`` (see tests/romhacking_root.py). Read only: nothing is written to the workspace.
"""
import hashlib

import romhacking_root
from core.containers.image_files import copy_range
from core.project_library import images

MM3D_CXI = ("Zelda", "Majoras Mask", "3D - 3DS", "image", "Majora's Mask 3D (decrypted).cxi")
MM3D_UPDATE_CIA = ("Zelda", "Majoras Mask", "3D - 3DS", "image", "Majora's Mask 3D Update (decrypted).cia")
MM3D_WORKSPACE = ("Zelda", "Majoras Mask", "3D - 3DS")


class _Hash:
    """A write target for ``copy_range`` that only hashes."""

    def __init__(self):
        self.digest = hashlib.sha256()

    def write(self, data):
        self.digest.update(data)
        return len(data)


def _sha_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# Workspace files the image does not hold as stored: ``exefs/exheader.bin`` (3dstool copies the exheader there too),
# ``romfs/version.ctxb`` (not in the RomFS), and ``exefs/code.bin`` (the image stores the code compressed; the workspace
# holds it decompressed, and Picoripi does not decompress ExeFS code yet).
NOT_STORED_AS_IS = {"exefs/exheader.bin", "romfs/version.ctxb", "exefs/code.bin"}
# The workspace icon differs from the image after byte 12480 (an edit of the workspace copy); its SMDH header and the
# first 12480 bytes are compared.
PREFIX_ONLY = {"exefs/icon.bin": 12480}


def _program_files(workspace):
    """The workspace files that the program's exheader, ExeFS and RomFS hold as stored: ``{relative path: file}``."""
    files = {}
    for path in workspace.rglob("*"):
        rel = path.relative_to(workspace).as_posix()
        if path.is_file() and rel not in NOT_STORED_AS_IS and (rel == "exheader.bin" or rel.startswith(("exefs/", "romfs/"))):
            files[rel] = path
    return files


@romhacking_root.needs(MM3D_CXI, MM3D_WORKSPACE)
def test_majoras_mask_decrypted_cxi_matches_the_workspace_program_files():
    workspace = romhacking_root.path(*MM3D_WORKSPACE)
    wanted = _program_files(workspace)
    assert wanted, "the workspace holds no program files"
    image = romhacking_root.path(*MM3D_CXI)

    assert images.identify(image)["encrypted"] is False
    with images.open_image(image) as reader:
        listed = {entry.path: entry for entry in reader.entries()}
        assert sum(1 for rel in wanted if rel.startswith("romfs/")) > 2000
        for rel, path in sorted(wanted.items()):
            entry = listed[rel]
            assert entry.size == path.stat().st_size, rel
            if rel in PREFIX_ONLY:
                reader.stream.seek(entry.offset)
                with open(path, "rb") as stream:
                    assert reader.stream.read(PREFIX_ONLY[rel]) == stream.read(PREFIX_ONLY[rel]), rel
                continue
            hashed = _Hash()
            assert copy_range(reader.stream, entry.offset, entry.size, hashed, lambda: False, lambda n: None)
            assert hashed.digest.hexdigest() == _sha_of(path), rel


@romhacking_root.needs(MM3D_UPDATE_CIA)
def test_majoras_mask_decrypted_update_cia_is_read_without_a_key():
    image = romhacking_root.path(*MM3D_UPDATE_CIA)

    found = images.identify(image)

    assert found["kind"] == "3ds"
    assert found["encrypted"] is False
    with images.open_image(image) as reader:
        paths = [entry.path for entry in reader.entries()]
    assert "exheader.bin" in paths
    assert any(path.startswith("romfs/") for path in paths)
