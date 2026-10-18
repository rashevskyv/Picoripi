"""Skies of Arcadia Legends scripts (plugins/skies_of_arcadia): the byte codec, one string per text segment, the
script-level budget and the saves. Synthetic scripts built here; no game data."""
import struct

import pytest

from plugins.skies_of_arcadia import scripts, text


def _script(pages, labels=()):
    """A big-endian script: header, label table (each label is ``(page index, offset in its text)``), then pages."""
    code_start = 16 + 20 * len(labels)
    bodies, offsets = [], []
    cursor = code_start
    for page in pages:
        block = b"\\h(" + page + b"\\c"
        block += b"\x00" * (-len(block) % 4)
        offsets.append(cursor)
        bodies.append(block)
        cursor += len(block)
    header = bytes(8) + struct.pack(">I", len(labels)) + bytes(4)
    table = b""
    for name, (page_index, at) in enumerate(labels):
        target = offsets[page_index] + 3 + at - code_start   # labels are code-relative
        table += f"L{name}".encode().ljust(16, b"\x00") + struct.pack(">I", target)
    return header + table + b"".join(bodies)


def test_codec_round_trips_every_byte_value():
    data = bytes(range(256)) + b"\x5c\x6e\x5c"
    assert text.encode(text.decode(data)) == (data, set())


def test_space_and_newline_are_the_game_bytes():
    assert text.decode(b"Hi\x7fthere\x5c\x6e") == "Hi there\\n"
    assert text.encode("Hi there\\n") == (b"Hi\x7fthere\x5c\x6e", set())


def test_character_without_a_byte_is_written_as_question_mark():
    assert text.encode("ї") == (b"?", {"ї"})


def test_one_string_per_segment_and_a_label_splits_a_page():
    body = _script([b"Hello", b"Bye"], labels=[(0, 2)])
    assert scripts.read_strings(body) == ["He", "llo", "Bye"]


def test_unchanged_strings_keep_the_body_exactly():
    body = _script([b"Hello", b"Bye"], labels=[(0, 2)])
    assert scripts.write_strings(body, scripts.read_strings(body)) == (body, set())


def test_budget_is_the_pooled_length_of_the_source_segments():
    body = _script([b"Hello there", b"Bye and more text"])
    state = scripts.budget_of(body, scripts.read_strings(body))
    assert (state.budget, state.used, state.free) == (28, 28, 0)
    assert state.changed == (False, False)


def test_trailing_spaces_are_padding_and_do_not_count():
    body = _script([b"Hi"])
    state = scripts.budget_of(body, ["Hi   "])
    assert state.changed == (False,) and state.free == 0
    assert scripts.write_strings(body, ["Hi   "]) == (body, set())


def test_a_changed_line_is_padded_to_the_source_length_mod_4():
    body = _script([b"Hi"])
    state = scripts.budget_of(body, ["Hello there"])   # 11 bytes; the source is 2 (2 - 11 = -9, mod 4 = 3)
    assert state.used == 14 and state.free == -12 and state.changed == (True,)
    assert scripts.budget_of(body, ["Hello"]).used == 6   # 5 bytes plus 1 space: (2 - 5) mod 4 = 1


def test_a_shorter_line_of_the_script_pays_for_a_longer_one():
    body = _script([b"Hi", b"Bye and more text"])
    out, missing = scripts.write_strings(body, ["Hello there", "Bye"])
    assert missing == set()
    # the script keeps its total length: the longer line is paid for by the shorter one
    assert len(out) == len(body)
    assert [s.rstrip(" ") for s in scripts.read_strings(out)] == ["Hello there", "Bye"]


def test_over_budget_text_is_written_as_typed_and_the_body_is_longer():
    body = _script([b"Hi", b"Bye"])
    out, missing = scripts.write_strings(body, ["Hello there", "Bye"])
    assert missing == set() and len(out) > len(body)
    assert [s.rstrip(" ") for s in scripts.read_strings(out)] == ["Hello there", "Bye"]
    state = scripts.budget_of(body, scripts.read_strings(out))
    assert state.free == -12 and state.changed == (True, False)


def test_reloaded_budget_matches_the_budget_of_the_typed_text():
    body = _script([b"Hi", b"Bye and more text"])
    out, _ = scripts.write_strings(body, ["Hello there", "Bye"])
    assert scripts.budget_of(body, scripts.read_strings(out)).free == 0


def test_string_count_mismatch_is_refused():
    body = _script([b"Hi", b"Bye"])
    with pytest.raises(ValueError):
        scripts.budget_of(body, ["Hi"])
    with pytest.raises(ValueError):
        scripts.write_strings(body, ["Hi"])


class _Context:
    def __init__(self, versions, relative_path):
        self._versions = versions
        self.relative_path = relative_path

    def existing_versions(self):
        return list(self._versions)


def test_rules_load_and_save_round_trip_unchanged():
    from plugins.skies_of_arcadia.rules import GameRules

    body = _script([b"Hello", b"Bye"], labels=[(0, 2)])
    rules = GameRules()
    data, _names = rules.load_data_from_json_obj(body)
    rules.prepare_save_context(_Context([body], "field/me202a.sct"))
    assert rules.save_data_to_json_obj(data, {}) == body


def test_rules_save_uses_the_source_version_and_keeps_the_length_within_budget():
    from plugins.skies_of_arcadia.rules import GameRules

    source = _script([b"Hello there"])
    rules = GameRules()
    data, _names = rules.load_data_from_json_obj(source)
    rules.prepare_save_context(_Context([b"stale translation copy", source], "field/me201a.sct"))
    data[0][0] = "Hi"
    out = rules.save_data_to_json_obj(data, {})
    assert len(out) == len(source) and out != source
