"""extract_json: every way a model wraps, breaks or cuts off its JSON."""
import json

import pytest

from utils.json_extract import ParseError, extract_json, extract_json_text


@pytest.mark.parametrize("text, expect, value", [
    # Unfenced arrays used to lose their brackets to a first-'{'/last-'}' slice.
    ('[{"a":1},{"b":2}]', "any", [{"a": 1}, {"b": 2}]),
    ('[{"a":1}]', "array", [{"a": 1}]),
    ('```json\n{"a": 1}\n```', "object", {"a": 1}),
    ('Sure, here it is:\n{"a": 1}\nHope that helps!', "object", {"a": 1}),
    # Trailing prose with braces of its own.
    ('{"a": 1}\nNote: {placeholders} were kept.', "object", {"a": 1}),
    # Brackets in the prose before the payload.
    ('See [1] and {this: {"a": 1}', "object", {"a": 1}),
    # A code fence inside a string must not end the block.
    ('```json\n{"a": "use ``` for code"}\n```', "object", {"a": "use ``` for code"}),
    # BOM and zero-width characters around and between tokens.
    ('﻿{"a":​ 1}', "object", {"a": 1}),
    # Raw newline inside a string.
    ('{"a": "line one\nline two"}', "object", {"a": "line one\nline two"}),
    # An object is skipped, not mined for its inner array, when an array is wanted.
    ('{"meta": [1]} then [{"term": "A"}]', "array", [{"term": "A"}]),
])
def test_reads_the_payload(text, expect, value):
    assert extract_json(text, expect)[0] == value


@pytest.mark.parametrize("text, value", [
    ('{"a": 1, "b": [1, 2,], }', {"a": 1, "b": [1, 2]}),
    ('{“a”: “x”}', {"a": "x"}),
])
def test_repairs_are_reported(text, value):
    assert extract_json(text) == (value, ["repaired"])


def test_a_comma_inside_a_string_is_not_a_trailing_comma():
    text = '{"a": "привіт, }", }'
    assert extract_json(text)[0] == {"a": "привіт, }"}


def test_curly_quotes_inside_a_string_are_kept():
    assert extract_json('{"a": "вона сказала “так”",}')[0] == {"a": "вона сказала “так”"}


@pytest.mark.parametrize("text, value", [
    ('[{"term": "A"}, {"term": "B"}, {"term": "C', [{"term": "A"}, {"term": "B"}, {"term": "C"}]),
    ('[{"term": "A"}, {"term": "B", "sec', [{"term": "A"}, {"term": "B"}]),
    ('{"translated_strings": [{"id": 1, "translation": "x"}, {"id": 2,', {"translated_strings": [{"id": 1, "translation": "x"}, {"id": 2}]}),
])
def test_truncated_output_is_closed_and_flagged(text, value):
    assert extract_json(text) == (value, ["truncated"])


@pytest.mark.parametrize("text", ["", "   ", "﻿", "not json at all", "{broken", "42", '"just a string"'])
def test_nothing_to_read_raises_instead_of_returning_empty(text):
    with pytest.raises(ParseError) as info:
        extract_json(text)
    assert info.value.raw_text == text
    assert isinstance(info.value, json.JSONDecodeError)
    assert "line 1 column 1" not in str(info.value)


def test_wrong_type_raises():
    with pytest.raises(ParseError, match="JSON array"):
        extract_json('{"a": 1}', "array")
    with pytest.raises(ParseError, match="JSON object"):
        extract_json('[1, 2]', "object")


class TestExtractJsonText:
    def test_valid_source_text_is_kept_verbatim(self):
        assert extract_json_text('Some text { "a": 1 } more text') == '{ "a": 1 }'
        assert extract_json_text('```json\n{"a":1}\n```') == '{"a":1}'

    def test_repaired_text_is_reserialised_and_loadable(self):
        cleaned = extract_json_text('{"a": 1, "b": "привіт", }')
        assert json.loads(cleaned) == {"a": 1, "b": "привіт"}
        assert "привіт" in cleaned

    def test_truncated_is_refused(self):
        with pytest.raises(ParseError, match="cut off"):
            extract_json_text('{"translated_strings": [{"id": 1}, {"id": 2')
