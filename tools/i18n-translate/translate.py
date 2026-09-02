"""Translate Picoripi UI strings from locales/en.json into every language in languages.json.

One string per request {"text", "languages"} -> {"code": "translation", ...}
against the local Gemini Web2API proxy, multithreaded. Missing keys resume on re-run.

Russian is not a Picoripi UI language. During development keep English in tr("...")
and locales/uk.json; run run.bat before deploy to fill the other catalogs.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
except ImportError:  # sync-only does not need the proxy client
    requests = None

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
I18N = REPO / "locales"
SRC_ROOTS = [
    REPO / "ui",
    REPO / "components",
    REPO / "dialogs",
    REPO / "handlers",
    REPO / "main.py",
]
LANGS = json.loads((ROOT / "languages.json").read_text(encoding="utf-8"))
LANGS.pop("ru", None)
FAIL_LOG = ROOT / "failures.log"
LANGUAGE_NAME_KEY = "@language_name"

PROMPT = """You are a translation engine for the UI of Picoripi, a desktop localization workbench for game text (Python, PyQt6).

INPUT (JSON): {{"text": "<english_ui_string>", "languages": ["<code>", ...]}}
OUTPUT (JSON only): {{"<code>": "<translation>", ...}}

LANGUAGE CODES:
{table}

RULES:
1. Output ONLY the JSON object. No markdown, no code fences, no explanations, no thinking.
2. Answer with every requested code, using exactly the codes listed above.
3. Preserve placeholders exactly: {{name}}, {{0}}, %s, %d, and HTML tags such as <b>, <br>, <code>.
4. Preserve newlines as \\n escapes and keep the same number of lines.
5. Keep Qt mnemonics: a leading or inner & marks the shortcut letter (example: &File). Put & on a sensible letter in the translation.
6. Leave product and brand names untouched: Picoripi, MemePalace, Gemini, Web2API, WebTOP, BFN, BMG, Twilight Princess, Zelda.
7. These are short UI labels, buttons, dialogs and tooltips: translate naturally and concisely, the way a native desktop app would word it.
8. If the text is a bare technical token, file extension, path, or already the target language, return it unchanged.
9. Do not translate into Russian. If a requested code were ru it would be a mistake; it will not be requested.
10. If the input includes "ukrainian", that is the approved Ukrainian UI wording. Use it as extra context for meaning and tone when translating into other languages.
"""


def build_prompt(codes):
    table = "\n".join(f"{c} = {LANGS[c]}" for c in codes)
    return PROMPT.format(table=table)


def extract_json(content):
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if fence:
        content = fence.group(1)
    first, last = content.find("{"), content.rfind("}")
    if first < 0 or last <= first:
        raise ValueError(f"no JSON object in reply: {content[:200]!r}")
    body = re.sub(r",\s*([}\]])", r"\1", content[first : last + 1])
    return json.loads(body)


PLACEHOLDER = re.compile(r"\{[^{}]+\}|%[sd]|</?[a-zA-Z][^>]*>")


def problems(src, dst):
    if src.count("\n") != dst.count("\n"):
        return f"{src.count(chr(10))} newlines became {dst.count(chr(10))}"
    src_ph = PLACEHOLDER.findall(src)
    dst_ph = PLACEHOLDER.findall(dst)
    if src_ph != dst_ph:
        return f"placeholders {src_ph} became {dst_ph}"
    return None


def retry_after(resp, default):
    try:
        return max(0.0, float(resp.headers.get("Retry-After")))
    except (AttributeError, TypeError, ValueError):
        return default


def translate(session, args, text, codes, ukrainian=None):
    user = {"text": text, "languages": codes}
    if ukrainian and "uk" not in codes:
        user["ukrainian"] = ukrainian
    payload = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": build_prompt(codes)},
            {"role": "user", "content": json.dumps(user, ensure_ascii=True)},
        ],
        "stream": False,
    }
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    last, waited, attempt = None, 0, 0
    while attempt <= args.retries:
        try:
            r = session.post(args.url, data=body, headers={"Content-Type": "application/json"}, timeout=args.timeout)
            r.raise_for_status()
            out = extract_json(r.json()["choices"][0]["message"]["content"])
            missing = [c for c in codes if not isinstance(out.get(c), str) or not out[c].strip()]
            if missing:
                raise ValueError(f"reply is missing {','.join(missing)}")
            bad = [f"{c}: {problems(text, out[c])}" for c in codes if problems(text, out[c])]
            if bad:
                raise ValueError("; ".join(bad))
            return {c: out[c] for c in codes}
        except Exception as e:
            resp = getattr(e, "response", None)
            if getattr(resp, "status_code", None) == 429 and waited < args.max_wait:
                nap = min(retry_after(resp, args.cooldown), args.max_wait - waited)
                waited += nap
                print(f"  rate limited, waiting {nap:.0f}s ({waited:.0f}/{args.max_wait:.0f}s used)")
                time.sleep(nap)
                continue
            last = e
            attempt += 1
            if attempt <= args.retries:
                time.sleep(args.retry_delay * attempt)
    raise RuntimeError(last)


_STYLE = {}


def load(code):
    path = I18N / f"{code}.json"
    if not path.exists():
        return {}
    raw = path.read_bytes().decode("utf-8")
    m = re.search(r'\r?\n( +)"', raw)
    _STYLE[code] = (len(m.group(1)) if m else 2, "\r\n" if "\r\n" in raw else "\n")
    return json.loads(raw)


def save(code, data):
    I18N.mkdir(parents=True, exist_ok=True)
    indent, eol = _STYLE.get(code, (2, "\n"))
    ordered = {k: data[k] for k in sorted(data, key=lambda s: (s.lower(), s))}
    text = (json.dumps(ordered, ensure_ascii=False, indent=indent) + "\n").replace("\n", eol)
    path = I18N / f"{code}.json"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


def _py_files():
    files = []
    for root in SRC_ROOTS:
        if root.is_file() and root.suffix == ".py":
            files.append(root)
        elif root.is_dir():
            files.extend(root.rglob("*.py"))
    return files


def source_strings():
    """Every tr(\"...\") / tr('...') literal the app uses."""
    found = set()
    for path in _py_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name != "tr" or not node.args:
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.strip():
                found.add(arg.value)
    return found


def sync_en(en):
    used = source_strings()
    missing = sorted(used - set(en))
    extra = [key for key in list(en) if key not in used and not str(key).startswith("@")]
    for key in extra:
        en.pop(key, None)
    for key in missing:
        en[key] = key
    return missing, extra


def build_jobs(en, data, codes, force=False):
    jobs = []
    for key in en:
        if str(key).startswith("@"):
            continue
        todo = [c for c in codes if force or not data[c].get(key, "").strip()]
        if todo:
            jobs.append((key, en[key] or key, todo))
    return jobs


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default="http://127.0.0.1:8081/v1/chat/completions")
    p.add_argument("--model", default="gemini-3.6-flash")
    p.add_argument("--threads", type=int, default=6)
    p.add_argument("--langs", help="comma separated subset, e.g. uk,de")
    p.add_argument("--limit", type=int, help="only the first N strings (smoke test)")
    p.add_argument("--force", action="store_true", help="re-translate keys that already exist")
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--retry-delay", type=float, default=2.0)
    p.add_argument("--cooldown", type=float, default=60.0)
    p.add_argument("--max-wait", type=float, default=1800.0)
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--flush-every", type=int, default=25)
    p.add_argument("--no-sync", action="store_true", help="skip adding source literals missing from en.json")
    p.add_argument("--sync-only", action="store_true", help="only refresh en.json from tr() literals")
    return p


def main():
    args = build_parser().parse_args()
    I18N.mkdir(parents=True, exist_ok=True)

    codes = [c.strip() for c in args.langs.split(",")] if args.langs else list(LANGS)
    unknown = [c for c in codes if c not in LANGS]
    if unknown:
        sys.exit(f"unknown language code(s): {', '.join(unknown)}")
    if "ru" in codes:
        sys.exit("Russian is not a Picoripi UI language")

    en = load("en")
    en.setdefault(LANGUAGE_NAME_KEY, "English")
    if not args.no_sync:
        added, extra = sync_en(en)
        save("en", en)
        if added:
            print(f"en.json: added {len(added)} string(s) the code uses but English lacked")
            for key in added[:8]:
                print(f"    {key[:70]!r}")
            if len(added) > 8:
                print(f"    ... and {len(added) - 8} more")
        if extra:
            print(f"en.json: dropped {len(extra)} stale key(s) no longer in tr() calls")

    if args.sync_only:
        print(f"{len(en)} English keys")
        return

    if requests is None:
        sys.exit("The requests package is required to translate. pip install requests")

    data = {c: load(c) for c in codes}
    for c in codes:
        native = LANGS.get(c)
        if native:
            data[c][LANGUAGE_NAME_KEY] = native
    uk_catalog = data["uk"] if "uk" in data else load("uk")
    jobs = build_jobs(en, data, codes, args.force)
    if args.limit:
        jobs = jobs[: args.limit]

    if not jobs:
        for c in codes:
            save(c, data[c])
        print("Nothing to translate: every language already has every key.")
        return

    print(f"{len(en)} source strings | {len(jobs)} need work | {len(codes)} languages | {args.threads} threads")
    print(f"proxy: {args.url} ({args.model})\n")

    lock = threading.Lock()
    state = {"done": 0, "failed": 0, "dirty": set()}
    started = time.monotonic()
    FAIL_LOG.write_text("", encoding="utf-8")

    def worker(job):
        key, text, todo = job
        session = requests.Session()
        try:
            uk_hint = uk_catalog.get(key) or None
            return job, translate(session, args, text, todo, ukrainian=uk_hint), None
        except Exception as e:
            return job, None, e
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        futures = [pool.submit(worker, j) for j in jobs]
        for f in as_completed(futures):
            (key, text, todo), out, err = f.result()
            with lock:
                state["done"] += 1
                n = state["done"]
                preview = text.replace("\n", " ")[:52]
                if err:
                    state["failed"] += 1
                    print(f"[{n:>5}/{len(jobs)}] FAIL {' '.join(todo)} | {preview} -> {err}")
                    with FAIL_LOG.open("a", encoding="utf-8") as fh:
                        fh.write(f"{key!r}\t{','.join(todo)}\t{err}\n")
                    continue
                for c in todo:
                    data[c][key] = out[c]
                state["dirty"].update(todo)
                print(f"[{n:>5}/{len(jobs)}] ok   {' '.join(todo)} | {preview}")
                if n % args.flush_every == 0:
                    for c in state["dirty"]:
                        save(c, data[c])
                    state["dirty"].clear()

    for c in codes:
        save(c, data[c])

    took = time.monotonic() - started
    print(f"\ndone in {took / 60:.1f} min | {state['done'] - state['failed']} translated, {state['failed']} failed")
    for c in codes:
        missing = sum(1 for k in en if not data[c].get(k, "").strip())
        print(f"  {c}: {len(data[c]):>5} keys, {missing} still missing")
    if state["failed"]:
        print(f"\nfailures logged to {FAIL_LOG} - re-run; missing keys are picked up again")


if __name__ == "__main__":
    main()
