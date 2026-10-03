"""WP3 review queue (3.6): a glossary with deletion records, opened by the pre-audit build and by this one.

Golden: ``tests/fixtures/review_queue/wp3/old_build_save.json`` (see ``make_golden.py`` there). The queue says
an older build "would show them as untranslated terms"; the golden shows otherwise: it hides them, and on
its next save it drops both the deletion record and every ``id`` -- so the next sync brings the deleted term
back. This build keeps both.
"""
import json
from pathlib import Path

from core.glossary_manager import GlossaryManager

GOLDEN = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures/review_queue/wp3/old_build_save.json").read_text(encoding="utf-8")
)


def test_the_old_build_drops_deletion_records_and_ids_and_this_one_keeps_them(tmp_path):
    old = GOLDEN["saved_after_one_addition"]
    assert GOLDEN["entries_shown"] == ["Rupee"]                         # old: hidden, not shown as untranslated
    assert not any(item.get("deleted_at") or item.get("id") for item in old)   # old: both lost on save

    raw = json.dumps(GOLDEN["input"], ensure_ascii=False, indent=2)
    path = tmp_path / "glossary.json"
    path.write_text(raw, encoding="utf-8")
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=path, raw_text=raw)
    assert [entry.original for entry in manager.get_entries()] == GOLDEN["entries_shown"]
    manager.add_entry("Goron", "Ґорон", "")

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [item["original"] for item in saved] == ["Rupee", "Goron", "Zora"]
    assert saved[0]["id"] == "a" * 32 and len(saved[1]["id"]) == 32
    assert saved[2] == GOLDEN["input"][1]
    for new, before in zip(saved[:2], old):                             # the rest is what the old build wrote
        assert {k: v for k, v in new.items() if k not in ("id", "updated_at")} == before
