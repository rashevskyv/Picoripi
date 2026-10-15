"""The 3DS system plugin on a copy of the owner's 3ds-ua src/strings and src/layouts (env PICORIPI_ROMHACKING).

Every file: a save without a change gives back the same bytes, and one edit changes one line. The widths equal the
owner's own tools/validate.py pixel_width for every string (run in a separate interpreter, read-only). Writes only
under pytest's tmp_path.
"""
import difflib
import json
import shutil
import subprocess
import sys

import pytest

import romhacking_root
from core.formats import SaveContext, translation_parse
from plugins.system_3ds.rules import GameRules, line_widths, read_entries

REPO = ("_shared", "3ds_sysfont_ua", "repo_manual")
SRC = REPO + ("src",)

pytestmark = pytest.mark.skipif(romhacking_root.missing(*SRC, "strings") is not None,
                                reason=romhacking_root.missing(*SRC, "strings") or "")

# The owner's measurement of each text, in a separate interpreter so its modules never enter this process.
_OWNER_WIDTHS = (
    "import json, sys; sys.path.insert(0, sys.argv[1]); import validate; "
    "table = validate.load_homoglyphs(); widths = validate.load_widths(); "
    "texts = json.load(sys.stdin); "
    "print(json.dumps([validate.pixel_width(validate.apply_homoglyphs(t, table), widths) for t in texts]))"
)


@pytest.fixture(scope="module")
def project_files(tmp_path_factory):
    """(rules, [(path, raw bytes, translation texts)]) of a copy of src/strings and src/layouts, loaded as the host does."""
    copy = tmp_path_factory.mktemp("src")
    for part in ("strings", "layouts"):
        shutil.copytree(romhacking_root.path(*SRC, part), copy / part)
    rules = GameRules()
    paths = [p for p in sorted(copy.rglob("*.json")) if rules.includes_source_file(p.relative_to(copy).as_posix())]
    raws = [p.read_bytes() for p in paths]
    for raw in raws:
        rules.load_data_from_json_obj(raw)
    with translation_parse(rules):
        return rules, [(path, raw, rules.load_data_from_json_obj(raw)[0][0]) for path, raw in zip(paths, raws)]


def _save(rules, raw, texts):
    rules.prepare_save_context(SaveContext(block_indices=[0], existing_versions=lambda: iter([raw])))
    return rules.save_data_to_json_obj([texts])


def test_every_file_saves_back_byte_exact_and_one_edit_changes_one_line(project_files):
    rules, files = project_files
    assert len(files) >= 138
    assert sum(len(texts) for _, _, texts in files) >= 16000
    for path, raw, texts in files:
        assert _save(rules, raw, texts) == raw, path.name
        if not texts:
            continue
        edited = list(texts)
        edited[-1] += " тест"
        saved = _save(rules, raw, edited)
        changed = [line for line in difflib.ndiff(raw.decode("utf-8").splitlines(), saved.decode("utf-8").splitlines())
                   if line[:1] in "+-"]
        assert len(changed) == 2, path.name
        before, after = read_entries(raw.decode("utf-8")), read_entries(saved.decode("utf-8"))
        assert [entry.ua for entry in after] == edited, path.name
        assert [(e.key, e.en, e.ru) for e in after] == [(e.key, e.en, e.ru) for e in before], path.name
        json.loads(saved)  # still JSON


def test_the_widths_equal_the_owners_validate(project_files):
    rules, files = project_files
    texts = [text for _, _, block in files for text in block]
    done = subprocess.run([sys.executable, "-I", "-B", "-c", _OWNER_WIDTHS, str(romhacking_root.path(*REPO, "tools"))],
                          input=json.dumps(texts), capture_output=True, text=True, encoding="utf-8", timeout=600,
                          check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    widths = rules._widths_table()
    mine = [round(max(line_widths(text, widths))) for text in texts]
    assert mine == json.loads(done.stdout)
