"""Unity AssetBundle CRC for Addressables catalogs (core/containers/unityfs_crc.py)."""
from __future__ import annotations

import base64
import json
import os
import zlib
from pathlib import Path

import pytest

from core.containers.unityfs_crc import bundle_crc, patch_catalog_crc

REAL_LAUNCHER = Path(os.environ.get("MGS3_PC_LAUNCHER_DATA", "D:/Games/MGS3 Master Collection/launcher_Data"))
REAL_TERMS = REAL_LAUNCHER / "StreamingAssets/aa/StandaloneWindows64/defaultlocalgroup_assets_module/textdata/textdata_terms.asset.bundle"


def _bundle(blocks: list[bytes]) -> bytes:
    """A UnityFS bundle with stored (uncompressed) blocks and the block info right after the header."""
    info = bytes(16) + len(blocks).to_bytes(4, "big")
    for block in blocks:
        info += len(block).to_bytes(4, "big") + len(block).to_bytes(4, "big") + (0).to_bytes(2, "big")
    header = (b"UnityFS\x00" + (6).to_bytes(4, "big") + b"5.x.x\x00" + b"2021.3.16f1\x00"
              + (0).to_bytes(8, "big") + len(info).to_bytes(4, "big") + len(info).to_bytes(4, "big")
              + (0).to_bytes(4, "big"))
    return header + info + b"".join(blocks)


def _catalog(records: list[str]) -> bytes:
    extra = "".join(records).encode("utf-16-le")
    return json.dumps({"m_LocatorId": "test", "m_ExtraDataString": base64.b64encode(extra).decode("ascii")}).encode()


def _extra(catalog: bytes) -> str:
    return base64.b64decode(json.loads(catalog)["m_ExtraDataString"]).decode("utf-16-le")


def test_bundle_crc_is_crc32_of_the_uncompressed_blocks():
    bundle = _bundle([b"abc", b"defgh"])
    assert bundle_crc(bundle) == zlib.crc32(b"abcdefgh") & 0xFFFFFFFF


def test_bundle_crc_ignores_the_header_and_block_info():
    one = _bundle([b"payload"])
    other = _bundle([b"pay", b"load"])
    assert bundle_crc(one) == bundle_crc(other) == zlib.crc32(b"payload") & 0xFFFFFFFF


def test_bundle_crc_rejects_files_that_are_not_unityfs():
    with pytest.raises(ValueError):
        bundle_crc(b"not a bundle")


def test_patch_changes_only_the_crc_digits():
    catalog = _catalog(['{"m_Hash":"ab","m_Crc":2430254833,"m_Timeout":0}',
                        '{"m_Crc":308193437,"m_X":1}'])
    patched = patch_catalog_crc(catalog, {2430254833: 1166981761, 308193437: 357291365})
    assert _extra(patched) == ('{"m_Hash":"ab","m_Crc":1166981761,"m_Timeout":0}'
                               '{"m_Crc":357291365,"m_X":1}')
    assert len(_extra(patched)) == len(_extra(catalog))
    assert json.loads(patched)["m_LocatorId"] == "test"


def test_patch_pads_a_shorter_crc_with_spaces_before_the_comma():
    catalog = _catalog(['{"m_Crc":2430254833,"m_Timeout":0}'])
    patched = patch_catalog_crc(catalog, {2430254833: 123456789})
    assert _extra(patched) == '{"m_Crc":123456789 ,"m_Timeout":0}'


def test_patch_without_edits_keeps_the_file_byte_exact():
    catalog = _catalog(['{"m_Crc":2430254833,"m_Timeout":0}'])
    assert patch_catalog_crc(catalog, {}) == catalog


def test_patch_refuses_a_crc_that_is_not_in_the_catalog_once():
    catalog = _catalog(['{"m_Crc":2430254833,"m_Timeout":0}'])
    with pytest.raises(ValueError):
        patch_catalog_crc(catalog, {1234: 5678})


def test_patch_refuses_a_new_crc_with_more_digits():
    catalog = _catalog(['{"m_Crc":308193437,"m_X":1}'])
    with pytest.raises(ValueError):
        patch_catalog_crc(catalog, {308193437: 1234567890})


@pytest.mark.skipif(not REAL_TERMS.is_file(), reason="MGS3 PC launcher data is not on disk")
def test_real_terms_bundle_matches_its_catalog_value():
    # The catalog record of textdata_terms (LZ4HC blocks) stores this CRC; the value was checked on all 204 records.
    assert bundle_crc(REAL_TERMS.read_bytes()) == 2430254833
