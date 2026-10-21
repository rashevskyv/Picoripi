"""The recomp package target: which port a base ROM goes to, the files written, and the two plugin lists."""
import hashlib
import json
from pathlib import Path

import pytest

from plugins.common import pokemon_recomp as pr
from plugins.pokemon_fr.rules import GameRules as FrRules
from plugins.pokemon_gsc.rules import GameRules as GscRules

EMERALD = "f3ae088181bf583e55daf962a92bb46f4f1d07b7"
GOLD = "d8b8a3600a465308c9953dfa04f0081c05bdcb94"


def _sha(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _project(root: Path, base: bytes) -> Path:
    """A project shaped like an unpacked ROM: text/ beside rom/base.*. Returns the text folder."""
    (root / "text").mkdir(parents=True)
    (root / "rom").mkdir()
    (root / "rom" / "base.gba").write_bytes(base)
    return root / "text"


def _fake_rom(payload: bytes):
    """A stand-in for the plugin's ROM writer: writes the bytes into the output folder."""
    def make(source_dir, translation_dir, output_dir):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "Pokemon Emerald UA.gba"
        path.write_bytes(payload)
        return str(path)
    return make


def test_port_comes_from_the_base_rom_sha1(tmp_path, monkeypatch):
    base = b"base rom"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", {_sha(base): {"id": "emerald", "kind": "gba"}})
    assert pr.port_for_source(str(_project(tmp_path, base)))["id"] == "emerald"


def test_unknown_base_rom_is_refused(tmp_path):
    source = _project(tmp_path, b"not a known dump")
    with pytest.raises(ValueError, match="No recomp port runs this ROM"):
        pr.port_for_source(str(source))


def test_build_package_writes_rom_manifest_and_run_script(tmp_path, monkeypatch):
    base, payload = b"base", b"translated rom bytes"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", {_sha(base): {
        "id": "emerald", "kind": "gba", "folder": "EmeraldRecomp", "exe": "EmeraldRecomp.exe",
        "game": "Pokemon Emerald (USA)", "zip": "EmeraldRecomp-windows-x64-v0.1.2.zip",
        "release": "https://example.invalid/EmeraldRecomp/v0.1.2"}})
    source = _project(tmp_path / "project", base)
    out = tmp_path / "out"
    folder = Path(pr.build_package(str(source), "", str(out), _fake_rom(payload), lambda p, m: None, lambda: False))

    assert folder == out / "EmeraldRecomp"
    rom_sha = _sha(payload)
    assert (folder / "Pokemon Emerald UA.gba").read_bytes() == payload
    manifest = json.loads((folder / "recomp.json").read_text(encoding="utf-8"))
    assert manifest == {"port": "emerald", "game": "Pokemon Emerald (USA)", "rom": "Pokemon Emerald UA.gba",
                        "rom_sha1": rom_sha, "rom_bytes": len(payload)}
    script = (folder / "run_UA.bat").read_text(encoding="ascii")
    assert f"--rom-sha1 {rom_sha}" in script and '"EmeraldRecomp.exe"' in script
    readme = (folder / "README_UA.txt").read_text(encoding="utf-8")
    assert rom_sha in readme and "https://example.invalid/EmeraldRecomp/v0.1.2" in readme
    assert not (out / "_rom").exists()


def test_gen2_package_names_the_gate_line_and_has_no_run_script(tmp_path, monkeypatch):
    base, payload = b"gold base", b"gold translated"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", {_sha(base): {
        "id": "gold", "kind": "gen2", "folder": "Gen2Recomped", "game": "Pokemon Gold (USA)"}})
    source = _project(tmp_path / "project", base)
    out = tmp_path / "out"
    folder = Path(pr.build_package(str(source), "", str(out), _fake_rom(payload), lambda p, m: None, lambda: False))

    assert not (folder / "run_UA.bat").exists()
    readme = (folder / "README_UA.txt").read_text(encoding="utf-8")
    assert f'sha1Alt = {{ "{_sha(payload)}" }},' in readme
    assert "POKEPORT_IMPORT_ROM" in readme


def _pret_workspace(root: Path, dump: bytes) -> Path:
    """A pret workspace: source/ beside ISO/ (the dump) and build/ (2_build.bat's ROM). Returns source/."""
    (root / "source").mkdir(parents=True)
    (root / "ISO").mkdir()
    (root / "ISO" / "Pokemon - Emerald Version (USA, Europe).gba").write_bytes(dump)
    return root / "source"


def test_pret_workspace_packages_an_unchanged_build_and_never_calls_the_writer(tmp_path, monkeypatch):
    dump = built = b"emerald dump"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", {_sha(dump): {
        "id": "emerald", "kind": "gba", "folder": "EmeraldRecomp", "exe": "EmeraldRecomp.exe",
        "game": "Pokemon Emerald (USA)", "built": "pokeemerald.gba", "zip": "z.zip", "version": "0.1.2",
        "release": "https://example.invalid/v0.1.2"}})
    source = _pret_workspace(tmp_path / "ws", dump)
    (tmp_path / "ws" / "build").mkdir()
    (tmp_path / "ws" / "build" / "pokeemerald.gba").write_bytes(built)

    def writer_must_not_run(*_):
        raise AssertionError("a pret workspace has no ROM writer")

    out = tmp_path / "out"
    folder = Path(pr.build_package(str(source), "", str(out), writer_must_not_run, lambda p, m: None, lambda: False))
    assert (folder / "pokeemerald.gba").read_bytes() == built
    assert json.loads((folder / "recomp.json").read_text(encoding="utf-8"))["rom_sha1"] == _sha(built)


def test_pret_workspace_refuses_a_changed_build(tmp_path, monkeypatch):
    dump, built = b"emerald dump", b"built with a longer text"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", {_sha(dump): {
        "id": "emerald", "kind": "gba", "folder": "EmeraldRecomp", "exe": "EmeraldRecomp.exe",
        "game": "Pokemon Emerald (USA)", "built": "pokeemerald.gba", "zip": "z.zip", "release": "x"}})
    source = _pret_workspace(tmp_path / "ws", dump)
    (tmp_path / "ws" / "build").mkdir()
    (tmp_path / "ws" / "build" / "pokeemerald.gba").write_bytes(built)
    with pytest.raises(ValueError, match="blank screen"):
        pr.build_package(str(source), "", str(tmp_path / "out"), lambda *_: "", lambda p, m: None, lambda: False)


def test_pret_workspace_without_a_build_names_2_build_bat(tmp_path, monkeypatch):
    dump = b"emerald dump"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", {_sha(dump): {
        "id": "emerald", "kind": "gba", "folder": "EmeraldRecomp", "exe": "EmeraldRecomp.exe",
        "game": "Pokemon Emerald (USA)", "built": "pokeemerald.gba", "zip": "z.zip", "version": "0.1.2",
        "release": "x"}})
    source = _pret_workspace(tmp_path / "ws", dump)
    with pytest.raises(ValueError, match="2_build.bat"):
        pr.build_package(str(source), "", str(tmp_path / "out"), lambda *_: "", lambda p, m: None, lambda: False)


def test_cancelled_build_writes_nothing_into_the_port_folder(tmp_path, monkeypatch):
    base = b"base"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", {_sha(base): {
        "id": "emerald", "kind": "gba", "folder": "EmeraldRecomp", "exe": "EmeraldRecomp.exe",
        "game": "Pokemon Emerald (USA)", "release": "x"}})
    source = _project(tmp_path / "project", base)
    out = tmp_path / "out"
    assert pr.build_package(str(source), "", str(out), _fake_rom(b"x"), lambda p, m: None, lambda: True) == ""
    assert not (out / "EmeraldRecomp").exists()


def test_both_plugins_list_the_recomp_target():
    fr = [t["id"] for t in FrRules.get_build_targets(None)]
    gsc = [t["id"] for t in GscRules.get_build_targets(None)]
    assert fr == ["rom", "recomp"]
    assert gsc == ["rom", "recomp"]


def test_known_ports_match_the_accepted_dumps():
    assert pr.PORTS_BY_BASE_SHA1[EMERALD]["id"] == "emerald"
    assert pr.PORTS_BY_BASE_SHA1[GOLD]["kind"] == "gen2"
