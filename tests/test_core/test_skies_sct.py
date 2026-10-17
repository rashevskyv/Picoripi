"""Skies of Arcadia message scripts: page reader on synthetic bytes and, when present, a real GameCube script."""
import os

from core.containers import aklz, skies_sct


def test_pages_split_on_wait_and_end_with_speakers():
    body = (b"\x00\x09\x04"
            + rb"\h(" + b"\x81s" + b"Vyse" + b"\x81t" + b")Hey\x7fFina." + rb"\n" + b"How." + rb"\c"
            + b"\x00\x00\x09\x04\x1d"
            + rb"\h(" + b"\x81s" + b"Fina" + b"\x81t" + b")Thanks." + rb"\e"
            + b"\x00\x09")
    found = skies_sct.pages(body)
    assert [p.speaker for p in found] == [b"Vyse", b"Fina"]
    assert [p.text for p in found] == [b"Hey\x7fFina." + rb"\n" + b"How.", b"Thanks."]
    assert [p.terminator for p in found] == [rb"\c", rb"\e"]
    assert body[found[0].start:found[0].start + 3] == rb"\h("


def test_page_without_speaker_keeps_its_text():
    body = rb"\h(" + b"Plain line." + rb"\e"
    (page,) = skies_sct.pages(body)
    assert page.speaker is None and page.text == b"Plain line."


REAL = os.environ.get("PICORIPI_SKIES_LEGENDS_ME002A", "")


def test_real_legends_script_has_speaker_pages():
    if not REAL or not os.path.isfile(REAL):
        return
    body = aklz.decode(open(REAL, "rb").read())
    found = skies_sct.pages(body)
    assert len(found) > 50
    assert any(p.speaker == b"Vyse" for p in found)
