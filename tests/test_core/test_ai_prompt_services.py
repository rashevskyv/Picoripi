import pytest
from unittest.mock import MagicMock
from core.translation.placeholder_manager import AIPlaceholderManager
from core.translation.glossary_formatter import GlossaryPromptFormatter
from core.glossary_manager import GlossaryEntry

def test_placeholder_manager():
    pm = AIPlaceholderManager()

    # 1. prepare_text_for_translation
    res, pmap = pm.prepare_text_for_translation("hello", [])
    assert res == "hello"
    assert pmap == {}

    # 2. restore_placeholders
    tag_mappings = {"{L-Stick}": "{escape:3:0009}"}
    translated = "натисни {L-Stick}"
    res2 = pm.restore_placeholders(translated, None, default_tag_mappings=tag_mappings)
    assert res2 == "натисни {escape:3:0009}"

def test_glossary_formatter():
    gf = GlossaryPromptFormatter()

    # 1. glossary_entries_to_text
    entries = [GlossaryEntry("sword", "меч", "notes")]
    res = gf.glossary_entries_to_text(entries)
    assert "| sword | меч | notes |" in res

    # 2. append_speaker_glossary_entries
    relevant = []
    gm = MagicMock()
    entry = GlossaryEntry("Hero", "Герой", "")
    gm.get_entry.return_value = entry
    gf.append_speaker_glossary_entries(relevant, ["Hero"], gm)
    assert len(relevant) == 1
    assert relevant[0] == entry
