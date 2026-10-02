"""The lines of one conversation travel to the model in one request (WP4 4.3)."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.translation.providers import ProviderResponse
from handlers.translation.ai_worker import AIWorker
from handlers.translation.worker.run_mixin import ITEMS_PER_CHUNK, pack_groups
from plugins.base_game_rules import BaseGameRules
from plugins.zelda_bmg.msg_flow import MsgFlowContext


def _ids(chunks):
    return [[item["id"] for item in chunk] for chunk in chunks]


def _conversations(*sizes):
    """Items numbered in a row; ``group`` is the conversation each belongs to."""
    items = []
    for conversation, size in enumerate(sizes):
        start = len(items)
        items.extend({"id": start + offset, "group": f"c{conversation}"} for offset in range(size))
    return items


class TestPacking:
    def test_three_conversations_of_five_make_ten_and_five(self):
        chunks = pack_groups(_conversations(5, 5, 5), lambda item: item["group"])

        assert [len(chunk) for chunk in chunks] == [10, 5]
        assert all(len({item["group"] for item in chunk}) <= 2 for chunk in chunks)
        assert {item["group"] for item in chunks[1]} == {"c2"}             # no conversation is split

    def test_without_groups_it_is_the_plain_cut(self):
        items = [{"id": index} for index in range(30)]

        assert _ids(pack_groups(items, None)) == [list(range(0, 12)), list(range(12, 24)), list(range(24, 30))]
        assert pack_groups(items, lambda item: None) == pack_groups(items, None)

    def test_a_conversation_longer_than_a_chunk_is_cut_and_only_that_one(self):
        chunks = pack_groups(_conversations(3, 30, 4), lambda item: item["group"])

        assert [len(chunk) for chunk in chunks] == [3, 12, 12, 10]
        assert {item["group"] for item in chunks[0]} == {"c0"}
        assert {item["group"] for item in chunks[3]} == {"c1", "c2"}       # the tail shares a chunk with the next one

    def test_members_scattered_through_the_list_are_brought_together(self):
        items = [
            {"id": 0, "group": "a"}, {"id": 1, "group": None}, {"id": 2, "group": "b"},
            {"id": 3, "group": "a"}, {"id": 4, "group": "b"}, {"id": 5, "group": "a"},
        ]

        # "a" is gathered at its first member; the lone line and "b" then share what is left of the limit
        assert _ids(pack_groups(items, lambda item: item["group"], limit=3)) == [[0, 3, 5], [1, 2, 4]]

    def test_every_item_is_kept_exactly_once(self):
        items = _conversations(7, 1, 13, 2, 12, 5)

        chunks = pack_groups(items, lambda item: item["group"])

        assert sorted(item["id"] for chunk in chunks for item in chunk) == list(range(len(items)))
        assert all(len(chunk) <= ITEMS_PER_CHUNK for chunk in chunks)


class _Rules(BaseGameRules):
    """Strings 0-4, 5-9 and 10-14 of block 0 are three conversations."""

    def get_ai_flow_group_for_string(self, block_idx, string_idx):
        return f"{block_idx}:{string_idx // 5}"


def _worker(task_details, rules):
    composer = MagicMock()
    composer.compose_batch_request.return_value = ("sys", "user", {})
    composer._get_mempalace_client.return_value = None
    composer.mw = SimpleNamespace(current_game_rules=rules)
    provider = MagicMock()
    provider.translate.side_effect = lambda messages, **_: ProviderResponse(text=json.dumps({"translated_strings": []}))
    details = dict({'type': 'translate_block_chunked', 'composer_args': {}, 'block_idx': 0}, **task_details)
    return AIWorker(provider, composer, details)


class TestWorkerPlan:
    ITEMS = [{"id": index, "text": f"line {index}"} for index in range(15)]

    def test_a_new_run_packs_whole_conversations(self):
        worker = _worker({'source_items': self.ITEMS, 'flow_chunks': True}, _Rules())

        chunks = worker._plan_chunks(self.ITEMS, None, "block")

        assert _ids(chunks) == [list(range(0, 10)), list(range(10, 15))]

    def test_a_run_started_before_this_plan_resumes_with_the_old_cut(self):
        worker = _worker({'source_items': self.ITEMS}, _Rules())

        assert _ids(worker._plan_chunks(self.ITEMS, None, "block")) == [list(range(0, 12)), list(range(12, 15))]

    def test_a_plugin_without_conversations_gets_the_plain_cut(self):
        worker = _worker({'source_items': self.ITEMS, 'flow_chunks': True}, BaseGameRules())

        assert _ids(worker._plan_chunks(self.ITEMS, None, "block")) == [list(range(0, 12)), list(range(12, 15))]

    def test_the_real_place_of_an_item_is_asked_not_its_number_in_the_run(self):
        # a project-wide run: items are numbered 0..n, their places are in temp_id_map
        places = {index: (0, 14 - index) for index in range(15)}
        worker = _worker({'source_items': self.ITEMS, 'flow_chunks': True, 'temp_id_map': places}, _Rules())

        chunks = worker._plan_chunks(self.ITEMS, None, "block")

        assert _ids(chunks) == [list(range(0, 10)), list(range(10, 15))]
        assert {places[item["id"]][1] // 5 for item in chunks[1]} == {0}

    def test_a_plugin_that_raises_does_not_stop_the_run(self):
        rules = _Rules()
        rules.get_ai_flow_group_for_string = MagicMock(side_effect=RuntimeError("no flow data"))
        worker = _worker({'source_items': self.ITEMS, 'flow_chunks': True}, rules)

        assert [len(chunk) for chunk in worker._plan_chunks(self.ITEMS, None, "block")] == [12, 3]


class TestTwilightPrincess:
    def _context(self):
        context = MsgFlowContext(None)
        first, second = SimpleNamespace(flow_id=7), SimpleNamespace(flow_id=9)
        context._by_msg = {3: [first], 4: [first, second], 5: [second]}
        return context

    def test_a_message_belongs_to_the_first_entry_that_reaches_it(self):
        context = self._context()

        assert [context.group_for_message(index) for index in (3, 4, 5, 6)] == [7, 7, 9, None]

    def test_the_group_id_is_unique_across_blocks(self):
        from plugins.zelda_bmg.rules import GameRules

        rules = GameRules.__new__(GameRules)
        rules._get_flow_context_for_block = lambda block_idx: self._context() if block_idx in (2, 3) else None

        assert rules.get_ai_flow_group_for_string(2, 4) == "2:7"
        assert rules.get_ai_flow_group_for_string(3, 4) == "3:7"
        assert rules.get_ai_flow_group_for_string(2, 6) is None           # no conversation reaches it
        assert rules.get_ai_flow_group_for_string(9, 4) is None           # no flow data for the block
        assert rules.get_ai_flow_group_for_string(2, "x") is None


@pytest.mark.parametrize("stored, expected", [({}, False), ({'flow_chunks': True}, True)])
def test_a_resumed_run_keeps_the_plan_it_was_started_with(stored, expected):
    from handlers.translation.batch_translator import AIBatchTranslator

    main_handler = MagicMock()
    main_handler.translation_progress = {0: dict({'completed_chunks': {0}, 'total_chunks': 2}, **stored)}
    translator = AIBatchTranslator.__new__(AIBatchTranslator)
    translator.main_handler = main_handler
    translator.mw = MagicMock()
    context = {
        'type': 'translate_block_chunked', 'provider': MagicMock(), 'block_idx': 0, 'is_resume': True,
        'source_items': [{"id": 0, "text": "A"}], 'prepared': False, 'mode_description': 'block 1', 'workers': 1,
    }
    main_handler.glossary_handler.load_prompts.return_value = (None, None)   # stop right after the plan is chosen

    translator.initiate_batch_translation(context)

    assert context['flow_chunks'] is expected
