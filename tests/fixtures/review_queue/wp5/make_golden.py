"""Generate the WP5 review-queue golden files by running the PRE-AUDIT code (baseline worktree at 691699c0).

Rerun (Git Bash), from the baseline worktree so its ``core``/``plugins`` are imported:

    cd /d/git/dev/Picoripi-baseline && PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
        TMPDIR=/d/git/dev/Picoripi/.tmp_test_run/wp5 TEMP=/d/git/dev/Picoripi/.tmp_test_run/wp5 \
        ../Picoripi/venv/Scripts/python.exe ../Picoripi/tests/fixtures/review_queue/wp5/make_golden.py [section ...] < /dev/null

Sections: tp_save, preview, analyzers, settings (default: all). The harness is
``tests/test_review/_rq_wp5_helpers.py``; the tests in ``tests/test_review/test_rq_wp5_*.py`` run the same
harness on the current code and compare. Real game data from the retail dump is never stored: only hashes.
"""
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HELPERS = HERE.parents[2] / "test_review" / "_rq_wp5_helpers.py"


def _load_helpers():
    spec = importlib.util.spec_from_file_location("_rq_wp5_helpers", HELPERS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tp_save(h):
    out = HERE / "tp_save"
    out.mkdir(exist_ok=True)
    result = h.tp_save_roundtrip(h.synthetic_arc_bytes(), "bmgres.arc", "zel_rq.bmg", h.SYNTH_EDITS,
                                 tempfile.mkdtemp())
    (out / "synthetic_source.arc").write_bytes(h.synthetic_arc_bytes())
    for n, save in enumerate(result["saves"], 1):
        assert save["ok"], save["errors"]
        (out / f"synthetic_save{n}.bmg").write_bytes(save["bmg"])
        (out / f"synthetic_save{n}.arc").write_bytes(save["arc"])
    (out / "synthetic_reopened.json").write_text(json.dumps(result["reopened"], indent=1), encoding="utf-8")

    real = h.TP_DUMP_MSG / h.REAL_ARC
    if real.exists():
        result = h.tp_save_roundtrip(real.read_bytes(), h.REAL_ARC, h.REAL_MEMBER, h.REAL_EDITS, tempfile.mkdtemp())
        hashes = {"source_arc": _sha(real.read_bytes()),
                  "saves": [{"bmg": _sha(s["bmg"]), "arc": _sha(s["arc"]), "ok": s["ok"]} for s in result["saves"]]}
        (out / "real_hashes.json").write_text(json.dumps(hashes, indent=1), encoding="utf-8")


def preview(h):
    out = HERE / "preview"
    out.mkdir(exist_ok=True)
    rendered = h.render_tp_previews(None)
    meta = {}
    for name, value in rendered.items():
        if "image" in value:
            (out / f"{name}.png").write_bytes(h.png_bytes(value["image"]))
            meta[name] = {"label": value["label"], "bar_visible": value["bar_visible"]}
        else:
            meta[name] = value
    (out / "synthetic.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")

    if (h.TP_DUMP_ROOT / "res" / "Layout" / "msgres01.arc").exists():
        rendered = h.render_tp_previews(h.TP_DUMP_ROOT)
        digests = {name: ({"pixels": h.pixel_digest(v["image"]), "label": v["label"]} if "image" in v else v)
                   for name, v in rendered.items()}
        (out / "dump_digests.json").write_text(json.dumps(digests, indent=1), encoding="utf-8")


def analyzers(h):
    out = HERE / "analyzers"
    out.mkdir(exist_ok=True)
    for plugin in h.PLUGINS:
        texts, pairs = h.corpus_for(plugin)
        result = h.analyze_corpus(plugin, texts, pairs)
        (out / f"{plugin}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    if (h.TP_DUMP_MSG / h.REAL_ARC).exists():
        result = h.analyze_corpus("zelda_bmg", h.tp_dump_texts(), [])
        digest = h.corpus_digest(result)
        (out / "tp_dump_digest.json").write_text(json.dumps({"digest": digest}, indent=1), encoding="utf-8")


def pokemon_archive(h):
    out = HERE / "pokemon_archive"
    out.mkdir(exist_ok=True)
    result = {
        "two_files": h.pokemon_roundtrip(tempfile.mkdtemp()),
        "single_block": h.pokemon_roundtrip(tempfile.mkdtemp(), files=h.POKEMON_SINGLE),
        "archive_members": {f"{plugin}:{member}": h.archive_member_load(plugin, member, payload, tempfile.mkdtemp())
                            for plugin, member, payload in h.ARCHIVE_MEMBER_CASES},
    }
    (out / "golden.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")


def settings(h):
    out = HERE / "settings"
    out.mkdir(exist_ok=True)
    result = {plugin: h.effective_plugin_settings(plugin) for plugin in h.PLUGINS}
    (out / "effective.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, sort_keys=True),
                                        encoding="utf-8")


SECTIONS = {"tp_save": tp_save, "preview": preview, "analyzers": analyzers, "pokemon_archive": pokemon_archive,
            "settings": settings}


def main(argv):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])  # noqa: F841 - fonts and pixmaps need it
    h = _load_helpers()
    for name in argv or list(SECTIONS):
        SECTIONS[name](h)
        print("written:", name)


if __name__ == "__main__":
    main(sys.argv[1:])
