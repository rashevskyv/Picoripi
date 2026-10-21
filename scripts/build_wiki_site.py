"""Build the wiki (``docs/wiki`` and ``docs/wiki/uk``) into a static website: one HTML page per Markdown page.

``python scripts/build_wiki_site.py <output folder>`` writes ``index.html`` (the wiki README) and the pages, copies
``img/``, turns ``.md`` links into ``.html`` links and draws ``mermaid`` blocks in the browser. The GitHub workflow
``.github/workflows/wiki-site.yml`` runs it and publishes the result with GitHub Pages.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import markdown

WIKI = Path(__file__).resolve().parents[1] / "docs" / "wiki"
REPO_URL = "https://github.com/rashevskyv/Picoripi/blob/main"
DOMAIN = "picoripi.customfw.xyz"   # the custom domain GitHub Pages serves the site on
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.esm.min.mjs"
STYLE = """
:root{--bg:#fff;--fg:#1d2330;--mut:#5b6577;--line:#d9deea;--acc:#2456d6;--code:#f3f5fa}
@media(prefers-color-scheme:dark){:root{--bg:#14171f;--fg:#e6e9f2;--mut:#9aa3b8;--line:#2a3042;--acc:#8ab0ff;--code:#1c2030}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,'Segoe UI',sans-serif}
header{border-bottom:1px solid var(--line);padding:10px 16px}header a{margin-right:16px;color:var(--acc);text-decoration:none}
main{max-width:900px;margin:0 auto;padding:16px 16px 64px}
a{color:var(--acc)}img{max-width:100%;border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;display:block;overflow-x:auto}th,td{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
code{background:var(--code);padding:1px 5px;border-radius:4px}pre{background:var(--code);padding:12px;overflow-x:auto;border-radius:6px}pre code{padding:0}
"""
FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
LINK = re.compile(r'href="([^"#:]*?\.md)(#[^"]*)?"')
MERMAID_BLOCK = re.compile(r'<pre><code class="language-mermaid">(.*?)</code></pre>', re.S)


def _link(source: Path, target: str, anchor: str) -> str:
    """The href of a link to a Markdown file: another wiki page becomes ``.html``; a file elsewhere in the repository
    (README, FEATURES, ...) becomes its GitHub page."""
    resolved = (source.parent / target).resolve()
    try:
        resolved.relative_to(WIKI)
    except ValueError:
        return f'href="{REPO_URL}/{resolved.relative_to(WIKI.parents[1]).as_posix()}{anchor}"'
    page = "index.html" if resolved.name == "README.md" else resolved.with_suffix(".html").name
    folder = "uk/" if resolved.parent.name == "uk" else ""
    here = "uk/" if source.parent.name == "uk" else ""
    prefix = "../" * (1 if here and not folder else 0) + (folder if (folder and not here) else "")
    return f'href="{prefix}{page}{anchor}"'

def render(source: Path, language: str) -> str:
    """The HTML page of one Markdown file."""
    text = FRONT_MATTER.sub("", source.read_text(encoding="utf-8"))
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    body = LINK.sub(lambda m: _link(source, m.group(1), m.group(2) or ""), body)
    body = MERMAID_BLOCK.sub(lambda m: f'<pre class="mermaid">{m.group(1)}</pre>', body)
    title = re.search(r"<h1>(.*?)</h1>", body)
    root = "" if source.parent == WIKI else "../"
    nav = (f'<a href="{root}index.html">English</a><a href="{root}uk/index.html">Українська</a>'
           f'<a href="https://github.com/rashevskyv/Picoripi">GitHub</a>')
    script = f'<script type="module">import mermaid from "{MERMAID}";mermaid.initialize({{startOnLoad:true}});</script>'
    return (f'<!doctype html><html lang="{language}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{re.sub("<[^>]+>", "", title.group(1)) if title else "Picoripi"}</title><style>{STYLE}</style></head>'
            f'<body><header>{nav}</header><main>{body}</main>{script}</body></html>')


def build(output: Path) -> int:
    """Write the site into ``output`` (made if missing). Returns the number of pages."""
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    count = 0
    for folder, language in ((WIKI, "en"), (WIKI / "uk", "uk")):
        target = output if folder == WIKI else output / "uk"
        target.mkdir(parents=True, exist_ok=True)
        for source in sorted(folder.glob("*.md")):
            name = "index" if source.name == "README.md" else source.stem
            (target / f"{name}.html").write_text(render(source, language), encoding="utf-8")
            count += 1
    if (WIKI / "img").is_dir():
        shutil.copytree(WIKI / "img", output / "img")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    (output / "CNAME").write_text(DOMAIN + "\n", encoding="utf-8")
    return count


if __name__ == "__main__":
    pages = build(Path(sys.argv[1] if len(sys.argv) > 1 else "wiki_site"))
    print(f"wiki site: {pages} pages")
