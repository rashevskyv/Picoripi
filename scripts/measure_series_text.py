"""Measure repeated and cross-game English text in the projects of a game series (read-only).

Reads each ``<root>/<game>/picoripi/project.uiproj`` with the Project Manager's own parser
(``core.project_library.plugin_facts``), so the counts match the Project Manager. Prints numbers only and
writes the full numbers to a JSON file. Game text stays in memory.

Usage (the venv interpreter, -I):
    python -I scripts/measure_series_text.py <series_root> <out_json> [--match-glob "*/picoripi/project.uiproj"]

"Normalised" replaces tag-like spans (``{...}``, ``[...]``, ``<...>``, ``\\n``, ``%d``, ``$NAME``) with ``#``.
That tag pattern is a generic guess for the series, not the plugins' tag syntax: the normalised numbers show an
upper bound for "differs only in tags". "Neutral" uses each plugin's own tag map (``get_series_tag_map``): a text
counts across games only with the same tag kinds in the same order, as the series memory does.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

REPO = Path(__file__).resolve().parent.parent
TAG = re.compile(r"\{[^{}]*\}|\[[^\[\]]*\]|<[^<>]*>|\\[nNpPlr]|%[0-9]*[sdx]|\$[A-Za-z0-9]+")


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", TAG.sub("#", text)).strip().lower()


def read_project(project_file: Path) -> Tuple[str, List[List[str]], int, Any]:
    """(plugin name, the English strings per counted block, number of blocks not counted, the plugin's tag map)."""
    from core.project_library import plugin_facts  # imported late: the repo root must be on sys.path

    data = json.loads(project_file.read_text(encoding="utf-8"))
    plugin = str(data.get("plugin_name") or "")
    rules = plugin_facts.default_load_rules(plugin)
    getter = getattr(rules, "get_series_tag_map", None)
    tag_map = getter() if callable(getter) else None
    base = project_file.parent
    metadata = data.get("metadata") or {}
    roots = [plugin_facts._root(base, metadata.get("source_path")), base]
    cache: Dict = {}
    blocks: List[List[str]] = []
    skipped = 0
    for block in data.get("blocks") or []:
        if (block.get("metadata") or {}).get("is_archive_member"):
            skipped += 1
            continue
        source = plugin_facts._resolve(str(block.get("source_file") or ""), roots)
        original = None
        if source is not None:
            original = plugin_facts._block_of(plugin_facts._parse(rules, source, cache), block.get("internal_key") or None)
        if original is None:
            skipped += 1
            continue
        blocks.append([str(text) for text in original if isinstance(text, str) and text.strip()])
    return plugin, blocks, skipped, tag_map


def neutral_key(text: str, tag_map: Any) -> str:
    """The series key with the plugin's tag kinds (plugins/common/series_tags.py); the generic key without a map."""
    from plugins.common.series_tags import neutral_of  # imported late: the repo root must be on sys.path

    if tag_map is None:
        return normalise(text)
    neutral = neutral_of(text, tag_map)
    return normalise(text) if neutral is None else neutral


def measure(projects: Dict[str, Tuple[str, List[List[str]], int, Any]]) -> dict:
    rows = []
    exact_games: Dict[str, Set[str]] = defaultdict(set)
    key_games: Dict[str, Set[str]] = defaultdict(set)
    exact_sets: Dict[str, Set[str]] = {}
    key_sets: Dict[str, Set[str]] = {}
    neutral_games: Dict[str, Set[str]] = defaultdict(set)
    for game, (plugin, blocks, skipped, tag_map) in projects.items():
        texts = [text for block in blocks for text in block]
        freq = Counter(texts)
        block_repeat = sum(1 for block in blocks if any(freq[text] > 1 for text in block))
        block_count: Counter = Counter()
        for block in blocks:
            block_count.update(set(block))
        repeated = [text for text, count in freq.items() if count > 1]
        in_one_block = sum(1 for text in repeated if block_count[text] == 1)
        keys = {normalise(text) for text in texts}
        rows.append({"game": game, "plugin": plugin, "blocks": len(blocks), "blocks_not_counted": skipped,
                     "strings": len(texts), "distinct_exact": len(freq),
                     "strings_repeating_text": sum(c for c in freq.values() if c > 1),
                     "distinct_texts_repeating": sum(1 for c in freq.values() if c > 1),
                     "blocks_with_a_repeat": block_repeat,
                     "repeated_texts_inside_one_block": in_one_block,
                     "repeated_texts_across_blocks": len(repeated) - in_one_block,
                     "distinct_normalised": len(keys),
                     "strings_with_tag_like_span": sum(1 for text in texts if TAG.search(text))})
        exact_sets[game] = set(freq)
        key_sets[game] = keys
        for text in freq:
            exact_games[text].add(game)
        for key in keys:
            key_games[key].add(game)
        for text in freq:
            neutral_games[neutral_key(text, tag_map)].add(game)
    names = list(projects)
    shared_neutral = [key for key, games in neutral_games.items() if len(games) > 1]
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared_exact = exact_sets[a] & exact_sets[b]
            shared_keys = key_sets[a] & key_sets[b]
            pairs.append({"a": a, "b": b, "same_plugin": projects[a][0] == projects[b][0],
                          "shared_exact": len(shared_exact), "shared_normalised": len(shared_keys),
                          "shared_normalised_up_to_2_words": sum(1 for k in shared_keys if len(k.split()) <= 2),
                          "shared_normalised_over_2_words": sum(1 for k in shared_keys if len(k.split()) > 2)})
    shared_keys = [key for key, games in key_games.items() if len(games) > 1]
    return {"games": rows, "pairs": pairs,
            "exact_distinct_texts": len(exact_games),
            "exact_texts_in_2_or_more_games": sum(1 for g in exact_games.values() if len(g) > 1),
            "exact_texts_in_5_or_more_games": sum(1 for g in exact_games.values() if len(g) >= 5),
            "normalised_distinct_texts": len(key_games),
            "normalised_texts_in_2_or_more_games": len(shared_keys),
            "normalised_shared_texts_up_to_2_words": sum(1 for k in shared_keys if len(k.split()) <= 2),
            "normalised_shared_texts_over_2_words": sum(1 for k in shared_keys if len(k.split()) > 2),
            "neutral_distinct_texts": len(neutral_games),
            "neutral_texts_in_2_or_more_games": len(shared_neutral),
            "neutral_shared_texts_up_to_2_words": sum(1 for k in shared_neutral if len(k.split()) <= 2),
            "neutral_shared_texts_over_2_words": sum(1 for k in shared_neutral if len(k.split()) > 2)}


def summary(report: dict) -> None:
    for row in report["games"]:
        print(f"{row['game']}: plugin={row['plugin']} strings={row['strings']} distinct={row['distinct_exact']} "
              f"repeating={row['strings_repeating_text']} blocks={row['blocks']} not_counted={row['blocks_not_counted']}")
    same = [p for p in report["pairs"] if p["same_plugin"]]
    other = [p for p in report["pairs"] if not p["same_plugin"]]
    print(f"pairs: {len(report['pairs'])} same plugin: {len(same)} other plugins: {len(other)}")
    for label, group in (("same plugin", same), ("other plugins", other)):
        if group:
            print(f"{label}: max exact shared {max(p['shared_exact'] for p in group)}, "
                  f"max normalised shared {max(p['shared_normalised'] for p in group)}")
    for key in ("exact_distinct_texts", "exact_texts_in_2_or_more_games", "exact_texts_in_5_or_more_games",
                "normalised_distinct_texts", "normalised_texts_in_2_or_more_games",
                "normalised_shared_texts_up_to_2_words", "normalised_shared_texts_over_2_words",
                "neutral_distinct_texts", "neutral_texts_in_2_or_more_games",
                "neutral_shared_texts_up_to_2_words", "neutral_shared_texts_over_2_words"):
        print(f"{key}: {report[key]}")


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("series_root", type=Path)
    parser.add_argument("out_json", type=Path)
    parser.add_argument("--match-glob", default="*/picoripi/project.uiproj")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(REPO))
    projects: Dict[str, Tuple[str, List[List[str]], int, Any]] = {}
    for project_file in sorted(args.series_root.glob(args.match_glob)):
        game = project_file.parent.parent.name
        try:
            projects[game] = read_project(project_file)
        except Exception as error:  # a measurement reports and goes on; it never writes
            print(f"{game}: not measured ({type(error).__name__})")
    report = measure(projects)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    summary(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
