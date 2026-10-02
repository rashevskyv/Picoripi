"""Build requests are told what the glossary has already decided (WP3 3.3)."""
import json
from pathlib import Path
from unittest.mock import MagicMock

from core.glossary.models import GlossaryEntry
from core.glossary_build.ai_adapters import make_extract, make_propose
from core.glossary_build.decisions import decided_block, families, is_decided, select_related
from core.glossary_build.pipeline_coordinator import MODE_DRAFT, GlossaryBuildCoordinator
from core.glossary_manager import (
    STATUS_CONFIRMED,
    STATUS_SEEDED,
    STATUS_TRANSLATED,
    GlossaryManager,
)
from core.translation.providers import ProviderResponse
from handlers.translation.ai_worker import AIWorker

PROMPTS = json.loads(Path("translation_prompts/glossary_pipeline_prompts.json").read_text(encoding="utf-8"))


def _entry(original, translation, status=""):
    return GlossaryEntry(original=original, translation=translation, status=status)


def _manager():
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=None, raw_text="")
    return manager


class TestSelectRelated:
    def test_picks_entries_that_share_a_word_and_leaves_the_rest_out(self):
        entries = [_entry("Rupee", "Рупія"), _entry("Lake Hylia", "Озеро Хайлія")]

        related = select_related(entries, "Great Bridge of Hylia")

        assert related == "- Lake Hylia → Озеро Хайлія"

    def test_a_short_stem_relates_hylia_to_hylian_and_a_plural_to_its_singular(self):
        entries = [_entry("Hylia", "Хайлія"), _entry("Clawshot", "Кігтемет")]

        assert "Hylia → Хайлія" in select_related(entries, "Hylian Shield")
        assert "Clawshot → Кігтемет" in select_related(entries, "Clawshots")

    def test_a_person_s_decision_outranks_a_machine_one_then_more_shared_words_win(self):
        entries = [
            _entry("Zora Armor", "Обладунок зора", STATUS_TRANSLATED),
            _entry("Zora River", "Річка Зора", STATUS_CONFIRMED),
            _entry("Zora Queen Armor", "Обладунок королеви зора", STATUS_TRANSLATED),
        ]

        lines = select_related(entries, "Zora Queen Armor Set").splitlines()

        assert [line.split(" → ")[0] for line in lines] == ["- Zora River", "- Zora Queen Armor", "- Zora Armor"]

    def test_undecided_entries_and_the_term_itself_are_never_offered(self):
        entries = [
            _entry("Zora", "", STATUS_SEEDED),              # no translation
            _entry("Zora Armor", "чернетка", STATUS_SEEDED),  # a draft nobody settled on
            _entry("Zoras", "Зори", STATUS_TRANSLATED),
        ]

        assert [is_decided(e) for e in entries] == [False, False, True]
        assert select_related(entries, "Zoras", exclude="zoras") == ""
        assert select_related(entries, "Zora", exclude="Zora") == "- Zoras → Зори"   # a sibling, not itself

    def test_the_list_is_capped_and_stop_words_relate_nothing(self):
        entries = [_entry(f"Zora {index:02d}", f"Зора {index:02d}") for index in range(60)]

        assert len(select_related(entries, "Zora", limit=40).splitlines()) == 40
        assert select_related([_entry("Hero of Time", "Герой часу")], "Sword of the Sages") == ""

    def test_no_related_entries_means_no_block(self):
        assert decided_block("", "translate") == ""
        assert decided_block("- A → Б", "translate").startswith("Settled renderings of related terms:\n- A → Б\n")


class TestFamilies:
    def test_entries_sharing_a_word_form_one_family_with_the_head_first(self):
        entries = [_entry(t, "") for t in ("Zora Armor", "Hylian Shield", "Zora", "Hylia", "The Zora Queen", "Rupee")]

        grouped = [[e.original for e in family] for family in families(entries)]

        assert grouped == [["Hylia", "Hylian Shield"], ["Rupee"], ["Zora", "Zora Armor", "The Zora Queen"]]

    def test_the_grouping_does_not_depend_on_input_order(self):
        terms = ["Zora Armor", "Hylian Shield", "Zora", "Hylia", "The Zora Queen", "Rupee"]
        forward = [[e.original for e in family] for family in families(_entry(t, "") for t in terms)]
        backward = [[e.original for e in family] for family in families(_entry(t, "") for t in reversed(terms))]

        assert forward == backward

    def test_a_word_shared_by_many_entries_joins_nothing(self):
        entries = [_entry(f"Key {name}", "") for name in (
            "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf",
            "Hotel", "India", "Juliet", "Kilo", "Lima", "Mike",
        )]

        assert all(len(family) == 1 for family in families(entries))


class TestAdapters:
    def test_an_empty_block_leaves_no_hole_in_the_prompt(self):
        seen = []
        propose = make_propose(lambda messages: seen.append(messages[1]["content"]) or "[]", PROMPTS)

        propose("Zora", "river folk")

        assert "{decided}" not in seen[0] and "\n\n\n" not in seen[0]

    def test_the_block_fills_the_slot(self):
        seen = []
        propose = make_propose(lambda messages: seen.append(messages[1]["content"]) or "[]", PROMPTS)

        propose("Zoras", "river folk", "Settled renderings of related terms:\n- Zora → Зора")

        assert "- Zora → Зора" in seen[0] and "{decided}" not in seen[0]
        assert seen[0].index("Term: Zoras") < seen[0].index("- Zora → Зора")

    def test_a_template_without_the_slot_still_gets_the_block(self):
        prompts = json.loads(json.dumps(PROMPTS))
        prompts["extract"]["user_prompt_template"] = "Game text chunk:\n{text_chunk}"
        seen = []
        extract = make_extract(lambda messages: seen.append(messages[1]["content"]) or "[]", prompts)

        extract("The Zoras swim.", "Already in the glossary (settled):\n- Zora → Зора")

        assert seen[0].startswith("Already in the glossary (settled):\n- Zora → Зора\n\nGame text chunk:")

    def test_blank_lines_inside_the_game_text_survive(self):
        seen = []
        extract = make_extract(lambda messages: seen.append(messages[1]["content"]) or "[]", PROMPTS)

        extract("first line\n\n\n\nsecond line")

        assert "first line\n\n\n\nsecond line" in seen[0]


class TestCoordinator:
    def test_the_second_family_member_is_told_what_the_first_one_got(self):
        manager = _manager()
        for term in ("Clawshots", "Clawshot", "Rupee"):
            manager.add_entry(term, "", "a description", fold_variants=False)
        prompts = {}

        def call(messages):
            user = messages[1]["content"]
            term = user.split("Term:", 1)[1].split("\n", 1)[0].strip()
            prompts[term] = user
            return json.dumps([{"translation": {"Clawshot": "Кігтемет"}.get(term, "щось"), "rationale": ""}])

        GlossaryBuildCoordinator(manager, call, PROMPTS, workers=1).run_translate()

        assert list(prompts) == ["Clawshot", "Clawshots", "Rupee"]
        assert "Settled renderings" not in prompts["Clawshot"]
        assert "- Clawshot → Кігтемет" in prompts["Clawshots"]
        assert "Кігтемет" not in prompts["Rupee"]

    def test_a_term_translated_earlier_in_the_pass_reaches_other_families_too(self):
        manager = _manager()
        manager.add_entry("Zora", "Зора", "river folk", fold_variants=False)
        manager.update_entry("Zora", "Зора", "river folk", status=STATUS_CONFIRMED)
        manager.add_entry("Zora Armor", "", "armor of the river folk", fold_variants=False)
        prompts = []

        def call(messages):
            prompts.append(messages[1]["content"])
            return json.dumps([{"translation": "Обладунок зора", "rationale": ""}])

        GlossaryBuildCoordinator(manager, call, PROMPTS, workers=1).run_translate()

        assert len(prompts) == 1 and "- Zora → Зора" in prompts[0]

    def test_a_forced_retranslation_is_not_shown_the_renderings_it_is_replacing(self):
        manager = _manager()
        manager.add_entry("Zora", "Стара Зора", "river folk", fold_variants=False)
        manager.add_entry("Zora Armor", "Старий обладунок", "armor", fold_variants=False)
        manager.update_entry("Zora", "Стара Зора", "river folk", status=STATUS_TRANSLATED)
        manager.update_entry("Zora Armor", "Старий обладунок", "armor", status=STATUS_TRANSLATED)
        prompts = {}

        def call(messages):
            user = messages[1]["content"]
            term = user.split("Term:", 1)[1].split("\n", 1)[0].strip()
            prompts[term] = user
            return json.dumps([{"translation": "Нова " + term, "rationale": ""}])

        GlossaryBuildCoordinator(manager, call, PROMPTS, workers=1).run_translate(force=True)

        assert "Стар" not in prompts["Zora"] and "Стар" not in prompts["Zora Armor"]
        assert "- Zora → Нова Zora" in prompts["Zora Armor"]

    def test_the_sweep_is_told_what_is_settled_for_the_words_in_its_chunk(self):
        manager = _manager()
        manager.add_entry("Zora", "Зора", "river folk", fold_variants=False)
        manager.add_entry("Rupee", "Рупія", "money", fold_variants=False)
        prompts = []

        def call(messages):
            prompts.append(messages[1]["content"])
            return "[]"

        GlossaryBuildCoordinator(manager, call, PROMPTS, workers=1).build([["The Zoras live upstream."]], MODE_DRAFT)

        assert len(prompts) == 1
        assert "- Zora → Зора" in prompts[0] and "Rupee" not in prompts[0]


def test_the_one_shot_builder_tells_each_chunk_what_is_already_decided():
    provider = MagicMock()
    first = "Clawshot is a tool. " + "x" * 979      # 999 chars + the joining newline = one chunk
    replies = iter([
        ProviderResponse(text=json.dumps([{"term": "Clawshot", "translation": "Кігтемет"}])),
        ProviderResponse(text="[]"),
    ])
    prompts = []

    def translate(messages, **_kwargs):
        prompts.append(messages[1]["content"])
        return next(replies)

    provider.translate.side_effect = translate
    worker = AIWorker(provider, MagicMock(), {
        "type": "build_glossary",
        "user_prompt_template": "Chunk:\n{text_chunk}",
        "block_data": [first, "Two Clawshots hang on the wall of Zora hall."],
        "target_indices": [0, 1],
        "chunk_size": 1000,
        "dialog_steps": ["1", "2", "3", "4"],
        "decided_entries": [_entry("Zora", "Зора", STATUS_CONFIRMED), _entry("Rupee", "Рупія", STATUS_CONFIRMED)],
    })
    error = MagicMock()
    worker.error.connect(error)

    worker.run()

    error.assert_not_called()
    assert len(prompts) == 2
    assert prompts[0].startswith("Chunk:")                         # nothing related yet
    assert prompts[1].startswith("Already in the glossary (settled):")
    assert "- Zora → Зора" in prompts[1] and "- Clawshot → Кігтемет" in prompts[1]
    assert "Rupee" not in prompts[1]
