"""The reconcile pass: related entries are made to agree, by request and on the record (WP3 3.5)."""
import json
from pathlib import Path

import pytest

from core.glossary.models import GlossaryEntry
from core.glossary_build.ai_adapters import make_reconcile
from core.glossary_build.pipeline_coordinator import MODE_RECONCILE, GlossaryBuildCoordinator
from core.glossary_build.reconcile_driver import Change, cluster_payload, clusters, plan_changes
from core.glossary_manager import STATUS_CONFIRMED, STATUS_SEEDED, STATUS_TRANSLATED, GlossaryManager
from handlers.translation.glossary_pipeline_worker import GlossaryBuildWorker
from utils.json_extract import ParseError

PROMPTS = json.loads(Path("translation_prompts/glossary_pipeline_prompts.json").read_text(encoding="utf-8"))

ROWS = [
    ("Clawshot", "Кігтемет", STATUS_CONFIRMED),
    ("Clawshots", "Гакостріли", STATUS_TRANSLATED),
    ("Postman", "Листоноша", ""),
    ("The Postman", "Поштар", STATUS_TRANSLATED),
    ("Hylia", "Гайлія", STATUS_CONFIRMED),
    ("Lake Hylia", "Озеро Хайлія", STATUS_TRANSLATED),
    ("Rupee", "Рупія", STATUS_TRANSLATED),
]

# What the model answers for the cluster that contains the given term.
REPLIES = {
    "Clawshot": {
        "merge": [],
        "canonical_translation_by_term": {"Clawshots": "Кігтемети", "Clawshot": "Гакостріл"},
        "keep_separate": ["Clawshot", "Clawshots"],
        "reason": "один корінь",
    },
    "Postman": {"merge": [["Postman", "The Postman"]], "canonical_translation_by_term": {}, "reason": "той самий термін"},
    "Hylia": {"merge": [], "canonical_translation_by_term": {"Lake Hylia": "Озеро Гайлія"}, "reason": "г, не х"},
}


def _entry(original, translation, status=""):
    return GlossaryEntry(original=original, translation=translation, status=status)


def _manager(rows=ROWS):
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
    for original, translation, status in rows:
        manager.add_entry(original, translation, "", fold_variants=False)
        manager.update_entry(original, translation, "", status=status)
    return manager


def _call(seen=None):
    def call(messages):
        user = messages[1]["content"]
        listing = json.loads(user[user.index("["):user.rindex("]") + 1])
        terms = [row["term"] for row in listing]
        if seen is not None:
            seen.append(terms)
        return json.dumps(next(reply for term, reply in REPLIES.items() if term in terms))

    return call


def _state(manager):
    return [(e.original, e.translation, e.status, e.aliases, tuple(v.translation for v in e.translation_variants))
            for e in manager.get_entries()]


class TestClusters:
    def test_related_entries_that_look_off_are_grouped_in_a_fixed_order(self):
        entries = [_entry(*row) for row in ROWS]

        found = [[e.original for e in group] for group in clusters(entries)]

        assert found == [["Clawshot", "Clawshots"], ["Hylia", "Lake Hylia"], ["Postman", "The Postman"]]
        assert found == [[e.original for e in group] for group in clusters(reversed(entries))]

    def test_a_family_whose_translations_share_the_root_is_not_asked_about(self):
        entries = [_entry("Zora", "Зора"), _entry("Zora Armor", "Обладунок зорів"), _entry("Zora River", "Річка Зора")]

        assert clusters(entries) == []

    def test_untranslated_entries_and_all_confirmed_groups_are_left_out(self):
        entries = [
            _entry("Zora", "", STATUS_SEEDED), _entry("Zoras", "Зори", STATUS_TRANSLATED),
            _entry("Goron", "Ґорон", STATUS_CONFIRMED), _entry("Gorons", "Горони", STATUS_CONFIRMED),
        ]

        assert clusters(entries) == []

    def test_a_likely_duplicate_spelling_joins_a_cluster_without_a_shared_word(self):
        entries = [_entry("Ooccoo", "Уккуу"), _entry("Oocco", "Окко")]

        assert [[e.original for e in group] for group in clusters(entries)] == [["Oocco", "Ooccoo"]]

    def test_the_payload_shows_who_decided_each_translation(self):
        payload = cluster_payload([
            _entry("Hylia", "Гайлія", STATUS_CONFIRMED), _entry("Lake Hylia", "Озеро Хайлія", STATUS_TRANSLATED),
            GlossaryEntry("Hylian", "гайлійський", notes="{{TERM}} — " + "дуже довгий опис " * 30),
        ])

        assert [row["status"] for row in payload] == ["confirmed", "machine", "existing"]
        assert payload[2]["note"].startswith("гайлійський — ") and len(payload[2]["note"]) <= 160


class TestPlanChanges:
    MEMBERS = [
        _entry("Clawshot", "Кігтемет", STATUS_CONFIRMED),
        _entry("Clawshots", "Гакостріли", STATUS_TRANSLATED),
        _entry("Claw Shot", "Кіготь", STATUS_TRANSLATED),
    ]

    def test_a_confirmed_entry_is_never_retranslated(self):
        changes = plan_changes(self.MEMBERS, {"canonical_translation_by_term": {"Clawshot": "Інше", "Clawshots": "Кігтемети"}})

        assert changes == [Change("align", "Clawshots", old="Гакостріли", new="Кігтемети")]

    def test_the_confirmed_member_survives_a_merge_wherever_it_is_listed(self):
        changes = plan_changes(self.MEMBERS, {"merge": [["Claw Shot", "Clawshot"]], "reason": "one term"})

        assert changes == [Change("merge", "Claw Shot", into="Clawshot", reason="one term")]

    def test_two_confirmed_entries_are_never_merged(self):
        members = [_entry("Goron", "Ґорон", STATUS_CONFIRMED), _entry("Gorons", "Ґорони", STATUS_CONFIRMED)]

        assert plan_changes(members, {"merge": [["Goron", "Gorons"]]}) == []

    def test_terms_outside_the_cluster_and_malformed_replies_change_nothing(self):
        verdict = {"merge": [["Clawshots", "Rupee"], "Clawshot"], "canonical_translation_by_term": {"Rupee": "Рубін"}}

        assert plan_changes(self.MEMBERS, verdict) == []
        assert plan_changes(self.MEMBERS, {"merge": "all", "canonical_translation_by_term": ["x"]}) == []
        assert plan_changes(self.MEMBERS, []) == []

    def test_an_entry_merged_away_is_not_retranslated_as_well(self):
        verdict = {"merge": [["Clawshots", "Claw Shot"]], "canonical_translation_by_term": {"Claw Shot": "Кігтемет"}}

        assert [change.kind for change in plan_changes(self.MEMBERS, verdict)] == ["merge"]

    def test_the_current_translation_is_not_a_change(self):
        assert plan_changes(self.MEMBERS, {"canonical_translation_by_term": {"Clawshots": " Гакостріли "}}) == []


class TestAdapter:
    def test_the_request_lists_the_cluster_and_returns_the_object(self):
        seen = []
        reconcile = make_reconcile(lambda messages: seen.append(messages) or '```json\n{"merge": []}\n```', PROMPTS)

        assert reconcile([{"term": "Hylia", "translation": "Гайлія"}]) == {"merge": []}
        assert '"term": "Hylia"' in seen[0][1]["content"] and "Гайлія" in seen[0][1]["content"]
        assert "{target_lang}" not in seen[0][0]["content"] and "{entries}" not in seen[0][1]["content"]

    @pytest.mark.parametrize("reply", ["I could not decide.", '{"merge": [["Postman", "The Post'])
    def test_an_unreadable_or_cut_off_reply_is_an_error_not_a_verdict(self, reply):
        with pytest.raises(ParseError):
            make_reconcile(lambda messages: reply, PROMPTS)([{"term": "Postman"}])


class TestCoordinator:
    def test_the_pass_merges_aligns_keeps_variants_and_leaves_confirmed_alone(self):
        manager = _manager()
        asked, log = [], []
        coordinator = GlossaryBuildCoordinator(manager, _call(asked), PROMPTS, workers=1, on_log=log.append)

        result = coordinator.run_reconcile()

        assert asked == [["Clawshot", "Clawshots"], ["Hylia", "Lake Hylia"], ["Postman", "The Postman"]]
        assert (result.reconciled, result.merged, result.failed) == (2, 1, 0)
        by_name = {e.original: e for e in manager.get_entries()}
        assert "The Postman" not in by_name
        assert by_name["Postman"].translation == "Листоноша" and by_name["Postman"].aliases == ("The Postman",)
        assert "Поштар" in [v.translation for v in by_name["Postman"].translation_variants]
        assert manager.get_entry("The Postman") is by_name["Postman"]          # still found by its old spelling
        assert (by_name["Clawshot"].translation, by_name["Clawshot"].status) == ("Кігтемет", STATUS_CONFIRMED)
        assert by_name["Clawshots"].translation == "Кігтемети"
        assert [v.translation for v in by_name["Clawshots"].translation_variants] == ["Кігтемети", "Гакостріли"]
        assert by_name["Lake Hylia"].translation == "Озеро Гайлія" and by_name["Lake Hylia"].status == STATUS_TRANSLATED
        assert by_name["Rupee"].translation == "Рупія"
        assert result.reconcile_changes == [
            "'Clawshots': Гакостріли → Кігтемети",
            "'Lake Hylia': Озеро Хайлія → Озеро Гайлія",
            "merged 'The Postman' into 'Postman'",
        ]
        assert [line for line in log if line.startswith("Reconcile: ")] == [
            f"Reconcile: {line}" for line in result.reconcile_changes
        ]

    def test_a_second_run_changes_nothing(self):
        manager = _manager()
        GlossaryBuildCoordinator(manager, _call(), PROMPTS, workers=1).run_reconcile()
        before = _state(manager)
        asked = []

        result = GlossaryBuildCoordinator(manager, _call(asked), PROMPTS, workers=1).run_reconcile()

        assert (result.reconciled, result.merged, result.reconcile_changes) == (0, 0, [])
        assert _state(manager) == before
        assert asked == [["Clawshot", "Clawshots"]]      # the one pair that still shares a spelling

    def test_the_result_is_the_same_with_parallel_requests(self):
        serial, parallel = _manager(), _manager()
        GlossaryBuildCoordinator(serial, _call(), PROMPTS, workers=1).run_reconcile()
        GlossaryBuildCoordinator(parallel, _call(), PROMPTS, workers=3).run_reconcile()

        assert _state(serial) == _state(parallel)

    def test_an_entry_confirmed_while_the_request_was_out_is_left_alone(self):
        manager = _manager([row for row in ROWS if "Hylia" in row[0]])

        def call(messages):
            manager.update_entry("Lake Hylia", "Озеро Хайлія", "", status=STATUS_CONFIRMED)
            return _call()(messages)

        result = GlossaryBuildCoordinator(manager, call, PROMPTS, workers=1).run_reconcile()

        assert result.reconciled == 0 and manager.get_entry("Lake Hylia").translation == "Озеро Хайлія"

    def test_reconcile_mode_builds_nothing(self):
        manager = _manager()
        calls = []
        coordinator = GlossaryBuildCoordinator(manager, lambda messages: calls.append(1) or "[]", PROMPTS)

        result = coordinator.build([["Clawshot text"]], MODE_RECONCILE)

        assert calls == [] and result.seeded == 0


class _Provider:
    def translate(self, messages, session=None, settings_override=None):
        return type("Response", (), {"text": _call()(messages)})()


def test_the_worker_runs_the_pass_and_reports_every_change(qtbot):
    manager = _manager()
    worker = GlossaryBuildWorker(manager, _Provider(), [[]], mode=MODE_RECONCILE, prompts=PROMPTS, workers=1)
    finished = []
    worker.build_finished.connect(lambda ok, summary: finished.append((ok, summary)))

    worker.run()

    ok, summary = finished[0]
    assert ok is True
    assert "reconciled 2, merged 1" in summary
    assert "- merged 'The Postman' into 'Postman'" in summary and "- 'Clawshots': Гакостріли → Кігтемети" in summary


def test_the_worker_skips_the_pass_unless_asked(qtbot):
    manager = _manager()
    before = _state(manager)
    worker = GlossaryBuildWorker(manager, _Provider(), [[]], mode="translate", translate=True, prompts=PROMPTS)

    worker.run()

    assert _state(manager) == before
