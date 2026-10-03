"""WP3 review queue: one full glossary build on a copy of the shipped glossary, against a scripted local AI.

The real ``GlossaryBuildWorker`` runs on its own thread with a real ``OpenAIProvider`` that talks HTTP to a
fake OpenAI-compatible server on 127.0.0.1. The route is the user-facing one: Automatic build (seed, sweep,
describe, translate) with "Reconcile related terms afterwards", then "Force Retranslate". Before the build a
term is added by hand through the real edit path. ``translation_prompts/glossary.json`` is only read.
"""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QDialog

from core.glossary.models import legacy_entry_id
from core.glossary_build.pipeline_coordinator import FAMILY_BATCH, MODE_AUTO, MODE_TRANSLATE, STORE_BATCH
from core.glossary_manager import STATUS_CONFIRMED, STATUS_TRANSLATED
from core.translation.providers import OpenAIProvider
from handlers.translation.glossary.edit_mixin import EditMixin
from handlers.translation.glossary_pipeline_worker import GlossaryBuildWorker
from ._rq_wp3_helpers import (
    REAL_GLOSSARY,
    FakeOpenAI,
    field,
    glossary_copy,
    kind_of,
    load,
    reconcile_terms,
)

DATASET = [
    [
        "Link's sword glows in the dark.",
        "Hylia blesses all who pray at Lake Hylia.",
        "Take one of the Hylian Shields from the shop.",
        "Bathe in the Hylia Spring to heal.",
        "He drew the Hylian Bow.",
        "Zora Armors keep you warm under water.",
    ],
    [
        "The Twilit Dragon roars.",
        "Sky Lanterns float in the night.",
        "Light a Sky Lantern for luck.",
    ],
]

# What the sweep "finds": four spellings of entries the glossary already has (possessive, plural, article)
# and four new terms, one of them in two spellings.
SWEEP = [
    ("Link's", "Characters"),
    ("Hylian Shields", "Equipment"),
    ("Zora Armors", "Equipment"),
    ("The Twilit Dragon", "Characters"),
    ("Hylia", "Characters"),
    ("Hylia Spring", "Locations"),
    ("Hylian Bow", "Equipment"),
    ("Sky Lanterns", "Items"),
    ("Sky Lantern", "Items"),
]
FOLDED_INTO = {"Link's": "Link", "Hylian Shields": "Hylian shield", "Zora Armors": "Zora armor",
               "The Twilit Dragon": "Twilit Dragon"}
NEW_TERMS = {"Hylia", "Hylia Spring", "Hylian Bow", "Sky Lanterns"}
TRANSLATIONS = {"Hylia": "Гілія", "Hylia Spring": "Джерело Гілії", "Hylian Bow": "Гілійський лук",
                "Sky Lanterns": "Небесні ліхтарі"}
HAND_ADDED = ("Ordon Springs", "Ордонські джерела")        # a plural of the existing "Ordon Spring"

NO_CHANGE = {"merge": [], "canonical_translation_by_term": {}, "keep_separate": [], "reason": ""}
RECONCILE = {
    "The Postman": {"merge": [["The Postman", "POSTMAN"]], "canonical_translation_by_term": {},
                    "keep_separate": [], "reason": "одна особа"},
    "Lake Hylia": {"merge": [], "canonical_translation_by_term": {"Lake Hylia": "Озеро Гілія"},
                   "keep_separate": [], "reason": "корінь Гілі-"},
}


class Script:
    """The scripted model. The first request for "Hylian Bow" fails with HTTP 500."""

    def __init__(self, forced: bool = False) -> None:
        self.forced = forced
        self.failed_once = False

    def __call__(self, messages):
        kind, user = kind_of(messages), messages[-1]["content"]
        if kind == "extract":
            return json.dumps([{"term": t, "section": s, "fragment": f"{t} in the text"} for t, s in SWEEP])
        if kind in ("describe", "fold"):
            return json.dumps({"description": f"Опис: {field(user, 'Term')}"})
        if kind == "translate":
            term = field(user, "Term")
            if term == "Hylian Bow" and not self.failed_once:
                self.failed_once = True
                return 500
            text = f"Новий {term}" if self.forced else TRANSLATIONS.get(term, f"Переклад {term}")
            return json.dumps([{"translation": text, "rationale": ""}])
        if kind == "reconcile":
            terms = reconcile_terms(user)
            return json.dumps(next((reply for key, reply in RECONCILE.items() if key in terms), NO_CHANGE))
        return json.dumps({"name": "", "confidence": "low", "evidence": ""})


class _Dialog:
    def exec(self):
        return QDialog.DialogCode.Accepted

    def get_values(self):
        return HAND_ADDED[1], "added by hand"


class _GlossaryEditor(EditMixin):
    """The glossary handler's add/edit path with its window parts replaced by plain stand-ins."""

    def __init__(self, manager):
        self.glossary_manager = manager
        self.mw = SimpleNamespace(data_store=SimpleNamespace(data=DATASET))
        self.main_handler = SimpleNamespace(_cached_glossary="")
        self._occurrence_updater = SimpleNamespace(show_translation_update_dialog=lambda **kwargs: None)

    def _create_edit_dialog(self, *args, **kwargs):
        return _Dialog()

    def _update_glossary_highlighting(self):
        pass


def _run(worker):
    """Start the worker thread and wait for build_finished; returns (ok, summary, progress)."""
    loop = QEventLoop()
    finished, progress = [], []
    worker.progress.connect(lambda stage, done, total: progress.append((stage, done, total)))
    worker.build_finished.connect(lambda ok, summary: (finished.append((ok, summary)), loop.quit()))
    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(loop.quit)
    guard.start(120_000)
    worker.start()
    loop.exec()
    guard.stop()
    assert worker.wait(10_000)
    assert finished, "the build did not finish within two minutes"
    return finished[0][0], finished[0][1], progress


def _worker(manager, url, **kwargs):
    provider = OpenAIProvider({"endpoint": url, "model": "fake-model"})
    return GlossaryBuildWorker(manager, provider, DATASET, workers=4, retry_delay=0, **kwargs)


@pytest.fixture(scope="module")
def build(qapp, tmp_path_factory):
    """Hand-add a term, then Automatic build + translate + reconcile on a copy of the shipped glossary."""
    tmp_path = tmp_path_factory.mktemp("wp3_build")
    real_bytes = REAL_GLOSSARY.read_bytes()
    path = glossary_copy(tmp_path)
    manager = load(path)
    before = {entry.original: entry for entry in manager.get_entries()}
    groups_before = [[e.original for e in group] for group in manager.canonical_groups()]

    _GlossaryEditor(manager).edit_glossary_entry(HAND_ADDED[0], is_new=True)

    with FakeOpenAI(Script()) as server:
        worker = _worker(manager, server.url, mode=MODE_AUTO, reconcile=True)
        ok, summary, progress = _run(worker)
        requests = list(server.requests)
    assert REAL_GLOSSARY.read_bytes() == real_bytes
    return SimpleNamespace(
        path=path, manager=manager, before=before, groups_before=groups_before, ok=ok, summary=summary,
        progress=progress, requests=requests, result=worker.last_result, raw=json.loads(real_bytes),
    )


def _prompts(build, kind, term=None):
    found = [m[-1]["content"] for m in build.requests if kind_of(m) == kind]
    return [u for u in found if term is None or field(u, "Term") == term]


# -- 3.1: canonical key folds new variants; a hand-added term stays as written -------------------------


def test_a_build_creates_no_plural_article_or_possessive_twin(build):
    assert build.ok, build.summary
    after = {entry.original for entry in build.manager.get_entries()}
    expected = (set(build.before) | NEW_TERMS | {HAND_ADDED[0]}) - {"POSTMAN"}     # POSTMAN: reconcile merge
    assert after == expected
    for variant, entry in FOLDED_INTO.items():
        kept = build.manager.get_entry(entry)
        assert (kept.translation, kept.notes) == (build.before[entry].translation, build.before[entry].notes), variant
        assert build.manager.find_entry(variant).original == entry
    groups = [[e.original for e in group] for group in build.manager.canonical_groups()]
    postman = next(g for g in build.groups_before if "POSTMAN" in g)
    assert sorted(map(sorted, groups)) == sorted(
        [sorted(g) for g in build.groups_before if g is not postman] + [["Ordon Spring", "Ordon Springs"]]
    )


def test_a_term_added_by_hand_is_kept_as_written_next_to_its_singular(build):
    hand = build.manager.get_entry(HAND_ADDED[0])
    assert (hand.original, hand.translation) == HAND_ADDED
    assert build.manager.get_entry("Ordon Spring").translation == build.before["Ordon Spring"].translation


# -- 3.3: "already decided" lines, tiers, families --------------------------------------------------------


def test_the_sweep_request_carries_the_settled_entries_for_its_words(build):
    sweeps = _prompts(build, "extract")
    assert sweeps
    for user in sweeps:
        assert user.startswith("Already in the glossary (settled):\n")
        assert "Do not list these again unless this text shows a new sense." in user
        for line in ("- Lake Hylia → озеро Гайлія", "- Hylian shield → гайлійський щит",
                     "- Twilit Dragon → Сутінковий Дракон", "- Zora armor → броня Зора"):
            assert line in user, line


def test_one_word_terms_are_settled_before_the_compounds_that_contain_them(build):
    order = [field(m[-1]["content"], "Term") for m in build.requests if kind_of(m) == "translate"]
    assert order.index("Hylia") < order.index("Hylia Spring")
    (head,) = _prompts(build, "translate", "Hylia")
    assert "Settled renderings of related terms:" in head and "- Lake Hylia → озеро Гайлія" in head
    for user in _prompts(build, "translate", "Hylia Spring") + _prompts(build, "translate", "Hylian Bow"):
        assert "- Hylia → Гілія" in user           # the head term this pass just settled
    # The second member of a family is shown what its sibling got a moment earlier.
    assert all("- Hylia Spring → Джерело Гілії" in u for u in _prompts(build, "translate", "Hylian Bow"))


def test_progress_and_failures_count_families_and_a_failed_call_retries_its_whole_family(build):
    translate = [(done, total) for stage, done, total in build.progress if stage == "translate"]
    # Hylia (tier 1); Hylia Spring + Hylian Bow (one family); Sky Lanterns: 3 units for 4 terms.
    assert {total for _done, total in translate} == {3}
    assert max(done for done, _total in translate) == 3
    assert build.result.translated == 4 and build.result.failed == 0
    assert len(_prompts(build, "translate", "Hylia Spring")) == 2        # retried with its sibling
    assert len(_prompts(build, "translate", "Hylian Bow")) == 2
    for term, translation in TRANSLATIONS.items():
        entry = build.manager.get_entry(term)
        assert (entry.translation, entry.status) == (translation, STATUS_TRANSLATED), term


def test_the_translate_progress_ends_at_its_total_after_a_retry_pass(build):
    translate = [(done, total) for stage, done, total in build.progress if stage == "translate"]
    assert translate[-1] == (3, 3), translate


# -- 3.5: reconcile report, variants, aliases ------------------------------------------------------------


def test_the_reconcile_report_lists_every_change_and_each_change_can_be_undone(build):
    assert build.result.reconcile_changes == [                          # clusters in head-term order
        "'Lake Hylia': озеро Гайлія → Озеро Гілія",
        "merged 'POSTMAN' into 'The Postman'",
    ]
    assert "reconciled 1, merged 1" in build.summary
    assert "\n\nReconciled:\n- 'Lake Hylia': озеро Гайлія → Озеро Гілія\n- merged 'POSTMAN' into 'The Postman'" in build.summary
    lake = build.manager.get_entry("Lake Hylia")
    assert lake.translation == "Озеро Гілія"
    assert ("озеро Гайлія", "before reconcile") in [(v.translation, v.rationale) for v in lake.translation_variants]
    postman = build.manager.get_entry("POSTMAN")                        # found through its alias
    assert postman.original == "The Postman" and "POSTMAN" in postman.aliases
    assert postman.translation == "Листоноша" and "Поштар" in [v.translation for v in postman.translation_variants]
    reconciles = _prompts(build, "reconcile")
    assert len(reconciles) >= 50                                        # every family that looks off is asked


# -- 3.6: id per entry on the next save; deletion record of the merged spelling ----------------------------


def test_the_saved_file_has_an_id_per_entry_and_untouched_entries_are_otherwise_unchanged(build):
    stored = json.loads(build.path.read_text(encoding="utf-8"))
    live = [item for item in stored if not item.get("deleted_at")]
    assert all(re.fullmatch(r"[0-9a-f]{32}", item["id"]) for item in live)
    touched = NEW_TERMS | {HAND_ADDED[0], "POSTMAN", "The Postman", "Lake Hylia"}
    by_original = {item["original"]: item for item in live}
    for old in build.raw:
        if old["original"] in touched:
            continue
        new = dict(by_original[old["original"]])
        assert new.pop("id") == legacy_entry_id(old["original"])
        assert new == old, old["original"]
    (stone,) = [item for item in stored if item.get("deleted_at")]
    assert (stone["original"], stone["id"]) == ("POSTMAN", legacy_entry_id("POSTMAN"))


# -- 3.1 + 3.6: forced re-translation keeps confirmed entries; the file is written every 20 results --------


def test_forced_retranslation_skips_confirmed_entries_and_writes_every_twenty_results(build, tmp_path):
    path = tmp_path / "glossary.json"
    path.write_text(build.path.read_text(encoding="utf-8"), encoding="utf-8")
    manager = load(path)
    for term in ("Clawshot", "Hylia"):
        entry = manager.get_entry(term)
        manager.update_entry(term, entry.translation, entry.notes, status=STATUS_CONFIRMED)
    snapshots = []
    real_write = manager._write_file

    def counting_write(raw):
        snapshots.append(sum(1 for item in json.loads(raw) if str(item.get("translation", "")).startswith("Новий ")))
        real_write(raw)

    manager._write_file = counting_write

    with FakeOpenAI(Script(forced=True)) as server:
        worker = _worker(manager, server.url, mode=MODE_TRANSLATE, translate=True, force_retranslate=True)
        ok, summary, progress = _run(worker)
        asked = {field(u, "Term") for u in server.of_kind("translate")}

    assert ok, summary
    assert {"Clawshot", "Hylia"}.isdisjoint(asked)
    assert manager.get_entry("Clawshot").translation == "Кігтемет"
    assert manager.get_entry("Hylia").translation == "Гілія"
    others = [e for e in manager.get_entries() if e.status != STATUS_CONFIRMED]
    assert len(others) == len(manager.get_entries()) - 2
    assert all(e.translation == f"Новий {e.original}" for e in others)
    # Results (family units) are written to disk in batches of STORE_BATCH, not only at the end.
    units = [total for stage, _done, total in progress if stage == "translate"][-1]
    growth = [b - a for a, b in zip([0, *snapshots], snapshots) if b != a]
    assert len(growth) >= units // STORE_BATCH
    assert max(growth) <= STORE_BATCH * FAMILY_BATCH
    assert snapshots[-1] == len(others)
