"""The documents agree with the repository: paths exist, links resolve, EN and UK pages match (WP7 7.6)."""
import re
from pathlib import Path

import pytest

from tools import docs_index
from utils.constants import APP_VERSION

ROOT = Path(__file__).resolve().parents[2]

# Documents that describe the code as it is. Design documents, the open-items list and
# history may name files that are planned or gone.
CURRENT_DOCS = sorted(
    ["README.md", "AGENTS.md", "docs/INDEX.md", "docs/ARCHITECTURE.md", "docs/ENGINEERING.md", "docs/DECISIONS.md", "docs/FEATURES.md"]
    + [path.relative_to(ROOT).as_posix() for path in (ROOT / "docs" / "wiki").rglob("*.md")]
)
WIKI_PAGES = sorted(path.name for path in (ROOT / "docs" / "wiki").glob("*.md"))

TOP_LEVEL = {path.name for path in ROOT.iterdir() if path.is_dir() and not path.name.startswith(".")} | {".agents"}
BACKTICKED = re.compile(r"`([^`\s]+)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")
# Files the application or the user creates at run time, and placeholders.
NOT_IN_REPOSITORY = ("<", "*", "…", "...", "{")


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _repository_paths(text: str):
    """Backticked strings that claim to be a path from the repository root."""
    for found in BACKTICKED.findall(text):
        candidate = found.rstrip(".,:;").split("::")[0]
        if "/" not in candidate or any(mark in candidate for mark in NOT_IN_REPOSITORY):
            continue
        if candidate.split("/")[0] in TOP_LEVEL:
            yield candidate


@pytest.mark.parametrize("document", CURRENT_DOCS)
def test_backticked_repository_paths_exist(document):
    missing = sorted({path for path in _repository_paths(_text(document)) if not (ROOT / path).exists()})

    assert missing == [], f"{document} names paths that do not exist"


@pytest.mark.parametrize("document", CURRENT_DOCS)
def test_relative_links_resolve(document):
    folder = (ROOT / document).parent
    broken = []
    for target in LINK.findall(_text(document)):
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            continue
        if not (folder / target.split("#")[0]).exists():
            broken.append(target)

    assert broken == [], f"{document} links to files that do not exist"


def _heading_levels(text: str):
    in_code = False
    levels = []
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        elif not in_code and re.match(r"#{1,6} ", line):
            levels.append(len(line) - len(line.lstrip("#")))
    return levels


@pytest.mark.parametrize("page", WIKI_PAGES)
def test_a_ukrainian_wiki_page_has_the_same_sections_as_the_english_one(page):
    english = _heading_levels(_text(f"docs/wiki/{page}"))
    ukrainian = _heading_levels(_text(f"docs/wiki/uk/{page}"))

    assert ukrainian == english, f"docs/wiki/uk/{page}: section structure differs from the English page"


def test_every_english_wiki_page_has_a_ukrainian_twin_and_the_reverse():
    assert sorted(path.name for path in (ROOT / "docs" / "wiki" / "uk").glob("*.md")) == WIKI_PAGES


def test_the_version_is_written_in_one_place():
    """utils/constants.py owns the version; CHANGELOG.md records it. Nothing else repeats it."""
    number = APP_VERSION.replace("-dev", "")
    repeated = [document for document in CURRENT_DOCS if number in _text(document)]

    assert repeated == []


def test_the_entry_documents_stay_small():
    """What every session reads first has a budget, in tokens."""
    budgets = {"AGENTS.md": 2000, "README.md": 3500, "docs/INDEX.md": 1300, "docs/ARCHITECTURE.md": 2500, "docs/ENGINEERING.md": 2000}
    sizes = {path: docs_index.estimate_tokens(_text(path)) for path in budgets}

    assert {path: size for path, size in sizes.items() if size > budgets[path]} == {}


def test_the_index_has_no_document_waiting_to_be_merged():
    for path in docs_index.documents():
        fields, _body = docs_index.split_header(docs_index.read(path))
        assert fields.get("status") in ("current", "design", "archive"), path


def test_the_plugin_contract_page_is_what_the_spec_generates():
    from plugins.spec import render_markdown

    assert _text("docs/PLUGIN_CONTRACT.md") == render_markdown(), "run: python -m plugins.spec --write"
