---
name: deslop
description: Check Picoripi code for slop with tools/deslop and fix the new findings. Trigger: /deslop, "деслоп", "перевір деслопом", "deslop". Also run it at every stop point of Picoripi work, before a report, before a work-package commit and before an integration audit verdict.
---

# Deslop

`tools/deslop` flags low-evidence code patterns. The baseline (`tools/deslop/baseline.json`) holds the old counts.
The default run reports only findings that are new over that baseline. Full rule notes: `docs/ENGINEERING.md`, section "Slop checks (deslop)".

## When to run

- On request: `/deslop`, "деслоп", "перевір деслопом", "deslop".
- At every stop point:
  - before you write a report to the user;
  - before you commit a work package;
  - before an integration audit verdict.

## How

1. From the repository root, run `python tasks.py deslop`.
2. Exit 0 means no new findings. Go on.
3. Exit 1 lists the findings of each file and rule whose count grew. Fix each one:
   - Tests assert on the output of the code under test, or on state the caller can see.
     A test that only checks mock calls is not a check. Fix it.
   - Prefer explicit fakes over `MagicMock`.
   - A false positive: suppress it on the reported line with `# deslop: ignore[rule-id] <reason>`. Always name the rule and give a reason.
4. Run `python tasks.py deslop` again. Repeat until exit 0.

To survey every finding, run `python tasks.py deslop --all`. It exits 0. It is not the check.

## Rules

| Rule | Scope | Meaning |
|------|-------|---------|
| `call-only-assertions` | tests | A test checks only mock calls, not a result. |
| `module-mocking` | tests | A whole module is replaced, which hides the real dependency. |
| `poor-substring-tests` | tests | A short or generic substring passes for many wrong outputs. |
| `repeated-assert-call` | tests | The same assertion appears twice in a row. |
| `chained-cast` | all | A cast of a cast invents type evidence twice. |
| `getattr-literal` | all | A constant attribute name hides a plain attribute access. |
| `reduce-accumulator-copy` | all | A reducer copies its accumulator, which is quadratic. |
| `filter-map-chain` | all | A map over a filter reads better as one comprehension. |

Opt-in rules (`--rule ID`) are listed by `python -m tools.deslop --list-rules`.

## Report

Give the user, in a few lines:

- the counts per rule for the new findings;
- each new finding fixed, or suppressed, with its reason;
- the final exit code of `python tasks.py deslop`.

## Never

- Never run `--update-baseline` to make a failing run pass.
- Never raise a count in `tools/deslop/baseline.json`, and never edit that file by hand.
- Only an audit or the owner regenerates the baseline. The counts only go down.
- Never suppress a finding without a rule id and a reason.
