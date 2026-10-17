"""Skies of Arcadia script writer: exact re-assembly, grown page relocation, label checks on synthetic data."""
import os
import struct

from core.containers import aklz, skies_script as S, skies_sct


def _u32(value, big):
    return struct.pack(">I" if big else "<I", value)


def _script(big):
    page = rb"\h(" + b"\x81s" + b"Vyse" + b"\x81t" + b")Hi there." + rb"\e"
    text = page + b"\x00" * (-len(page) % 4)
    code_start = 16 + 20 * 2
    code = text + _u32(code_start + len(text), big)   # an aligned pointer to the loop label after the page
    labels = [(b"init", code_start), (b"loop", code_start + len(text))]
    header = b"\x00" * 8 + _u32(2, big) + b"\x00" * 4
    table = b"".join(name.ljust(16, b"\x00") + _u32(target, big) for name, target in labels)
    return header + table + code


def test_unchanged_script_reassembles_exactly():
    for big in (True, False):
        body = _script(big)
        assert S.rebuild_pages(body) == body


def test_grown_page_moves_later_words_and_labels():
    for big in (True, False):
        body = _script(big)
        new_body, delta = S.grow_page(body, 0, b"A much longer line of Ukrainian text here.", big)
        assert delta > 0 and delta % 4 == 0
        assert skies_sct.pages(new_body)[0].text == b"A much longer line of Ukrainian text here."
        labels0 = S.read_labels(body, big)
        labels1 = S.read_labels(new_body, big)
        assert [l.name for l in labels0] == [l.name for l in labels1]
        assert labels1[1].target == labels0[1].target + delta
        old_pointer = struct.unpack_from(">I" if big else "<I", body, len(body) - 4)[0]
        new_pointer = struct.unpack_from(">I" if big else "<I", new_body, len(new_body) - 4)[0]
        assert new_pointer == old_pointer + delta


REAL = os.environ.get("PICORIPI_SKIES_LEGENDS_ME002A", "")


def test_real_legends_script_grows_one_page_only():
    if not REAL or not os.path.isfile(REAL):
        return
    body = aklz.decode(open(REAL, "rb").read())
    before = skies_sct.pages(body)
    new_body, _ = S.grow_page(body, 0, before[0].text + b"\n" + b"UA TEST", True)
    after = skies_sct.pages(new_body)
    assert len(after) == len(before)
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if (a.speaker, a.text) != (b.speaker, b.text)]
    assert changed == [0]
    assert aklz.decode(aklz.encode(new_body)) == new_body
