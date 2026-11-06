"""An AI reply keeps the tags in the form the AI was sent ({COLOR(3)}), and the tag check accepts it although the
data store holds the game's form (<COLOR>(3))."""
import json
from types import SimpleNamespace

import pytest

from core.translation.layout_contract import TranslationLayoutError
from handlers.translation.worker.run_mixin import AIWorkerRunMixin
from plugins.luigis_mansion_1_gc.rules import GameRules

SOURCE = "It's me, <COLOR>(3)Professor E. Gadd<COLOR>(0)..."


def _check(reply):
    worker = SimpleNamespace(mw=None, task_details={"block_idx": 0})
    worker.mw = SimpleNamespace(current_game_rules=GameRules(worker.mw))
    chunk = [{"id": 0, "text": SOURCE}]
    return AIWorkerRunMixin._validate_chunk_result(worker, 0, chunk, json.dumps(
        {"translated_strings": [{"id": 0, "translation": reply}]}))


def test_a_reply_with_the_tags_as_sent_is_accepted():
    _check("Це я, {COLOR(3)}професор Е. Ґедд{COLOR(0)}...")


def test_a_reply_that_lost_a_tag_is_refused():
    with pytest.raises(TranslationLayoutError):
        _check("Це я, {COLOR(3)}професор Е. Ґедд...")
