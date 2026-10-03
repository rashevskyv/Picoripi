"""WP5 review queue: "Saving a Twilight Princess project goes through new plumbing (5.5)".

Open a zelda_bmg project with a message archive, edit one line, save through the host save path, reopen,
edit another line, save again (this save patches the translation archive written by the first). The written
``.bmg`` and the packed archive must be byte for byte what the pre-audit code wrote
(``tests/fixtures/review_queue/wp5/make_golden.py``).
"""
import hashlib
import json

import pytest

from . import _rq_wp5_helpers as h

GOLDEN = h.FIXTURES / "tp_save"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_synthetic_archive_save_matches_baseline_bytes(qapp, tmp_path):
    source = h.synthetic_arc_bytes()
    assert source == (GOLDEN / "synthetic_source.arc").read_bytes(), "the synthetic input drifted"

    result = h.tp_save_roundtrip(source, "bmgres.arc", "zel_rq.bmg", h.SYNTH_EDITS, tmp_path)

    for n, save in enumerate(result["saves"], 1):
        assert save["ok"] and not save["errors"]
        assert save["bmg"] == (GOLDEN / f"synthetic_save{n}.bmg").read_bytes(), f"save {n}: .bmg differs"
        assert save["arc"] == (GOLDEN / f"synthetic_save{n}.arc").read_bytes(), f"save {n}: archive differs"

    # Reopen: both edits are there, every other line is the source line.
    expected = list(result["source"])
    for idx, text in h.SYNTH_EDITS:
        expected[idx] = text
    assert result["reopened"] == expected
    assert result["reopened"] == json.loads((GOLDEN / "synthetic_reopened.json").read_text(encoding="utf-8"))


def test_synthetic_bmg_is_written_atomically(qapp, tmp_path, monkeypatch):
    """The ``.bmg`` goes to a temporary file in the same folder and is renamed over the target."""
    import os

    replaced = []
    real_replace = os.replace

    def spy(src, dst):
        replaced.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    h.tp_save_roundtrip(h.synthetic_arc_bytes(), "bmgres.arc", "zel_rq.bmg", h.SYNTH_EDITS[:1], tmp_path)
    targets = [dst for _src, dst in replaced]
    assert any(t.replace("\\", "/").endswith("bmgres.arc/zel_rq.bmg") for t in targets)
    assert any(t.replace("\\", "/").endswith("trans/res/Msgus/bmgres.arc") for t in targets)
    for src, dst in replaced:
        assert os.path.dirname(src) == os.path.dirname(dst)


@pytest.mark.skipif(not (h.TP_DUMP_MSG / h.REAL_ARC).exists(), reason="retail Twilight Princess dump not on this machine")
def test_real_message_archive_save_matches_baseline_hashes(qapp, tmp_path):
    golden_path = GOLDEN / "real_hashes.json"
    if not golden_path.exists():
        pytest.skip("real_hashes.json was generated without the dump")
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    source = (h.TP_DUMP_MSG / h.REAL_ARC).read_bytes()
    assert _sha(source) == golden["source_arc"], "the dump file differs from the one the golden was made from"

    result = h.tp_save_roundtrip(source, h.REAL_ARC, h.REAL_MEMBER, h.REAL_EDITS, tmp_path)

    for n, (save, want) in enumerate(zip(result["saves"], golden["saves"]), 1):
        assert save["ok"] and want["ok"]
        assert _sha(save["bmg"]) == want["bmg"], f"save {n}: .bmg differs from the baseline build"
        assert _sha(save["arc"]) == want["arc"], f"save {n}: packed archive differs from the baseline build"
    expected = list(result["source"])
    for idx, text in h.REAL_EDITS:
        expected[idx] = text
    assert result["reopened"] == expected
