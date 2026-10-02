"""Check a plugin against the contract in ``plugins/spec.py``.

    python -m plugins.validate                 # every plugin
    python -m plugins.validate zelda_mc demo   # the named ones

Exit code 1 when any plugin has an error. Errors are things the host will trip
over (a hook that raises, a wrong return type, a signature the host cannot
call, a broken JSON file). Warnings are things that work today but lean on
something nobody promised (an unknown config key, a main-window attribute
outside the allowed list).

Hooks are called on a ``GameRules()`` built without a main window, the same way
the test suite builds it: a plugin has to survive that.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from plugins.base_game_rules import BaseGameRules
from plugins.spec import (
    HOOKS,
    KNOWN_CONFIG_KEYS,
    MAIN_WINDOW_ATTRIBUTES,
    PROMPT_SECTIONS,
    SESSION_KEYS,
)

PLUGINS_DIR = Path(__file__).resolve().parent
# Directories under plugins/ that hold a config.json but are not game plugins.
NOT_PLUGINS = frozenset({"import_plugins", "common"})
_HOST_NAMES = ("mw", "main_window", "main_window_ref")


@dataclass
class Report:
    """What the validator found in one plugin."""

    plugin: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = [f"{self.plugin}: {'OK' if self.ok else 'FAILED'}"]
        lines += [f"  error: {text}" for text in self.errors]
        lines += [f"  warning: {text}" for text in self.warnings]
        return "\n".join(lines)


def plugin_names(root: Path = PLUGINS_DIR) -> List[str]:
    """Every plugin directory: it has a ``config.json`` (the rule the application uses)."""
    return sorted(
        path.parent.name
        for path in root.glob("*/config.json")
        if path.parent.name not in NOT_PLUGINS
    )


# -- config.json and the other data files ----------------------------------------

def check_config(config: Any, report: Report) -> None:
    if not isinstance(config, dict):
        report.errors.append("config.json must hold a JSON object")
        return
    if not str(config.get("display_name") or "").strip():
        report.errors.append("config.json: 'display_name' is missing or empty")
    session = sorted(SESSION_KEYS.intersection(config))
    if session:
        report.errors.append(
            "config.json holds per-session keys (they belong in project_settings.json): " + ", ".join(session)
        )
    unknown = sorted(set(config) - KNOWN_CONFIG_KEYS - SESSION_KEYS)
    if unknown:
        report.warnings.append("config.json: keys the host does not know: " + ", ".join(unknown))


def check_font_map(font_map: Any, report: Report) -> None:
    if not isinstance(font_map, dict):
        report.errors.append("font_map.json must hold a JSON object of {character or tag: {'width': N}}")
        return
    bad = [key for key, value in font_map.items() if not (isinstance(value, dict) and isinstance(value.get("width"), int))]
    if bad:
        report.errors.append(f"font_map.json: {len(bad)} entries have no integer 'width', e.g. {bad[:3]}")


def check_prompts(prompts: Any, report: Report) -> None:
    if not isinstance(prompts, dict):
        report.errors.append("translation_prompts/prompts.json must hold a JSON object")
        return
    unknown = sorted(set(prompts) - set(PROMPT_SECTIONS))
    if unknown:
        report.warnings.append("prompts.json: sections the host does not read: " + ", ".join(unknown))


def _read_json(path: Path, report: Report) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        report.errors.append(f"{path.name}: cannot be read as JSON ({error})")
        return None


# -- the rules class --------------------------------------------------------------

def _accepts(method: Any, base_method: Any) -> Optional[str]:
    """Why ``method`` cannot be called the way the host calls ``base_method``, or None."""
    try:
        own = inspect.signature(method)
        base = inspect.signature(base_method)
    except (TypeError, ValueError):
        return None
    names = [name for name in base.parameters if name != "self"]
    own_parameters = own.parameters
    takes_anything = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in own_parameters.values())
    # Positional arguments may be renamed; the optional ones are passed by name.
    by_name = [name for name in names if base.parameters[name].default is not inspect.Parameter.empty]
    missing = [name for name in by_name if name not in own_parameters and not takes_anything]
    if missing:
        return "does not accept the keyword argument(s) " + ", ".join(missing)
    try:
        own.bind(*([None] * (len(names) + ("self" in own_parameters))))
    except TypeError as error:
        return f"cannot be called with the host's {len(names)} argument(s): {error}"
    return None


def _describe(value: Any) -> str:
    return type(value).__name__


def _type_name(expected: Any) -> str:
    if isinstance(expected, tuple):
        return " or ".join(item.__name__ for item in expected)
    return expected.__name__


def check_rules(rules_class: Any, report: Report) -> None:
    """Check a ``GameRules`` class: construction, signatures, a dummy call of every callable hook."""
    if not (inspect.isclass(rules_class) and issubclass(rules_class, BaseGameRules)):
        report.errors.append("rules.GameRules must be a subclass of plugins.base_game_rules.BaseGameRules")
        return
    try:
        rules = rules_class()
    except Exception as error:  # noqa: BLE001 - whatever a plugin raises is the finding
        report.errors.append(f"GameRules() cannot be built without a main window: {type(error).__name__}: {error}")
        return

    for hook in HOOKS:
        if not hasattr(rules, hook.name):
            if hook.on_base:
                report.errors.append(f"{hook.name}: missing (BaseGameRules defines it; do not delete it)")
            continue
        member = getattr(rules, hook.name)
        if hook.kind != "method":
            continue
        if not callable(member):
            report.errors.append(f"{hook.name}: must be a method, found {_describe(member)}")
            continue
        if hook.on_base:
            problem = _accepts(getattr(rules_class, hook.name), getattr(BaseGameRules, hook.name))
            if problem:
                report.errors.append(f"{hook.name}: {problem}")
                continue
        if hook.call is None:
            continue
        try:
            result = member(*hook.call)
        except Exception as error:  # noqa: BLE001
            shown = ", ".join(repr(argument) for argument in hook.call)
            report.errors.append(f"{hook.name}({shown}) raised {type(error).__name__}: {error}")
            continue
        if result is None:
            if hook.returns is not None and not hook.optional:
                report.errors.append(f"{hook.name}: returned None, expected {_type_name(hook.returns)}")
        elif hook.returns is not None and not isinstance(result, hook.returns):
            report.errors.append(f"{hook.name}: returned {_describe(result)}, expected {_type_name(hook.returns)}")
        elif hook.name == "get_spellcheck_ignore_pattern":
            try:
                re.compile(result)
            except re.error as error:
                report.errors.append(f"get_spellcheck_ignore_pattern: not a valid regex ({error})")
        elif hook.name == "load_data_from_json_obj":
            if not (len(result) == 2 and isinstance(result[0], list) and isinstance(result[1], dict)):
                report.errors.append("load_data_from_json_obj: must return (list of blocks, dict of block names)")
        elif hook.name == "get_problem_definitions":
            nameless = [key for key, value in result.items() if not (isinstance(value, dict) and value.get("name"))]
            if nameless:
                report.errors.append(f"get_problem_definitions: entries without a 'name': {nameless[:3]}")


# -- source code -------------------------------------------------------------------

def _host_attribute(node: ast.AST) -> Optional[str]:
    """``X`` in ``self.mw.X`` / ``mw.X`` / ``getattr(self.mw, "X", …)``."""
    def is_host(value: ast.AST) -> bool:
        return (isinstance(value, ast.Name) and value.id in _HOST_NAMES) or (
            isinstance(value, ast.Attribute) and value.attr in _HOST_NAMES
        )

    if isinstance(node, ast.Attribute) and is_host(node.value):
        return node.attr
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("getattr", "hasattr", "setattr")
        and len(node.args) >= 2
        and is_host(node.args[0])
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    ):
        return node.args[1].value
    return None


def check_sources(paths: Iterable[Path], report: Report, root: Optional[Path] = None) -> None:
    """Warn about main-window attributes outside ``MAIN_WINDOW_ATTRIBUTES``."""
    outside: Dict[str, str] = {}
    for path in sorted(paths):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as error:
            report.errors.append(f"{path.name}: cannot be parsed ({error})")
            continue
        for node in ast.walk(tree):
            name = _host_attribute(node)
            if name and name not in MAIN_WINDOW_ATTRIBUTES and not name.startswith("__"):
                shown = path.relative_to(root) if root else path.name
                outside.setdefault(name, f"{shown}:{getattr(node, 'lineno', 0)}")
    for name, where in sorted(outside.items()):
        report.warnings.append(f"uses main-window attribute '{name}' ({where}), which is not in the allowed list")


# -- one plugin ----------------------------------------------------------------------

def validate_plugin(name: str, root: Path = PLUGINS_DIR) -> Report:
    report = Report(name)
    folder = root / name
    config_path = folder / "config.json"
    if not config_path.is_file():
        report.errors.append("no config.json: the application will not list this plugin")
        return report
    config = _read_json(config_path, report)
    if config is not None:
        check_config(config, report)
    if (folder / "font_map.json").is_file():
        font_map = _read_json(folder / "font_map.json", report)
        if font_map is not None:
            check_font_map(font_map, report)
    prompts_path = folder / "translation_prompts" / "prompts.json"
    if prompts_path.is_file():
        prompts = _read_json(prompts_path, report)
        if prompts is not None:
            check_prompts(prompts, report)

    try:
        module = importlib.import_module(f"plugins.{name}.rules")
    except Exception as error:  # noqa: BLE001
        report.errors.append(f"plugins.{name}.rules cannot be imported: {type(error).__name__}: {error}")
        return report
    rules_class = getattr(module, "GameRules", None)
    if rules_class is None:
        report.errors.append("rules.py defines no class named GameRules")
        return report
    check_rules(rules_class, report)

    try:
        defaults = importlib.import_module(f"plugins.{name}.config")
    except ModuleNotFoundError:
        defaults = None
    except Exception as error:  # noqa: BLE001
        report.errors.append(f"plugins.{name}.config cannot be imported: {type(error).__name__}: {error}")
        defaults = None
    if defaults is not None:
        for constant in ("DEFAULT_AUTOFIX_SETTINGS", "DEFAULT_DETECTION_SETTINGS"):
            value = getattr(defaults, constant, {})
            if not isinstance(value, dict):
                report.errors.append(f"config.py: {constant} must be a dict of problem id -> bool")

    check_sources((p for p in folder.rglob("*.py") if "__pycache__" not in p.parts), report, root=folder)
    return report


def main(argv: Sequence[str]) -> int:
    names = list(argv) or plugin_names()
    reports = [validate_plugin(name) for name in names]
    print("\n".join(report.render() for report in reports))
    return 0 if all(report.ok for report in reports) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
