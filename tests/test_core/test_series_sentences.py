"""Series sentence reuse (D45): which sentences of other games are candidates, and how each one is classified."""
from core.translation.series_memory import source_hash
from test_core.test_series_memory import enable_sentences, window  # noqa: F401  (window fixture)

SENTENCE = "Yes we go now"


def _series_rows(manager, source, rows):
    manager.series_memory = {source_hash(source): rows}


def _english(manager, name, addressee=""):
    """This game's context for (7, 10): the English speaker name and an addressee."""
    manager.context_for = lambda block_idx, string_idx, source: {
        "speaker": f"UA {name}", "speaker_en": name, "addressee": addressee, "fold": "f",
    }


def test_the_setting_is_off_by_default_so_no_candidate_is_offered(window):  # noqa: F811
    manager = window.saved_translations_manager
    _series_rows(manager, SENTENCE, [{"source": SENTENCE, "translation": "Так, ходімо", "project": "TP HD",
                                      "speaker_en": "Ann", "addressee": ""}])
    assert manager.series_candidates(7, 10, SENTENCE) == []


def test_a_series_term_is_never_a_candidate_however_the_setting_is(window):  # noqa: F811
    manager = window.saved_translations_manager
    enable_sentences(window)
    manager.configure_series_reuse(True, 2, True)  # "Yes" has one word: a term
    assert manager.series_candidates(7, 10, "Yes") == []


def test_a_sentence_with_the_same_english_speaker_is_safe(window):  # noqa: F811
    manager = window.saved_translations_manager
    enable_sentences(window)
    manager.configure_series_reuse(True, 2, True)
    _series_rows(manager, SENTENCE, [{"source": SENTENCE, "translation": "Так, ходімо", "project": "TP HD",
                                      "speaker_en": "Ann", "addressee": ""}])
    _english(manager, "Ann")

    (candidate,) = manager.series_candidates(7, 10, SENTENCE)

    assert candidate["translation"] == "Так, ходімо"
    assert candidate["project"] == "TP HD"
    assert candidate["safe"] is True and candidate["reason"] == ""
    assert candidate["own_speaker_en"] == "Ann" and candidate["speaker_en"] == "Ann"


def test_each_doubtful_reason_is_written_and_makes_the_candidate_unsafe(window):  # noqa: F811
    manager = window.saved_translations_manager
    enable_sentences(window)
    manager.configure_series_reuse(True, 2, True)
    _series_rows(manager, SENTENCE, [
        {"source": SENTENCE, "translation": "А", "project": "WW", "speaker_en": "Bob", "addressee": ""},
        {"source": SENTENCE, "translation": "Б", "project": "WW", "addressee": ""},
        {"source": SENTENCE, "translation": "В", "project": "WW", "speaker_en": "Ann", "addressee": "Tom"},
        {"source": SENTENCE, "translation": "Так [ko]", "project": "WW", "speaker_en": "Ann", "addressee": ""},
    ])
    _english(manager, "Ann")

    by_translation = {c["translation"]: c["reason"] for c in manager.series_candidates(7, 10, SENTENCE)}
    assert by_translation["А"] == "The speaker names differ."
    assert by_translation["Б"] == "A speaker name is missing in one game."
    assert by_translation["В"] == "The addressee differs."
    assert by_translation["Так [ko]"] == "The tags do not match this text."


def test_a_safe_candidate_comes_before_a_doubtful_one(window):  # noqa: F811
    manager = window.saved_translations_manager
    enable_sentences(window)
    manager.configure_series_reuse(True, 2, True)
    _series_rows(manager, SENTENCE, [
        {"source": SENTENCE, "translation": "Doubtful", "project": "WW", "speaker_en": "Bob", "addressee": ""},
        {"source": SENTENCE, "translation": "Safe", "project": "TP", "speaker_en": "Ann", "addressee": ""},
    ])
    _english(manager, "Ann")

    assert [c["translation"] for c in manager.series_candidates(7, 10, SENTENCE)] == ["Safe", "Doubtful"]


def test_a_memory_row_saved_before_english_names_is_doubtful_not_excluded(window):  # noqa: F811
    manager = window.saved_translations_manager
    enable_sentences(window)
    manager.configure_series_reuse(True, 2, True)
    _series_rows(manager, SENTENCE, [{"source": SENTENCE, "translation": "Старе", "project": "TP", "addressee": ""}])
    _english(manager, "Ann")

    (candidate,) = manager.series_candidates(7, 10, SENTENCE)

    assert candidate["safe"] is False and candidate["translation"] == "Старе"
