"""The Gen 2 gate script on a synthetic Gen2Recomp checkout: manifest remap, placeholder move, importer patch."""
import json
import subprocess
import sys
from pathlib import Path

GATE = Path(__file__).resolve().parents[3] / "plugins" / "common" / "recomp_templates" / "gen2_gate.py"
CANON = "d8b8a3600a465308c9953dfa04f0081c05bdcb94"
NEW = "1553efb4d508e3e92ee0946bcfe8fb8b2652c620"

GAME_VERSION = f'''return {{
  VERSIONS = {{
  gold = {{
    id = "gold",
    sha1 = "{CANON}",
    manifest = "tools/rom_manifest_gold.json",
    cachePrefix = "gold/",
  }},
  }},
}}
'''
IMPORTER = '''local function decodeManifest(version)
  local path = GameVersion.info(version).manifest
  return path
end
local function startData(actualHash)
    local manifest = decodeManifest(version)
end
'''


def _checkout(root: Path) -> Path:
    (root / "src" / "core").mkdir(parents=True)
    (root / "src" / "import").mkdir(parents=True)
    (root / "tools").mkdir()
    (root / "data" / "generated_gen2_gold").mkdir(parents=True)
    (root / "src" / "core" / "GameVersion.lua").write_text(GAME_VERSION, encoding="utf-8")
    (root / "src" / "import" / "RomImporter.lua").write_text(IMPORTER, encoding="utf-8")
    manifest = {"romSha1": CANON, "symbols": {"Moved": [72, 100], "Still": [72, 200], "Ram": [0, 0xC100]}}
    (root / "tools" / "rom_manifest_gold.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "data" / "generated_gen2_gold" / "text.lua").write_text(
        '__t["A"] = "{GEN2_TEXT:48:0064:Moved}"\n__t["B"] = "{GEN2_TEXT:48:00C8:Still}"\n', encoding="utf-8")
    return root


def _sym(path: Path) -> Path:
    path.write_text("48:0164 Moved\n48:00C8 Still\n00:C100 Ram\n", encoding="utf-8")
    return path


def _run(*args):
    return subprocess.run([sys.executable, "-I", str(GATE), *args], capture_output=True, text=True)


def test_changed_build_writes_manifest_placeholders_and_importer_patch(tmp_path):
    root = _checkout(tmp_path / "Gen2Recomped-src")
    result = _run(str(root), "gold", CANON, NEW, str(_sym(tmp_path / "pokegold.sym")))
    assert result.returncode == 0, result.stdout + result.stderr

    manifest = json.loads((root / "tools" / "rom_manifest_gold_1553efb4.json").read_text(encoding="utf-8"))
    assert manifest["romSha1"] == NEW
    assert manifest["symbols"]["Moved"] == [72, 0x164]
    assert manifest["symbols"]["Still"] == [72, 200]
    assert manifest["symbols"]["Ram"] == [0, 0xC100]  # RAM keeps the shipped value
    text = (root / "data" / "generated_gen2_gold" / "text.lua").read_text(encoding="utf-8")
    assert "{GEN2_TEXT:48:0164:Moved}" in text and "{GEN2_TEXT:48:00C8:Still}" in text
    game = (root / "src" / "core" / "GameVersion.lua").read_text(encoding="utf-8")
    assert f'sha1Alt = {{ "{NEW}" }}' in game
    assert f'manifestBySha1 = {{ ["{NEW}"] = "tools/rom_manifest_gold_1553efb4.json" }}' in game
    importer = (root / "src" / "import" / "RomImporter.lua").read_text(encoding="utf-8")
    assert "local function decodeManifest(version, sha1)" in importer
    assert "decodeManifest(version, actualHash)" in importer
    assert (root / "src" / "core" / "GameVersion.lua.bak").is_file()


def test_second_run_changes_nothing(tmp_path):
    root = _checkout(tmp_path / "src")
    sym = _sym(tmp_path / "pokegold.sym")
    assert _run(str(root), "gold", CANON, NEW, str(sym)).returncode == 0
    before = (root / "src" / "core" / "GameVersion.lua").read_text(encoding="utf-8")
    result = _run(str(root), "gold", CANON, NEW, str(sym))
    assert result.returncode == 0 and "already accepted" in result.stdout
    assert (root / "src" / "core" / "GameVersion.lua").read_text(encoding="utf-8") == before


def test_changed_build_without_symbol_map_is_refused(tmp_path):
    root = _checkout(tmp_path / "src")
    result = _run(str(root), "gold", CANON, NEW)
    assert result.returncode == 1 and "pret .sym" in result.stdout
    assert not (root / "tools" / "rom_manifest_gold_1553efb4.json").exists()


def test_missing_block_is_refused(tmp_path):
    root = _checkout(tmp_path / "src")
    result = _run(str(root), "silver", CANON, NEW, str(_sym(tmp_path / "s.sym")))
    assert result.returncode == 1 and "not found once" in result.stdout
