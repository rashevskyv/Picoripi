"""Golden output of the pre-audit build (commit 691699c0) for a glossary file that holds a deletion record.

What an older Picoripi does with a WP3 glossary: it loads the file, the user adds one term, it saves.
The result is stored in ``old_build_save.json`` next to this script and read by
``tests/test_review/test_rq_wp3_old_build.py``.

Rerun from the baseline worktree (Git Bash):
    cd /d/git/dev/Picoripi-baseline && PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
        ../Picoripi/venv/Scripts/python.exe ../Picoripi/tests/fixtures/review_queue/wp3/make_golden.py < /dev/null
"""
import json
import tempfile
from pathlib import Path

from core.glossary_manager import GlossaryManager

HERE = Path(__file__).resolve().parent
INPUT = [
    {"original": "Rupee", "translation": "Рупія", "notes": "", "section": "Items", "profiled": False, "id": "a" * 32},
    {"original": "Zora", "id": "b" * 32, "deleted_at": "2026-10-02T10:00:00+00:00"},
]


def main() -> None:
    raw = json.dumps(INPUT, ensure_ascii=False, indent=2)
    path = Path(tempfile.mkdtemp()) / "glossary.json"
    path.write_text(raw, encoding="utf-8")
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=path, raw_text=raw)
    shown = [entry.original for entry in manager.get_entries()]
    manager.add_entry("Goron", "Ґорон", "")
    saved = json.loads(path.read_text(encoding="utf-8"))
    for item in saved:
        item.pop("updated_at", None)                     # a clock value, not behaviour
    out = {"input": INPUT, "entries_shown": shown, "saved_after_one_addition": saved}
    (HERE / "old_build_save.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
