"""Decrypted Nintendo 3DS programs of the owner's RomHacking workspace: no key is needed, and workspace files equal the
files the image holds (same size and sha256).

The workspace ``exefs`` (code, icon, banner) is the Update build's: it equals the decrypted Update CIA, and the packed
ExeFS code is decoded to the workspace bytes. The workspace ``romfs`` is the base game's: it equals the base CXI.

Needs ``PICORIPI_ROMHACKING`` (see tests/romhacking_root.py). Read only: nothing is written to the workspace; the
extracted copies go to pytest's temporary folder.
"""
import hashlib

import romhacking_root
from core.containers.image_files import copy_range
from core.project_library import images

MM3D_CXI = ("Zelda", "Majoras Mask", "3D - 3DS", "image", "Majora's Mask 3D (decrypted).cxi")
MM3D_UPDATE_CIA = ("Zelda", "Majoras Mask", "3D - 3DS", "image", "Majora's Mask 3D Update (decrypted).cia")
MM3D_WORKSPACE = ("Zelda", "Majoras Mask", "3D - 3DS")
# Workspace files the base CXI does not hold: the exheader copy 3dstool also writes into ``exefs``, the workspace's
# ``romfs/version.ctxb`` (not in the RomFS), and the workspace ExeFS (from the Update build; see the Update test).
NOT_FROM_BASE = {"exefs/exheader.bin", "romfs/version.ctxb", "exefs/code.bin", "exefs/icon.bin"}


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


def _program_files(workspace, skip):
    """The workspace files the program's exheader and RomFS hold as stored: ``{relative path: file}``."""
    files = {}
    for path in workspace.rglob("*"):
        rel = path.relative_to(workspace).as_posix()
        if not path.is_file() or rel in skip:
            continue
        if rel in ("exheader.bin", "exefs/banner.bin") or rel.startswith("romfs/"):
            files[rel] = path
    return files


@romhacking_root.needs(MM3D_CXI, MM3D_WORKSPACE)
def test_majoras_mask_decrypted_cxi_romfs_matches_the_workspace():
    workspace = romhacking_root.path(*MM3D_WORKSPACE)
    wanted = _program_files(workspace, NOT_FROM_BASE)
    assert sum(1 for rel in wanted if rel.startswith("romfs/")) > 2000
    image = romhacking_root.path(*MM3D_CXI)

    assert images.identify(image)["encrypted"] is False
    with images.open_image(image) as reader:
        listed = {entry.path: entry for entry in reader.entries()}
        for rel, path in sorted(wanted.items()):
            entry = listed[rel]
            assert entry.size == path.stat().st_size, rel
            hashed = _Hash()
            assert copy_range(reader.source(entry), entry.offset, entry.size, hashed, lambda: False, lambda n: None)
            assert hashed.digest.hexdigest() == _sha_of(path), rel
        assert listed["exheader.bin"].size == romhacking_root.path(*MM3D_WORKSPACE, "exheader.bin").stat().st_size


@romhacking_root.needs(MM3D_UPDATE_CIA, MM3D_WORKSPACE)
def test_majoras_mask_update_cia_exefs_matches_the_workspace(tmp_path):
    image = romhacking_root.path(*MM3D_UPDATE_CIA)
    workspace = romhacking_root.path(*MM3D_WORKSPACE)

    assert images.identify(image)["encrypted"] is False
    written = images.extract(image, tmp_path, lambda p, t: None, lambda: False,
                             select=lambda path: path in ("exefs/code.bin", "exefs/icon.bin"))

    assert written == str(tmp_path)
    for name in ("code.bin", "icon.bin"):
        assert _sha_of(tmp_path / "exefs" / name) == _sha_of(workspace / "exefs" / name), name


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
