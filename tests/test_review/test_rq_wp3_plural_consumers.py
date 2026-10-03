"""WP3 review queue (3.4): plural matching and untranslated-entry filtering, seen from every consumer.

The queue says plurals now find their glossary entry "in prompts, in the source highlighting, in the
occurrence list and in the 'term not translated' check", and that entries without a translation no longer
reach the prompt or the Story Inspector. Each consumer is driven here with a real ``GlossaryManager``.
"""
from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtGui import QTextDocument

from core.glossary_manager import STATUS_SEEDED, GlossaryManager
from core.story_inspector import build_timeline_inspection
from handlers.async_issue_scanner import AsyncIssueScanner
from handlers.translation.ai_prompt_composer import AIPromptComposer
from utils.syntax_highlighter import JsonTagHighlighter

SOURCE = "You owe me 20 Rupees, two foxes and three fairies at Lake Hylia."
PLURALS = [("Rupee", "Rupees"), ("Fairy", "fairies"), ("Lake Hylia", "Lake Hylia")]


def _manager():
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
    for original, translation, notes in (
        ("Rupee", "Рупія", "money"), ("Fairy", "Фея", "a fairy"), ("Hylia", "Гілія", "goddess"),
        ("Lake Hylia", "озеро Гілія", "a lake"), ("Fox", "", "an animal"),
    ):
        manager.add_entry(original, translation, notes, fold_variants=False)
    manager.update_entry("Fox", "", "an animal", status=STATUS_SEEDED)      # described, not translated
    return manager


def test_the_occurrence_list_finds_the_plural_spellings():
    index = _manager().build_occurrence_index([[SOURCE]])
    # Every entry that occurs, nested "Hylia" included: the "inside a longer term" rule is for prompts.
    assert {term for term, found in index.items() if found} == {"Rupee", "Fairy", "Lake Hylia", "Hylia", "Fox"}


def test_the_translation_prompt_lists_plural_hits_and_leaves_out_untranslated_and_nested_terms():
    handler = SimpleNamespace(
        mw=SimpleNamespace(current_game_rules=None, data_store=SimpleNamespace(block_names={}), target_language="Ukrainian"),
        _glossary_manager=_manager(), data_processor=None, ui_updater=None,
    )
    _system, user = AIPromptComposer(handler).compose_messages(
        "SYS", SOURCE, block_idx=None, string_idx=None, expected_lines=1, mode_description="m"
    )
    rows = [line for line in user.splitlines() if line.startswith("| ") and "---" not in line]
    assert rows == ["| Original | Translation | Notes |", "| Rupee | Рупія | money |", "| Fairy | Фея | a fairy |",
                    "| Lake Hylia | озеро Гілія | a lake |"]


def test_the_source_highlighting_marks_the_plural_spellings(qapp):
    doc = QTextDocument()
    doc.setPlainText(SOURCE)
    highlighter = JsonTagHighlighter(doc)
    highlighter.set_glossary_manager(_manager())
    highlighter._glossary_enabled = True
    highlighter._rebuild_glossary_cache()
    marked = {(SOURCE[start:start + length], match.entry.original)
              for start, length, match in highlighter._glossary_matches_cache[0]}
    assert {(text, original) for original, text in PLURALS} <= marked
    assert ("foxes", "Fox") in marked                                    # highlighting shows every entry


def test_the_editor_scan_and_its_translation_bridge_see_the_plurals():
    scanner = AsyncIssueScanner(0, 0, SOURCE, {}, 0, None, glossary_manager=_manager(), source_text=SOURCE,
                                editor_text="Ти винен мені 20 рупій, дві лисиці й три феї біля озера Гілія.")
    scanner.editor_text = SOURCE
    assert {(SOURCE[m["start"]:m["end"]], m["original"]) for m in scanner._run_glossary_matches()} >= {
        (text, original) for original, text in PLURALS
    }
    scanner.editor_text = "Ти винен мені 20 рупій, дві лисиці й три феї біля озера Гілія."
    bridged = {m["original"] for m in scanner._run_translation_matches()}
    # "Hylia" inside "Lake Hylia" is not bridged on its own; an untranslated "Fox" has nothing to bridge.
    assert {"Rupee", "Fairy", "Lake Hylia"} <= bridged and not {"Hylia", "Fox"} & bridged


class _Composer:
    def _get_block_label(self, b):
        return "zel_01"

    def _get_wing_name(self):
        return ""

    def _get_mempalace_client(self):
        return None

    def _find_speaker_in_script(self, b, s, text):
        return (None, None)

    def _translate_speaker(self, name):
        return name

    def _fetch_story_context(self, b, s, text):
        return ""


def test_the_story_inspector_shows_plural_hits_and_no_untranslated_entry():
    mw = SimpleNamespace(
        translation_handler=SimpleNamespace(prompt_composer=_Composer(), _glossary_manager=_manager()),
        current_game_rules=None,
        data_processor=SimpleNamespace(get_current_string_text=lambda b, s: (SOURCE, None)),
    )
    bundle = build_timeline_inspection(mw, 0, 0)
    assert [entry["original"] for entry in bundle["glossary_entries"]] == ["Rupee", "Fairy", "Lake Hylia"]
