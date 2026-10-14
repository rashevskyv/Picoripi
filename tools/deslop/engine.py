"""File discovery, suppression, configuration, scan and baseline for the deslop checks.

Configuration is ``[tool.deslop]`` in ``pyproject.toml``. A TOML reader is needed only to load it:
``tomllib`` (Python 3.11+), else ``tomli``. Without either, the defaults apply and a warning is printed.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

from tools.deslop.rules import DEFAULT_OPTIONS, RULES, Module, Rule

try:  # pragma: no cover - depends on the interpreter
    import tomllib as _toml
except ModuleNotFoundError:  # Python 3.10
    try:
        import tomli as _toml
    except ModuleNotFoundError:
        _toml = None

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).resolve().parent / "baseline.json"
# Directories skipped by name anywhere (hidden directories are always skipped).
SKIP_NAMES = frozenset({"__pycache__"})
# Directories skipped by repo-relative path.
DEFAULT_EXCLUDES = ("venv", "build", "dist", "graphify-out", "font_tool", "gemini", "companion/venv", "node_modules")
SUPPRESS = re.compile(r"#\s*deslop:\s*ignore(?:\[([^\]]*)\])?")


@dataclass(frozen=True)
class Violation:
    rule: str
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}"


@dataclass
class Scan:
    violations: List[Violation] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    seconds: float = 0.0


def load_config(root: Path = ROOT) -> Dict[str, Any]:
    """The ``[tool.deslop]`` table, or an empty table when it is missing or cannot be read."""
    path = root / "pyproject.toml"
    if not path.exists():
        return {}
    if _toml is None:
        print("deslop: no TOML reader (tomllib or tomli); [tool.deslop] ignored, defaults used", file=sys.stderr)
        return {}
    data = _toml.loads(path.read_text(encoding="utf-8"))
    return dict(data.get("tool", {}).get("deslop", {}))


def resolve_options(settings: Dict[str, Any]) -> Dict[str, Any]:
    options = dict(DEFAULT_OPTIONS)
    for key, value in settings.items():
        name = key.replace("-", "_")
        if name in ("enable", "disable", "exclude"):
            continue
        if name not in DEFAULT_OPTIONS:
            raise ValueError(f"unknown [tool.deslop] option: {key}")
        options[name] = value
    return options


def default_rule_ids() -> FrozenSet[str]:
    return frozenset(rule_id for rule_id, rule in RULES.items() if rule.default_on)


def enabled_rule_ids(settings: Dict[str, Any], extra: Iterable[str] = ()) -> Set[str]:
    """Default-on rules, plus ``enable`` from the config, minus ``disable``, plus the command-line rules."""
    chosen = (set(default_rule_ids()) | set(settings.get("enable", []))) - set(settings.get("disable", []))
    chosen |= set(extra)
    unknown = chosen - set(RULES)
    if unknown:
        raise ValueError("unknown deslop rule: " + ", ".join(sorted(unknown)))
    return chosen


def excludes_from(settings: Dict[str, Any]) -> Tuple[str, ...]:
    return DEFAULT_EXCLUDES + tuple(str(item).strip("/") for item in settings.get("exclude", []))


def _rel_posix(path: str, root: Path) -> str:
    rel = os.path.relpath(os.path.abspath(path), root)
    return "" if rel == "." else rel.replace("\\", "/")


def _is_excluded(rel: str, excludes: Sequence[str]) -> bool:
    return any(rel == item or rel.startswith(item + "/") for item in excludes)


def iter_python_files(starts: Sequence[str], root: Path, excludes: Sequence[str]) -> Iterator[Path]:
    for start in starts:
        for dirpath, dirnames, filenames in os.walk(Path(root, start)):
            base = _rel_posix(dirpath, root)
            kept = []
            for name in dirnames:
                if name.startswith(".") or name in SKIP_NAMES:
                    continue
                rel = f"{base}/{name}" if base else name
                if not _is_excluded(rel, excludes):
                    kept.append(name)
            dirnames[:] = sorted(kept)
            for name in sorted(filenames):
                if name.endswith(".py"):
                    yield Path(dirpath, name)


def _suppressed(lines: Sequence[str], line: int, rule_id: str) -> bool:
    if not 0 < line <= len(lines):
        return False
    match = SUPPRESS.search(lines[line - 1])
    if match is None:
        return False
    listed = match.group(1)
    return listed is None or rule_id in {item.strip() for item in listed.split(",")}


def _module_findings(module: Module, rule_ids: Iterable[str]) -> Iterator[Tuple[str, int, str]]:
    for rule_id in rule_ids:
        rule = RULES[rule_id]
        if rule.check is None or (rule.scope == "tests" and not module.is_test):
            continue
        for line, message in rule.check(module):
            yield rule_id, line, message


def lint_source(
    source: str,
    path: str = "tests/test_sample.py",
    rule_ids: Optional[Iterable[str]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> List[Violation]:
    """Run the per-file rules over one source text. Used by the rule tests."""
    chosen = sorted(default_rule_ids() if rule_ids is None else set(rule_ids))
    module = Module(path, ast.parse(source, filename=path), {**DEFAULT_OPTIONS, **(options or {})})
    lines = source.splitlines()
    return [
        Violation(rule_id, path, line, message)
        for rule_id, line, message in _module_findings(module, chosen)
        if not _suppressed(lines, line, rule_id)
    ]


def scan(
    starts: Sequence[str] = (".",),
    *,
    rule_ids: Iterable[str],
    options: Optional[Dict[str, Any]] = None,
    excludes: Sequence[str] = DEFAULT_EXCLUDES,
    root: Path = ROOT,
) -> Scan:
    """Parse every Python file under ``starts`` once and run the chosen rules on it."""
    started = time.perf_counter()
    chosen = sorted(set(rule_ids))
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    per_file = [rule_id for rule_id in chosen if RULES[rule_id].collect is None]
    project: List[Rule] = [RULES[rule_id] for rule_id in chosen if RULES[rule_id].collect is not None]
    result = Scan()
    entries: Dict[str, Dict[Any, List[Tuple[str, int, str]]]] = {rule.id: defaultdict(list) for rule in project}
    lines_by_path: Dict[str, List[str]] = {}

    for path in iter_python_files(starts, root, excludes):
        rel = _rel_posix(str(path), root)
        result.files.append(rel)
        raw = path.read_bytes()
        try:
            tree = ast.parse(raw, filename=rel)
        except (SyntaxError, ValueError) as error:
            result.errors.append(f"{rel}: {error}")
            continue
        module = Module(rel, tree, opts)
        lines = raw.decode("utf-8", errors="replace").splitlines()
        for rule_id, line, message in _module_findings(module, per_file):
            if not _suppressed(lines, line, rule_id):
                result.violations.append(Violation(rule_id, rel, line, message))
        for rule in project:
            if rule.scope == "tests" and not module.is_test:
                continue
            for line, key, name in rule.collect(module):
                entries[rule.id][key].append((rel, line, name))
                lines_by_path[rel] = lines

    for rule in project:
        for rel, items in rule.report(entries[rule.id]).items():
            lines = lines_by_path.get(rel, [])
            for line, message in items:
                if not _suppressed(lines, line, rule.id):
                    result.violations.append(Violation(rule.id, rel, line, message))

    result.violations.sort(key=lambda item: (item.path, item.line, item.rule))
    result.seconds = time.perf_counter() - started
    return result


def counts_of(violations: Iterable[Violation]) -> Dict[str, Dict[str, int]]:
    """Violation counts: {repo-relative path: {rule id: count}}."""
    found: Dict[str, Dict[str, int]] = {}
    for item in violations:
        per_rule = found.setdefault(item.path, {})
        per_rule[item.rule] = per_rule.get(item.rule, 0) + 1
    return found


def load_baseline(path: Path = BASELINE) -> Dict[str, Dict[str, int]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def growth(current: Dict[str, Dict[str, int]], baseline: Dict[str, Dict[str, int]]) -> List[Tuple[str, str, int, int]]:
    """(path, rule, old, new) for every count that is higher than the baseline allows."""
    grown = []
    for path, per_rule in sorted(current.items()):
        for rule_id, count in sorted(per_rule.items()):
            old = baseline.get(path, {}).get(rule_id, 0)
            if count > old:
                grown.append((path, rule_id, old, count))
    return grown


def write_baseline(path: Path, current: Dict[str, Dict[str, int]], scanned: Iterable[str]) -> None:
    """Replace the entries of the scanned files; keep the entries of files that were not scanned."""
    data = load_baseline(path)
    for rel in scanned:
        data.pop(rel, None)
    for rel, per_rule in current.items():
        data[rel] = dict(sorted(per_rule.items()))
    text = json.dumps({key: data[key] for key in sorted(data)}, indent=2) + "\n"
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temp, path)
