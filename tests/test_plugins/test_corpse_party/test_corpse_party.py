"""Corpse Party (3DS): message slots, quoted-string lists and the real files (skipped when missing)."""
import romhacking_root

import pytest

from plugins.corpse_party import msg, txtlist


def _slot(text: bytes, tail: bytes) -> bytes:
    return text.ljust(msg.TEXT, b"\0") + tail


TAIL = lambda n: bytes([n, 0, 1, 0, 0, 0, 0, 0])  # noqa: E731


def _file():
    parts = [
        _slot(b"View the chapter?\0Yes\0No", b"\0" * 8),            # no tail: goes on
        _slot(b"", b"\xff" * 8),                                    # tail of 0xFF: ends the first message
        _slot(b"It was raining\0one...", TAIL(2)),
        _slot(b"x" * 119 + b"\0", b"\0" * 8),                       # a long message over two slots...
        _slot(b"", TAIL(3)),
    ]
    return b"".join(parts)


def test_messages_follow_the_tails():
    m = msg.Msg(_file())
    assert [x.slots for x in m.messages] == [2, 1, 2]
    assert m.texts()[0] == "View the chapter?\nYes\nNo"
    assert m.texts()[1] == "It was raining\none..."


def test_unedited_is_exact_and_edit_keeps_what_fits():
    raw = _file()
    m = msg.Msg(raw)
    assert m.rebuild(m.texts()) == raw
    texts = m.texts()
    texts[1] = "UA TEST\nok"
    out = msg.Msg(m.rebuild(texts))
    assert out.texts()[1] == "UA TEST\nok" and len(m.rebuild(texts)) == len(raw)
    texts[1] = "z" * 130
    with pytest.raises(msg.MsgError):
        m.rebuild(texts)


def test_bytes_outside_ascii_are_tags():
    assert msg.decode_line(b"\xffHi") == "{xff}Hi"
    assert msg.encode_line("{xff}Hi") == b"\xffHi"


def test_quoted_lists_round_trip_and_ignore_comments():
    raw = b'1,0,"ED No.1","Chapter Clear","a/nb"\r\n  2,"Name", // "not a string"\r\n'
    assert txtlist.texts(raw) == ["ED No.1", "Chapter Clear", "a\nb", "Name"]
    assert txtlist.rebuild(raw, txtlist.texts(raw)) == raw
    out = txtlist.rebuild(raw, ["x", "y", "z\nw", "n"])
    assert txtlist.texts(out) == ["x", "y", "z\nw", "n"]


ROOT = romhacking_root.under('Corpse Party\\3DS\\source\\romfs\\data')


@pytest.mark.skipif(not ROOT.is_dir(), reason="the game is not unpacked")
def test_real_files_round_trip():
    files = sorted(ROOT.glob("*/*_scriptlist.MSG"))
    assert len(files) == 20
    total = 0
    for path in files:
        raw = path.read_bytes()
        m = msg.Msg(raw)
        total += len(m.messages)
        assert m.rebuild(m.texts()) == raw
    assert total > 8000
    for name in ("itemdatalist", "deaddatalist", "endinglist", "playersettinglist"):
        raw = (ROOT / f"{name}.txt").read_bytes()
        assert txtlist.rebuild(raw, txtlist.texts(raw)) == raw
