"""Wrap UI string literals in tr(), joining implicit concatenations.

Edits only the wrapped spans so the rest of the file keeps its formatting.
Idempotent. Skips f-strings and values already inside tr().
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
TARGETS = [REPO / "ui", REPO / "components", REPO / "dialogs", REPO / "handlers", REPO / "main.py"]
IMPORT = "from core.i18n import tr"
SKIP_DIRS = {"__pycache__", "tests"}

DOT_METHODS = {
    "setToolTip",
    "setWindowTitle",
    "setPlaceholderText",
    "setStatusTip",
    "setWhatsThis",
    "setText",
    "addMenu",
    "addTab",
    "addItem",
    "addRow",
    "addAction",
}
CTORS = {
    "QAction",
    "QLabel",
    "QPushButton",
    "QCheckBox",
    "QGroupBox",
    "QRadioButton",
    "QMenu",
    "QToolButton",
}
MSGBOX = {"information", "warning", "critical", "question"}


def should_skip_file(path: Path) -> bool:
    return any(p in SKIP_DIRS for p in path.parts)


def _skip_value(s: str) -> bool:
    t = s.strip()
    if not t:
        return True
    if t.isdigit():
        return True
    if re.fullmatch(r"[\d./:%\s]+", t):
        return True
    if len(t) <= 2 and t not in {"OK", "No", "Aa"}:
        return True
    return False


def _is_fstring(raw: str) -> bool:
    p = raw.lstrip()
    return p[:1] in "fF" or p[:2].lower() in ("rf", "fr")


def _lit(raw: str) -> str | None:
    if _is_fstring(raw):
        return None
    try:
        value = ast.literal_eval(raw)
    except Exception:
        return None
    return value if isinstance(value, str) else None


def _index(source: str, row: int, col: int) -> int:
    if row == 1:
        return col
    pos = 0
    current = 1
    while current < row:
        nl = source.find("\n", pos)
        if nl < 0:
            return len(source)
        pos = nl + 1
        current += 1
    return pos + col


def _iter_string_args(tokens, start):
    """Yield lists of (index, token) for each argument that is only string literals."""
    n = len(tokens)
    k = start
    depth = 1
    arg = []
    arg_pure = True
    while k < n and depth:
        t = tokens[k]
        if t.string == "(":
            depth += 1
            arg_pure = False
        elif t.string == ")":
            depth -= 1
            if depth == 0:
                if arg and arg_pure:
                    yield arg
                break
            arg_pure = False
        elif t.string == "," and depth == 1:
            if arg and arg_pure:
                yield arg
            arg = []
            arg_pure = True
            k += 1
            continue
        elif t.type == tokenize.STRING and depth == 1:
            if _lit(t.string) is None:
                arg_pure = False
            else:
                arg.append((k, t))
        elif t.type in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT):
            pass
        elif depth == 1:
            arg_pure = False
        k += 1


def _already_tr(tokens, first_idx):
    prev = first_idx - 1
    while prev >= 0 and tokens[prev].type in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT):
        prev -= 1
    if prev >= 0 and tokens[prev].string == "(":
        prev -= 1
        while prev >= 0 and tokens[prev].type in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT):
            prev -= 1
        return prev >= 0 and tokens[prev].string == "tr"
    return False


def _should_wrap(tokens, i) -> bool:
    tok = tokens[i]
    if tok.type != tokenize.NAME:
        return False
    name = tok.string
    prev = tokens[i - 1] if i else None
    if name in CTORS:
        return True
    if name in DOT_METHODS and prev is not None and prev.string == ".":
        return True
    if name in MSGBOX and prev is not None and prev.string == ".":
        # QMessageBox.information
        p2 = tokens[i - 2] if i >= 2 else None
        return p2 is not None and p2.string == "QMessageBox"
    return False


def process(source: str) -> str:
    readline = io.StringIO(source).readline
    try:
        tokens = list(tokenize.generate_tokens(readline))
    except tokenize.TokenError:
        return source

    replacements = []  # (start_idx, end_idx, text)
    n = len(tokens)
    i = 0
    while i < n:
        if _should_wrap(tokens, i):
            j = i + 1
            if j < n and tokens[j].string == "(":
                for strings in _iter_string_args(tokens, j + 1):
                    first_i = strings[0][0]
                    if _already_tr(tokens, first_i):
                        continue
                    first = strings[0][1]
                    last = strings[-1][1]
                    combined = "".join(_lit(t.string) or "" for _, t in strings)
                    if _skip_value(combined):
                        continue
                    start = _index(source, first.start[0], first.start[1])
                    end = _index(source, last.end[0], last.end[1])
                    replacements.append((start, end, "tr(" + repr(combined) + ")"))
        i += 1

    if not replacements:
        return source
    replacements.sort(key=lambda r: r[0], reverse=True)
    new = source
    last_applied = len(new) + 1
    for start, end, text in replacements:
        if end > last_applied:
            continue
        new = new[:start] + text + new[end:]
        last_applied = start
    if IMPORT not in new:
        new = _insert_import(new)
    return new


def _insert_import(text: str) -> str:
    lines = text.splitlines(keepends=True)
    last_imp = None
    depth = 0
    in_import = False
    for i, line in enumerate(lines):
        if depth == 0 and not line[:1].isspace() and line.startswith(("import ", "from ")):
            in_import = True
        if in_import:
            last_imp = i
            depth += line.count("(") - line.count(")")
            if depth <= 0:
                depth = 0
                in_import = False
    at = (last_imp + 1) if last_imp is not None else 0
    lines.insert(at, IMPORT + "\n")
    return "".join(lines)


def main():
    files = []
    for root in TARGETS:
        if root.is_file():
            files.append(root)
        else:
            files.extend(p for p in root.rglob("*.py") if not should_skip_file(p))
    changed = 0
    for path in files:
        raw = path.read_text(encoding="utf-8")
        new = process(raw)
        if new != raw:
            path.write_text(new, encoding="utf-8")
            changed += 1
            print(path.relative_to(REPO))
    print(f"updated {changed} files")


if __name__ == "__main__":
    main()
