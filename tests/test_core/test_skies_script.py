"""Skies of Arcadia script writer: code-relative labels, relocated branch operands, page round trip (synthetic data)."""
import os
import struct

import pytest

from core.containers import skies_script as S, skies_sct

GOTO, DISPATCH, MARK = 0x0B, 0x90, 0x09


def _u32(value, big):
    return struct.pack(">I" if big else "<I", value & 0xFFFFFFFF)


def _page(extra=b""):
    return rb"\h(" + b"\x81s" + b"Vyse" + b"\x81t" + b")Hi there." + extra + rb"\e"


def _script(big, page_text=None, inside_label=False):
    """A script with branch operands that cross the text page. ``inside_label`` adds a label inside the text.

    Code layout (code-relative): 09 init | 0b <op to loop> | page (padded) | 09 loop | 90 <op to init> 7fffffff | 09 tail
    """
    page = page_text if page_text is not None else _page()
    page = page + b"\x00" * (-len(page) % 4)
    count = 4 if inside_label else 3
    cs = S.HEADER_SIZE + S.LABEL_SIZE * count
    init_at = cs + 4                       # the 0b word; the 09 before it is at cs
    operand_at = init_at + 4               # the goto operand
    page_at = operand_at + 4               # the text page starts here
    loop_at = page_at + len(page) + 4      # the 09 before loop is the last word of the page block
    dispatch_at = loop_at                  # the 90 entry: word, operand, mask
    dispatch_operand = dispatch_at + 4
    tail_at = dispatch_at + 16             # the 09 before tail is the word after the mask
    code = bytearray()
    code += _u32(MARK, big)
    code += _u32(GOTO, big) + _u32(loop_at - (operand_at + 4), big)
    code += page
    code += _u32(MARK, big)
    code += _u32(DISPATCH, big) + _u32(init_at - (dispatch_operand + 4), big) + _u32(0x7FFFFFFF, big)
    code += _u32(MARK, big)
    labels = [(b"init", init_at - cs), (b"loop", loop_at - cs), (b"tail", tail_at - cs)]
    if inside_label:
        labels.append((b"mid", page_at + 12 + 6 - cs))   # 6 bytes into the text (the head is 12 bytes)
    header = b"\x00" * 8 + _u32(len(labels), big) + b"\x00" * 4
    table = b"".join(name.ljust(16, b"\x00") + _u32(target, big) for name, target in labels)
    return header + table + bytes(code)


def _operand_targets(body, big):
    return S.branch_sites(body, big)


@pytest.mark.parametrize("big", [True, False])
def test_unchanged_script_reassembles_exactly(big):
    body = _script(big)
    assert S.rebuild_pages(body) == body
    segs = S.text_segments(body, big)
    assert len(segs) == 1
    _, a, b = segs[0]
    same, delta = S.grow_regions(body, {(a, b): body[a:b]}, big)
    assert same == body and delta == 0


@pytest.mark.parametrize("big", [True, False])
def test_labels_are_code_relative_and_cover_the_page(big):
    body = _script(big)
    cs = S.code_start(body, big)
    labels = S.read_labels(body, big)
    assert [l.name for l in labels] == [b"init", b"loop", b"tail"]
    for label in labels:
        assert struct.unpack_from(">I" if big else "<I", body, cs + label.target - 4)[0] == MARK
    segs = S.text_segments(body, big)
    assert len(segs) == 1 and segs[0][0] == 0


@pytest.mark.parametrize("big", [True, False])
def test_growth_relocates_labels_and_crossing_branches(big):
    body = _script(big)
    cs = S.code_start(body, big)
    (_, a, b), = S.text_segments(body, big)
    new_text = body[a:b] + b" and a longer end of the line"
    new, delta = S.grow_regions(body, {(a, b): new_text}, big)
    assert delta > 0 and delta % 4 == 0
    labels_old = {l.name: l.target for l in S.read_labels(body, big)}
    labels_new = {l.name: l.target for l in S.read_labels(new, big)}
    assert labels_new[b"init"] == labels_old[b"init"]             # before the edit: unchanged
    assert labels_new[b"loop"] == labels_old[b"loop"] + delta      # after the edit: moved
    assert labels_new[b"tail"] == labels_old[b"tail"] + delta
    for name, target in labels_new.items():
        assert struct.unpack_from(">I" if big else "<I", new, cs + target - 4)[0] == MARK
    old_sites = _operand_targets(body, big)
    new_sites = _operand_targets(new, big)
    assert len(old_sites) == len(new_sites) == 2
    shifted = sorted((o + (delta if o >= b else 0), t + (delta if t >= b else 0)) for o, t in old_sites)
    assert sorted(new_sites) == shifted
    assert S.rebuild_pages(new) == new
    text = skies_sct.pages(new)[0].text
    assert text.startswith(new_text) and set(text[len(new_text):]) <= {0x7F}   # space padding to 4 bytes


@pytest.mark.parametrize("big", [True, False])
def test_label_inside_text_is_a_segment_cut_and_refused_for_growth(big):
    inside = _script(big, inside_label=True)
    segs = S.text_segments(inside, big)
    assert len(segs) == 2
    (_, a, mid), (_, mid2, b) = segs
    assert mid == mid2 and a < mid < b
    with pytest.raises(ValueError):
        S.grow_regions(inside, {(a, b): inside[a:b] + b"XXXX"}, big)


def test_no_branch_site_inside_the_text():
    big = True
    body = _script(big)
    (_, a, b), = S.text_segments(body, big)
    assert all(not (a <= operand < b) for operand, _ in S.branch_sites(body, big))


REAL_DIR = os.environ.get("PICORIPI_SKIES_SCRIPTS_DIR", "")


@pytest.mark.parametrize("big", [False])
def test_real_field_scripts_keep_labels_and_branches(big):
    """Every decoded field script of ``PICORIPI_SKIES_SCRIPTS_DIR`` (a folder of ``*.sct``): growth keeps the structure."""
    if not REAL_DIR or not os.path.isdir(REAL_DIR):
        pytest.skip("set PICORIPI_SKIES_SCRIPTS_DIR to a folder of decoded field scripts")
    checked = 0
    for name in sorted(os.listdir(REAL_DIR))[:40]:
        if not name.lower().endswith(".sct"):
            continue
        body = open(os.path.join(REAL_DIR, name), "rb").read()
        segs = S.text_segments(body, big)
        if not segs:
            continue
        _, a, b = segs[0]
        new, delta = S.grow_regions(body, {(a, b): body[a:b] + b"X" * 8}, big)
        cs = S.code_start(new, big)
        for old, moved in zip(S.read_labels(body, big), S.read_labels(new, big)):
            expected = old.target + (delta if cs + old.target >= b else 0)
            assert moved.target == expected, name
        assert len(S.branch_sites(new, big)) == len(S.branch_sites(body, big)), name
        checked += 1
    assert checked, "no field script with text"
