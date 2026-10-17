"""Skies of Arcadia Legends scripts (plugins/skies_of_arcadia): the byte codec, one string per text segment, and the
in-place and growing saves. Synthetic scripts built here; no game data."""
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
        target = offsets[page_index] + 3 + at
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
    for fixed in (True, False):
        assert scripts.write_strings(body, scripts.read_strings(body), fixed) == (body, [], set())


def test_fixed_edit_is_in_place_and_padded_to_the_same_length():
    body = _script([b"Hello there"])
    out, refused, missing = scripts.write_strings(body, ["Hi"], fixed=True)
    assert len(out) == len(body) and refused == [] and missing == set()
    assert scripts.read_strings(out) == ["Hi" + " " * 9]


def test_fixed_edit_refuses_a_longer_text_and_keeps_the_source():
    body = _script([b"Hi"])
    out, refused, _ = scripts.write_strings(body, ["Hello there"], fixed=True)
    assert out == body and refused == [0]


def test_growable_edit_writes_the_longer_text_back():
    body = _script([b"Hi", b"Bye"])
    out, refused, _ = scripts.write_strings(body, ["Hello there", "Bye"], fixed=False)
    assert refused == []
    # grow_regions pads the new text with spaces to a multiple of 4 (the code after it stays aligned)
    assert [s.rstrip(" ") for s in scripts.read_strings(out)] == ["Hello there", "Bye"]
    assert len(out) > len(body)


@pytest.mark.parametrize("rel, fixed", [
    ("field/me201a.sct", True),
    ("files\\field\\me201a.sct", True),
    ("field/me202a.sct", False),
    ("other/me201a.sct", False),
])
def test_fixed_size_scripts_match_by_path_end(rel, fixed):
    assert scripts.is_fixed(rel) is fixed


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


def test_rules_save_uses_the_source_version_and_the_fixed_rule():
    from plugins.skies_of_arcadia.rules import GameRules

    source = _script([b"Hello there"])
    rules = GameRules()
    data, _names = rules.load_data_from_json_obj(source)
    rules.prepare_save_context(_Context([b"stale translation copy", source], "field/me201a.sct"))
    data[0][0] = "Hi"
    out = rules.save_data_to_json_obj(data, {})
    assert len(out) == len(source) and out != source
