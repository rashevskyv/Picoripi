"""The Addressables catalog of Castlevania: Belmont's Curse: a changed bundle gets its new size and nothing else changes.
The catalog is made here in the game's layout (entries of seven int32, a 4-byte count; UTF-16 options records)."""
import base64
import json
import struct

import pytest

from plugins.castlevania_belmonts_curse import catalog

OPTIONS = "UnityEngine.ResourceManagement.ResourceProviders.AssetBundleRequestOptions"


def _record(name: str, size: int) -> bytes:
    """One options record: tag byte, assembly and class names (7-bit lengths), int32 length, UTF-16 JSON body."""
    body = json.dumps({"m_Hash": "ab" * 16, "m_Crc": 0, "m_BundleName": f"{name}-bundle", "m_BundleSize": size},
                      separators=(",", ":")).encode("utf-16-le")
    assembly = b"Unity.ResourceManager, Version=0.0.0.0"
    klass = OPTIONS.encode("utf-8")
    return (b"\x07" + bytes([len(assembly)]) + assembly + bytes([len(klass)]) + klass
            + struct.pack("<i", len(body)) + body)


def _catalog(bundles):
    """A catalog with one entry per bundle (its internal id, its options record) and one non-bundle entry."""
    ids = [f"{{UnityEngine.AddressableAssets.Addressables.RuntimePath}}/Switch/{name}" for name, _size in bundles]
    ids.append("Assets/notes.asset")
    extra = bytearray()
    records = []
    for index, (name, size) in enumerate(bundles):
        offset = len(extra)
        extra += _record(name, size)
        records.append(struct.pack("<7i", index, 1, 0, -1, offset, index, 1))
    records.append(struct.pack("<7i", len(bundles), 2, 0, -1, -1, len(bundles), 2))
    entries = struct.pack("<i", len(records)) + b"".join(records)     # a count, then seven int32 per entry
    doc = {"m_LocatorId": "AddressablesMainContentCatalog", "m_InternalIds": ids,
           "m_EntryDataString": base64.b64encode(entries).decode("ascii"),
           "m_ExtraDataString": base64.b64encode(bytes(extra)).decode("ascii"),
           "m_KeyDataString": "", "m_BucketDataString": "", "m_ProviderIds": ["p"]}
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


BUNDLES = [("localization_assets_all_aa.bundle", 104012), ("fonts_assets_all_bb.bundle", 427304),
           ("ui-hud_assets_all_cc.bundle", 5000)]


def test_bundle_options_read_each_record():
    options = catalog.bundle_options(_catalog(BUNDLES))
    assert options["fonts_assets_all_bb.bundle"]["m_BundleSize"] == 427304
    assert options["fonts_assets_all_bb.bundle"]["m_Crc"] == 0
    assert "Assets/notes.asset" not in options


def test_an_unchanged_size_returns_the_catalog_as_it_was():
    raw = _catalog(BUNDLES)
    assert catalog.patch_sizes(raw, {"fonts_assets_all_bb.bundle": 427304}) is raw
    assert catalog.patch_sizes(raw, {}) is raw


def test_a_new_size_changes_only_that_bundle_record():
    raw = _catalog(BUNDLES)
    patched = catalog.patch_sizes(raw, {"localization_assets_all_aa.bundle": 344276})
    options = catalog.bundle_options(patched)
    assert options["localization_assets_all_aa.bundle"]["m_BundleSize"] == 344276
    assert options["localization_assets_all_aa.bundle"]["m_BundleName"] == "localization_assets_all_aa.bundle-bundle"
    assert options["localization_assets_all_aa.bundle"]["m_Hash"] == "ab" * 16
    assert options["fonts_assets_all_bb.bundle"]["m_BundleSize"] == 427304
    before, after = json.loads(raw), json.loads(patched)
    assert {key: value for key, value in before.items() if key not in ("m_EntryDataString", "m_ExtraDataString")} \
        == {key: value for key, value in after.items() if key not in ("m_EntryDataString", "m_ExtraDataString")}


def test_several_bundles_change_together_and_the_others_stay():
    sizes = {"fonts_assets_all_bb.bundle": 3319672, "ui-hud_assets_all_cc.bundle": 2}
    patched = catalog.patch_sizes(_catalog(BUNDLES), sizes)
    options = catalog.bundle_options(patched)
    assert options["fonts_assets_all_bb.bundle"]["m_BundleSize"] == 3319672
    assert options["ui-hud_assets_all_cc.bundle"]["m_BundleSize"] == 2
    assert options["localization_assets_all_aa.bundle"]["m_BundleSize"] == 104012


def test_a_bundle_the_catalog_does_not_name_is_refused():
    with pytest.raises(ValueError):
        catalog.patch_sizes(_catalog(BUNDLES), {"missing_assets_all_dd.bundle": 1})
