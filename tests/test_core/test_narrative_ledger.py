from core.translation.narrative_ledger import NarrativeLedger


def test_narrative_ledger_init_and_clear():
    ledger = NarrativeLedger()
    assert ledger.format_for_prompt() == ""

    ledger.record_term("Master Sword", "Вищий Меч", "Items")
    ledger.record_speaker_voice("Zelda", "звертання на 'Ви'")
    ledger.record_story_event("Link awakened.")

    formatted = ledger.format_for_prompt()
    assert "Master Sword -> Вищий Меч [Items]" in formatted
    assert "Zelda: звертання на 'Ви'" in formatted
    assert "Link awakened." in formatted

    ledger.clear()
    assert ledger.format_for_prompt() == ""


def test_narrative_ledger_max_events():
    ledger = NarrativeLedger(max_recent_events=3)
    for i in range(5):
        ledger.record_story_event(f"Event {i}")
    assert len(ledger.recent_events) == 3
    assert ledger.recent_events == ["Event 2", "Event 3", "Event 4"]


def test_narrative_ledger_serialization():
    ledger = NarrativeLedger()
    ledger.record_term("Deku Tree", "Дерево Деку")
    ledger.record_speaker_voice("Navi", "звертання на 'ти'")
    ledger.record_story_event("Spoke with the tree.")

    d = ledger.to_dict()
    restored = NarrativeLedger.from_dict(d)

    assert restored.established_terms == ledger.established_terms
    assert restored.speaker_voices == ledger.speaker_voices
    assert restored.recent_events == ledger.recent_events
