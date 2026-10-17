"""Brilliant Diamond / Shining Pearl: the wizard unpack and the build of the message tables, on the owner's images.

The tests run the wizard's own job (``build.run_unpack``) and skip unless the owner's packages, the workspace and the
Switch key path (a path in the shared ``zelda_env.ini``; the key file is opened by Picoripi's reader only) are on disk.
"""
import hashlib
import json
import re
from pathlib import Path

import pytest
import romhacking_root

from core.containers import console_crypto
from core.project_library import build
from core.unity.unityfs import Bundle
from core.unity.serialized import SerializedFile
from plugins.pokemon_bdsp import bundles, unpack
from plugins.pokemon_bdsp import build as bdsp_build
from plugins.testing import load_rules

ROOT = romhacking_root.under("Pokemon")
BDSP = ROOT / "Brilliant Diamond and Shining Pearl"
BASE = BDSP / "nsp" / "Pokemon Brilliant Diamond [0100000011D90000][v0].nsp"
UPDATE = BDSP / "nsp" / "Pokemon Brilliant Diamond [0100000011D90800][v393216].nsp"
KEY_INI = romhacking_root.root() / "_shared" / "scripts" / "zelda_env.ini" if romhacking_root.root() else None


def _switch_key_path():
    if KEY_INI is None or not KEY_INI.is_file():
        return None
    for line in KEY_INI.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^\s*switch_keys\s*=\s*(.+?)\s*$", line)
        if match and Path(match.group(1)).is_file():
            return match.group(1)
    return None


def _provider(console):
    return _switch_key_path() if console == "switch" else None


def _need():
    if not (BASE.is_file() and UPDATE.is_file()):
        pytest.skip("the owner's Brilliant Diamond packages are not on disk")
    if _switch_key_path() is None:
        pytest.skip("the Switch key path is not in the shared env file")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unpacked(tmp_path):
    _need()
    rules = load_rules("pokemon_bdsp")
    with console_crypto.key_source(_provider):
        folder = build.run_unpack(rules, {"base": str(BASE), "update": str(UPDATE)}, str(tmp_path / "project"),
                                  lambda percent, text: None, lambda: False, _provider)
    return Path(folder)


def test_identify_tells_base_from_update_and_refuses_other_files(tmp_path):
    _need()
    assert unpack.identify(str(BASE))["role"] == "base"
    assert unpack.identify(str(UPDATE))["role"] == "update"
    other = tmp_path / "other.nsp"
    other.write_bytes(b"not a switch package")
    assert unpack.identify(str(other)) is None


def test_wizard_unpack_writes_every_english_table_like_the_workspace(tmp_path):
    folder = _unpacked(tmp_path)
    theirs = sorted((BDSP / "source" / "message").glob("english_*.bdmsg"))
    ours = sorted((folder / "message").glob("english_*.bdmsg"))
    assert [p.name for p in ours] == [p.name for p in theirs] and len(ours) == 128
    assert all(_sha(a) == _sha(b) for a, b in zip(ours, theirs))


def test_the_message_bundles_are_kept_beside_the_source(tmp_path):
    folder = _unpacked(tmp_path)
    for rel in bundles.MESSAGE_BUNDLES:
        kept = folder.parent / "romfs" / rel
        workspace = BDSP / "romfs" / rel
        assert kept.is_file() and workspace.is_file()
        assert _sha(kept) == _sha(workspace)


def test_an_unedited_translation_builds_nothing(tmp_path):
    folder = _unpacked(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    result = bdsp_build.build_switch(str(folder), str(folder), str(out), lambda p, t: None, lambda: False)
    assert not (out / "atmosphere").exists()
    assert result == str(out / "atmosphere")


def test_an_edited_label_is_written_back_and_nothing_else_changes(tmp_path):
    folder = _unpacked(tmp_path)
    translation = tmp_path / "translation"
    (translation / "message").mkdir(parents=True)
    name = "english_dlp_adventure_note"
    table = json.loads((folder / "message" / f"{name}.bdmsg").read_text(encoding="utf-8"))
    word = table["labelDataArray"][0]["wordDataArray"][0]
    word["str"] = "Test label value"
    (translation / "message" / f"{name}.bdmsg").write_text(
        json.dumps(table, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    bdsp_build.build_switch(str(folder), str(translation), str(out), lambda p, t: None, lambda: False)
    title = bdsp_build.TITLE_IDS[0]
    rel = next(r for r in bundles.MESSAGE_BUNDLES if name in bundles.tables(_serialized(BDSP / "romfs" / r)))
    written = out / "atmosphere" / "contents" / title / "romfs" / rel
    serialized = _serialized(written)
    names = bundles.tables(serialized)
    edited = serialized.read(names[name])
    assert edited["labelDataArray"][0]["wordDataArray"][0]["str"] == "Test label value"
    original = _serialized(BDSP / "romfs" / rel)
    original_names = bundles.tables(original)
    for other, path_id in names.items():
        if other != name:
            assert serialized.read(path_id) == original.read(original_names[other])


def _serialized(path: Path) -> SerializedFile:
    bundle = Bundle(path.read_bytes())
    return SerializedFile(bundle.read(bundle.nodes[0].name))


def test_a_table_the_game_does_not_have_is_refused(tmp_path):
    folder = _unpacked(tmp_path)
    translation = tmp_path / "translation"
    (translation / "message").mkdir(parents=True)
    (translation / "message" / "english_not_in_the_game.bdmsg").write_text(
        json.dumps(json.loads((folder / "message" / "english_dlp_adventure_note.bdmsg").read_text("utf-8"))),
        encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(ValueError):
        bdsp_build.build_switch(str(folder), str(translation), str(out), lambda p, t: None, lambda: False)
