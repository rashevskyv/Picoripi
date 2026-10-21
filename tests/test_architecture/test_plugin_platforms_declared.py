"""Every game plugin names the platforms it ships on, so the new-project wizard can offer them and show them."""
import ast
import json
from pathlib import Path

from core.project_library import plugin_facts
from plugins.base_game_rules import BaseGameRules

PLUGINS = Path(__file__).resolve().parents[2] / "plugins"
NOT_PLUGINS = {"common", "import_plugins", "ENG", "UA", "__pycache__"}


def _defines_get_platforms(folder: Path) -> bool:
    for source in folder.glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        if any(isinstance(node, ast.FunctionDef) and node.name == "get_platforms" for node in ast.walk(tree)):
            return True
    return False


def test_every_plugin_names_at_least_one_known_platform():
    missing, unknown = [], []
    for folder in sorted(p for p in PLUGINS.iterdir() if p.is_dir() and p.name not in NOT_PLUGINS):
        if not (folder / "config.json").is_file() or _defines_get_platforms(folder):
            continue
        ids = json.loads((folder / "config.json").read_text(encoding="utf-8")).get("platforms") or []
        if not ids:
            missing.append(folder.name)
        unknown += [f"{folder.name}:{item}" for item in ids if item not in plugin_facts.PLATFORM_LABELS]
    assert missing == [], "plugins without \"platforms\" in config.json and no get_platforms: " + ", ".join(missing)
    assert unknown == [], "platform ids not in plugin_facts.PLATFORM_LABELS: " + ", ".join(unknown)


def test_the_default_hook_reads_the_plugins_config():
    from plugins.code_of_princess.rules import GameRules

    platforms = GameRules(None).get_platforms()
    assert [p["id"] for p in platforms] == ["3ds", "switch"]
    assert [p["label"] for p in platforms] == ["Nintendo 3DS", "Nintendo Switch"]
    assert BaseGameRules(None).get_platforms() == []   # the base class has no config.json beside it
