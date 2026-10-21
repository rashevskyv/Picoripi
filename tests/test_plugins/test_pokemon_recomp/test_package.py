"""The recomp package target: which ports a project's dumps go to, the files written, and the plugin lists."""
import hashlib
import json
from pathlib import Path

import pytest

from plugins.common import pokemon_recomp as pr
from plugins.pokemon_fr.rules import GameRules as FrRules
from plugins.pokemon_gsc.rules import GameRules as GscRules

EMERALD = "f3ae088181bf583e55daf962a92bb46f4f1d07b7"
GOLD = "d8b8a3600a465308c9953dfa04f0081c05bdcb94"
noop = lambda p, m: None  # noqa: E731
never = lambda: False  # noqa: E731


def _sha(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _port(sha: str, **extra) -> dict:
    base = {"id": "emerald", "kind": "gba", "folder": "EmeraldRecomp", "exe": "EmeraldRecomp.exe",
            "game": "Pokemon Emerald (USA)", "built": "pokeemerald.gba", "code": "BPEE", "zip": "z.zip",
            "release": "https://example.invalid/v0.1.2", "version": "0.1.2"}
    base.update(extra)
    return {sha: base}


def _rom_project(root: Path, base: bytes) -> Path:
    """A ROM-mode project: text/ beside rom/base.*. Returns the text folder."""
    (root / "text").mkdir(parents=True)
    (root / "rom").mkdir()
    (root / "rom" / "base.gba").write_bytes(base)
    return root / "text"


def _pret_workspace(root: Path, dumps: dict) -> Path:
    """A pret workspace: source/ beside ISO/ (the dumps). Returns source/."""
    (root / "source").mkdir(parents=True)
    (root / "ISO").mkdir()
    for name, data in dumps.items():
        (root / "ISO" / name).write_bytes(data)
    return root / "source"


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
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", _port(_sha(base)))
    assert pr.port_for_source(str(_rom_project(tmp_path, base)))["id"] == "emerald"


def test_unknown_base_rom_is_refused(tmp_path):
    with pytest.raises(ValueError, match="No recomp port runs this ROM"):
        pr.port_for_source(str(_rom_project(tmp_path, b"not a known dump")))


def test_rom_mode_package_writes_rom_manifest_and_run_script(tmp_path, monkeypatch):
    base, payload = b"base", b"translated rom bytes"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", _port(_sha(base)))
    source = _rom_project(tmp_path / "project", base)
    out = tmp_path / "out"
    folder = Path(pr.build_package(str(source), "", str(out), _fake_rom(payload), noop, never))

    assert folder == out / "EmeraldRecomp" / "emerald"
    rom_sha = _sha(payload)
    assert (folder / "Pokemon Emerald UA.gba").read_bytes() == payload
    manifest = json.loads((folder / "recomp.json").read_text(encoding="utf-8"))
    assert manifest["rom_sha1"] == rom_sha and manifest["re_recompile"] is False
    script = (folder / "run_UA.bat").read_text(encoding="ascii")
    assert f"--rom-sha1 {rom_sha}" in script and '"EmeraldRecomp.exe"' in script
    readme = (folder / "README_UA.txt").read_text(encoding="utf-8")
    assert rom_sha in readme and "https://example.invalid/v0.1.2" in readme
    assert not (folder / "recompile_UA.sh").exists()
    assert not (out / "EmeraldRecomp" / "_rom").exists()


def test_cancelled_build_writes_nothing_into_the_port_folder(tmp_path, monkeypatch):
    base = b"base"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", _port(_sha(base)))
    source = _rom_project(tmp_path / "project", base)
    out = tmp_path / "out"
    assert pr.build_package(str(source), "", str(out), _fake_rom(b"x"), noop, lambda: True) == ""
    assert not (out / "EmeraldRecomp").exists()


def test_pret_unchanged_build_packages_without_recompile(tmp_path, monkeypatch):
    dump = built = b"emerald dump"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", _port(_sha(dump)))
    source = _pret_workspace(tmp_path / "ws", {"Pokemon - Emerald Version (USA, Europe).gba": dump})
    (tmp_path / "ws" / "build").mkdir()
    (tmp_path / "ws" / "build" / "pokeemerald.gba").write_bytes(built)

    def writer_must_not_run(*_):
        raise AssertionError("a pret workspace has no ROM writer")

    folder = Path(pr.build_package(str(source), "", str(tmp_path / "out"), writer_must_not_run, noop, never))
    assert (folder / "pokeemerald.gba").read_bytes() == built
    assert json.loads((folder / "recomp.json").read_text(encoding="utf-8"))["re_recompile"] is False


def test_pret_changed_emerald_build_ships_the_re_recompile_script(tmp_path, monkeypatch):
    dump, built = b"emerald dump", b"built with a longer text"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", _port(_sha(dump)))
    source = _pret_workspace(tmp_path / "ws", {"Pokemon - Emerald Version (USA, Europe).gba": dump})
    (tmp_path / "ws" / "build").mkdir()
    (tmp_path / "ws" / "build" / "pokeemerald.gba").write_bytes(built)
    folder = Path(pr.build_package(str(source), "", str(tmp_path / "out"), lambda *_: "", noop, never))

    assert json.loads((folder / "recomp.json").read_text(encoding="utf-8"))["re_recompile"] is True
    script = (folder / "recompile_UA.sh").read_text(encoding="utf-8")
    assert f'SHA="{_sha(built)}"' in script and 'CODE="BPEE"' in script and 'ROM="$HERE/pokeemerald.gba"' in script
    assert "__ROM__" not in script and "__SHA1__" not in script
    assert "recompile_UA.sh" in (folder / "README_UA.txt").read_text(encoding="utf-8")


def test_pret_changed_firered_build_is_refused(tmp_path, monkeypatch):
    dump, built = b"firered dump", b"changed"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", _port(_sha(dump), id="firered", folder="FireRedLeafGreenRecomp",
                                                        built="pokefirered.gba", game="Pokemon FireRed v1.0 (USA)"))
    source = _pret_workspace(tmp_path / "ws", {"Pokemon - FireRed Version (USA, Europe).gba": dump})
    (tmp_path / "ws" / "build").mkdir()
    (tmp_path / "ws" / "build" / "pokefirered.gba").write_bytes(built)
    with pytest.raises(ValueError, match="not built yet|re-recompilation"):
        pr.build_package(str(source), "", str(tmp_path / "out"), lambda *_: "", noop, never)


def test_pret_workspace_without_a_build_names_2_build_bat(tmp_path, monkeypatch):
    dump = b"emerald dump"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", _port(_sha(dump)))
    source = _pret_workspace(tmp_path / "ws", {"Pokemon - Emerald Version (USA, Europe).gba": dump})
    with pytest.raises(ValueError, match="2_build.bat"):
        pr.build_package(str(source), "", str(tmp_path / "out"), lambda *_: "", noop, never)


def test_gen2_package_ships_the_gate_script_and_names_the_block(tmp_path, monkeypatch):
    base, payload = b"gold base", b"gold translated"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", {_sha(base): {
        "id": "gold", "kind": "gen2", "folder": "Gen2Recomped", "game": "Pokemon Gold (USA)",
        "built": "pokegold.gbc", "block": "gold", "canonical": GOLD, "base_sha1": _sha(base)}})
    source = _rom_project(tmp_path / "project", base)
    folder = Path(pr.build_package(str(source), "", str(tmp_path / "out"), _fake_rom(payload), noop, never))

    assert folder == tmp_path / "out" / "Gen2Recomped" / "gold"
    assert (folder / "set_gen2_gate_UA.py").is_file()
    assert not (folder / "run_UA.bat").exists()
    readme = (folder / "README_UA.txt").read_text(encoding="utf-8")
    assert f"gold {GOLD} {_sha(payload)}" in readme and "POKEPORT_IMPORT_ROM" in readme


def test_build_packages_makes_one_folder_per_dump(tmp_path, monkeypatch):
    gold, silver = b"gold dump", b"silver dump"
    monkeypatch.setattr(pr, "PORTS_BY_BASE_SHA1", {
        _sha(gold): {"id": "gold", "kind": "gen2", "folder": "Gen2Recomped", "game": "Gold", "built": "pokegold.gbc",
                     "block": "gold", "canonical": GOLD},
        _sha(silver): {"id": "silver", "kind": "gen2", "folder": "Gen2Recomped", "game": "Silver",
                       "built": "pokesilver.gbc", "block": "silver", "canonical": _sha(silver)}})
    source = _pret_workspace(tmp_path / "ws", {"Pokemon - Gold Version (UE) [!].gbc": gold,
                                               "Pokemon - Silver Version (UE) [!].gbc": silver})
    (tmp_path / "ws" / "build").mkdir()
    (tmp_path / "ws" / "build" / "pokegold.gbc").write_bytes(gold)
    (tmp_path / "ws" / "build" / "pokesilver.gbc").write_bytes(silver)
    root = Path(pr.build_packages(str(source), "", str(tmp_path / "out"), lambda *_: "", noop, never))

    assert root == tmp_path / "out" / "recomp"
    assert (root / "Gen2Recomped" / "gold" / "pokegold.gbc").read_bytes() == gold
    assert (root / "Gen2Recomped" / "silver" / "pokesilver.gbc").read_bytes() == silver


def test_both_plugins_list_the_recomp_target():
    fr = [t["id"] for t in FrRules.get_build_targets(None)]
    gsc = [t["id"] for t in GscRules.get_build_targets(None)]
    assert fr == ["rom", "recomp"]
    assert gsc == ["rom", "recomp"]


def test_known_ports_match_the_accepted_dumps():
    assert pr.PORTS_BY_BASE_SHA1[EMERALD]["id"] == "emerald"
    assert pr.PORTS_BY_BASE_SHA1[GOLD]["kind"] == "gen2"
