"""The deslop ratchet: enabled rules (defaults plus [tool.deslop]) may not gain violations over tools/deslop/baseline.json.

The baseline holds counts per file and rule, never source text. Lower a count by fixing or suppressing
the violations. Refresh the baseline only after a review accepts a higher count:
``python -m tools.deslop --update-baseline``.
"""
from tools.deslop import engine


def test_default_rules_do_not_grow_over_the_baseline():
    assert engine.BASELINE.exists(), "tools/deslop/baseline.json is missing; run python -m tools.deslop --update-baseline"
    settings = engine.load_config()
    result = engine.scan(
        ["."],
        rule_ids=engine.enabled_rule_ids(settings),
        options=engine.resolve_options(settings),
        excludes=engine.excludes_from(settings),
    )

    grown = engine.growth(engine.counts_of(result.violations), engine.load_baseline())

    lines = [f"{path}: [{rule}] {old} -> {new}" for path, rule, old, new in grown]
    assert not grown, "deslop counts grew over tools/deslop/baseline.json:\n" + "\n".join(lines)
