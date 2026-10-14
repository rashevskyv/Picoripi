"""deslop for Python: flags low-evidence code patterns (slop) with stdlib ``ast`` checks.

Run it with ``python -m tools.deslop [paths] [--rule ID] [--baseline FILE] [--update-baseline]``, or
``python tasks.py deslop``. Rules are in ``rules.py``, scanning and the baseline in ``engine.py``.

Credits (both MIT): the ideas come from https://github.com/maharshi365/deslop, whose generic rules are
vendored from https://github.com/dmmulroy/anti-slop (copyright Dillon Mulroy). This is a Python port of
those ideas; no JavaScript code is copied. The TypeScript-only rules (unknown, typeof, Reflect,
Tailwind) have no Python counterpart and are not ported.
"""
