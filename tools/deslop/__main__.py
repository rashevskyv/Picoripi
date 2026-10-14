"""Command line for the deslop checks: scan, list rules, print a summary, compare or update the baseline."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import List, Optional

from tools.deslop import engine
from tools.deslop.rules import RULES, is_test_path


def _print_summary(result: engine.Scan) -> None:
    tests: Counter = Counter()
    product: Counter = Counter()
    per_file: Counter = Counter()
    for item in result.violations:
        (tests if is_test_path(item.path) else product)[item.rule] += 1
        if item.rule == "call-only-assertions":
            per_file[item.path] += 1
    print(f"{'rule':<26}{'tests':>8}{'product':>9}")
    for rule_id in sorted(RULES):
        if tests[rule_id] or product[rule_id]:
            print(f"{rule_id:<26}{tests[rule_id]:>8}{product[rule_id]:>9}")
    print("top files for call-only-assertions:")
    for path, count in per_file.most_common(10):
        print(f"  {count:>4}  {path}")


def _list_rules() -> None:
    for rule in RULES.values():
        state = "on " if rule.default_on else "off"
        print(f"{rule.id:<26}{state}  {rule.scope:<6}  {rule.why}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.deslop", description="Flag low-evidence code patterns.")
    parser.add_argument("paths", nargs="*", default=["."], help="files or folders, relative to the repository root")
    parser.add_argument("--rule", action="append", default=[], metavar="ID", help="also run this opt-in rule")
    parser.add_argument("--baseline", type=Path, metavar="FILE", help="fail only where a count grows over FILE")
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="write the counts of the enabled rules to FILE (default: tools/deslop/baseline.json)",
    )
    parser.add_argument("--summary", action="store_true", help="print totals per rule and the top call-only files")
    parser.add_argument("--list-rules", action="store_true", help="list the rules and exit")
    args = parser.parse_args(argv)

    if args.list_rules:
        _list_rules()
        return 0

    settings = engine.load_config()
    try:
        options = engine.resolve_options(settings)
        rule_ids = engine.enabled_rule_ids(settings, args.rule)
    except ValueError as error:
        print(f"deslop: {error}", file=sys.stderr)
        return 2

    result = engine.scan(args.paths, rule_ids=rule_ids, options=options, excludes=engine.excludes_from(settings))
    for error in result.errors:
        print(f"deslop: skipped {error}", file=sys.stderr)
    print(f"deslop: scanned {len(result.files)} files in {result.seconds:.2f} s")
    if args.summary:
        _print_summary(result)

    if args.update_baseline:
        target = args.baseline or engine.BASELINE
        engine.write_baseline(target, engine.counts_of(result.violations), result.files)
        print(f"deslop: baseline written to {target}")
        return 0

    if args.baseline is not None:
        grown = engine.growth(engine.counts_of(result.violations), engine.load_baseline(args.baseline))
        for path, rule_id, old, new in grown:
            print(f"{path}: [{rule_id}] {old} -> {new}; fix the new ones or suppress them with a reason")
        if grown:
            print("deslop: counts grew. Lower them, or after a review run: python -m tools.deslop --update-baseline")
            return 1
        print("deslop: no count grew over the baseline")
        return 0

    for item in result.violations:
        print(item)
    if result.violations:
        print(f"deslop: {len(result.violations)} violation(s)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
