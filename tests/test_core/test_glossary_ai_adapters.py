"""Tests for AI adapters (core/glossary_build/ai_adapters.py).

The model call is faked, so these exercise prompt filling and, above all,
robust parsing of messy JSON replies into typed driver inputs.
"""
import json
from pathlib import Path

from core.glossary_build.ai_adapters import (
    make_extract,
    make_fold,
    make_propose,
    make_synthesize_stack,
    parse_json_array,
    parse_json_object,
)
from core.glossary_build.context_window import ContextWindow, Occurrence
from core.glossary_build.text_sweep import SweepChunk, SweepItem


PROMPTS = json.loads(
    Path("translation_prompts/glossary_pipeline_prompts.json").read_text(encoding="utf-8")
)


def _window(text):
    return ContextWindow(Occurrence(0, 0), 0, 0, 0, text)


def _chunk(text):
    return SweepChunk(items=(SweepItem(0, 0, text),), text=text)


class TestParsing:
    def test_plain_array(self):
        assert parse_json_array('[{"term": "A"}]') == [{"term": "A"}]

    def test_fenced_array(self):
        assert parse_json_array('```json\n[{"term": "A"}]\n```') == [{"term": "A"}]

    def test_array_with_surrounding_prose(self):
        text = 'Here you go:\n[{"term": "A"}]\nHope that helps!'
        assert parse_json_array(text) == [{"term": "A"}]

    def test_object_promoted_to_array(self):
        assert parse_json_array('{"term": "A"}') == [{"term": "A"}]

    def test_garbage_returns_empty(self):
        assert parse_json_array("not json at all") == []

    def test_object_fenced(self):
        assert parse_json_object('```json\n{"description": "x"}\n```') == {"description": "x"}

    def test_object_with_prose(self):
        assert parse_json_object('Sure: {"description": "x"} done') == {"description": "x"}


class TestExtract:
    def test_parses_terms(self):
        reply = '[{"term": "Ordon", "section": "Places", "fragment": "a village"}]'
        extract = make_extract(lambda m: reply, PROMPTS)
        terms = extract(_chunk("some text"))
        assert len(terms) == 1
        assert terms[0].term == "Ordon"
        assert terms[0].section == "Places"
        assert terms[0].fragment == "a village"

    def test_blank_terms_skipped(self):
        reply = '[{"term": "  "}, {"term": "Real"}]'
        extract = make_extract(lambda m: reply, PROMPTS)
        assert [t.term for t in extract(_chunk("x"))] == ["Real"]

    def test_chunk_text_reaches_the_call(self):
        captured = {}

        def call(messages):
            captured["user"] = messages[1]["content"]
            return "[]"

        extract = make_extract(call, PROMPTS)
        extract(_chunk("UNIQUE_MARKER_123"))
        assert "UNIQUE_MARKER_123" in captured["user"]

    def test_mask_applied(self):
        captured = {}

        def call(messages):
            captured["user"] = messages[1]["content"]
            return "[]"

        extract = make_extract(call, PROMPTS, mask=lambda t: t.replace("SECRET", "X"))
        extract(_chunk("has SECRET tag"))
        assert "SECRET" not in captured["user"]
        assert "X" in captured["user"]

    def test_fragment_falls_back_to_description_key(self):
        reply = '[{"term": "A", "description": "desc form"}]'
        extract = make_extract(lambda m: reply, PROMPTS)
        assert extract(_chunk("x"))[0].fragment == "desc form"


class TestSynthesizeAndFold:
    def test_synthesize_reads_description_object(self):
        synth = make_synthesize_stack(lambda m: '{"description": "the hero"}', PROMPTS, term="Link")
        assert synth([_window("Link runs")]) == "the hero"

    def test_synthesize_plain_text_fallback(self):
        synth = make_synthesize_stack(lambda m: "just prose, no json", PROMPTS, term="Link")
        assert synth([_window("x")]) == "just prose, no json"

    def test_windows_reach_call(self):
        captured = {}

        def call(messages):
            captured["user"] = messages[1]["content"]
            return '{"description": "x"}'

        synth = make_synthesize_stack(call, PROMPTS, term="Link")
        synth([_window("WINDOW_A"), _window("WINDOW_B")])
        assert "WINDOW_A" in captured["user"] and "WINDOW_B" in captured["user"]

    def test_fold_merges_fragments(self):
        captured = {}

        def call(messages):
            captured["user"] = messages[1]["content"]
            return '{"description": "merged"}'

        fold = make_fold(call, PROMPTS, term="Link")
        assert fold(["frag one", "frag two"]) == "merged"
        assert "frag one" in captured["user"] and "frag two" in captured["user"]


class TestPropose:
    def test_parses_variants(self):
        reply = '[{"translation": "Ордон", "rationale": "translit"}]'
        propose = make_propose(lambda m: reply, PROMPTS)
        variants = propose("Ordon", "a village")
        assert variants == [{"translation": "Ордон", "rationale": "translit"}]

    def test_bare_strings_coerced(self):
        propose = make_propose(lambda m: '["Ордон", "Ордона"]', PROMPTS)
        variants = propose("Ordon", "")
        assert variants[0]["translation"] == "Ордон"
        assert variants[0]["rationale"] == ""

    def test_term_and_description_reach_call(self):
        captured = {}

        def call(messages):
            captured["user"] = messages[1]["content"]
            return "[]"

        propose = make_propose(call, PROMPTS)
        propose("TERM_X", "DESC_Y")
        assert "TERM_X" in captured["user"] and "DESC_Y" in captured["user"]

    def test_target_lang_injected_into_system(self):
        captured = {}

        def call(messages):
            captured["system"] = messages[0]["content"]
            return "[]"

        propose = make_propose(call, PROMPTS, target_lang="Polish")
        propose("t", "d")
        assert "Polish" in captured["system"]
