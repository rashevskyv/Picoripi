"""Tests for TP message-flow (FLW1/FLI1) parsing and the AI flow-context hooks."""
import struct

import pytest

from plugins.zelda_bmg.msg_flow import (
    actor_map_for_bmg, parse_flow_sections, build_conversation, flow_context_from_bmg,
    MsgFlowContext, QUERY_LABELS, EVENT_LABELS,
    NODE_MESSAGE, NODE_BRANCH, NODE_EVENT,
)


def _msg_node(msg_index, next_idx):
    return struct.pack(">BBHHH", NODE_MESSAGE, 0, msg_index, next_idx, 0)


def _branch_node(query_idx, param, table_base):
    return struct.pack(">BBHHH", NODE_BRANCH, 0, query_idx, param, table_base)


def _event_node(event_idx, next_idx):
    return struct.pack(">BBH4x", NODE_EVENT, event_idx, next_idx)


def _flw1(nodes, branch_table):
    body = struct.pack(">HH", len(nodes), len(branch_table)) + b"\x00" * 4
    body += b"".join(nodes)
    body += struct.pack(f">{len(branch_table)}H", *branch_table) if branch_table else b""
    return struct.pack(">4sI", b"FLW1", 8 + len(body)) + body


def _fli1(flows):
    body = struct.pack(">H", len(flows)) + b"\x00" * 6
    for flow_id, node_idx in flows.items():
        body += struct.pack(">IHH", flow_id << 16, node_idx, 0)
    return struct.pack(">4sI", b"FLI1", 8 + len(body)) + body


def _sample_sections():
    # Conversation: msg 0 -> player choice (2 options)
    #   option 1: msg 1 -> event "give item"(17)
    #   option 2: msg 2 -> end
    nodes = [
        _msg_node(0, 1),
        _branch_node(4, 0, 0),   # query 4 = Player Choice (2 options)
        _msg_node(1, 4),
        _msg_node(2, 0xFFFF),
        _event_node(17, 0xFFFF),
    ]
    return _flw1(nodes, [2, 3]), _fli1({0x152: 0})


def test_parse_flow_sections():
    flw1, fli1 = _sample_sections()
    flow = parse_flow_sections(flw1, fli1)
    assert flow is not None
    assert len(flow.nodes) == 5
    assert flow.flows == {0x152: 0}
    assert flow.branch_table[:2] == [2, 3]
    assert flow.nodes[1].kind == NODE_BRANCH
    assert flow.nodes[1].arg == 4
    assert flow.nodes[4].kind == NODE_EVENT
    assert flow.nodes[4].arg == 17


def test_parse_flow_sections_uses_branch_count_not_alignment_bytes():
    flw1, fli1 = _sample_sections()
    padded = flw1 + b"\xff\x00\x00\x00" * 16
    flow = parse_flow_sections(padded, fli1)
    assert flow is not None
    assert flow.branch_table == [2, 3]


def test_build_conversation_walks_branches_and_events():
    flw1, fli1 = _sample_sections()
    flow = parse_flow_sections(flw1, fli1)
    conv = build_conversation(flow, 0x152)

    assert conv.msg_indices == [0, 1, 2]
    # conditions on the choice branches
    assert conv.msg_conditions[1] == [f"{QUERY_LABELS[4]} = option 1"]
    assert conv.msg_conditions[2] == [f"{QUERY_LABELS[4]} = option 2"]
    # the give-item event is attached to the message it follows
    assert conv.msg_events[1] == [EVENT_LABELS[17]]
    # outline mentions the choice and the action
    outline = "\n".join(conv.outline)
    assert QUERY_LABELS[4] in outline
    assert EVENT_LABELS[17] in outline


def test_msg_flow_context_renders_per_line_and_overview():
    flw1, fli1 = _sample_sections()
    flow = parse_flow_sections(flw1, fli1)
    ctx = MsgFlowContext(flow, msg_label=lambda i: f'[msg {400 + i}] "text {i}"')

    line_ctx = ctx.context_for_message(1)
    assert "dialogue flow #338" in line_ctx          # 0x152 = 338
    assert "line 2 of 3" in line_ctx
    assert QUERY_LABELS[4] in line_ctx
    assert EVENT_LABELS[17] in line_ctx

    assert ctx.context_for_message(99) is None

    overview = ctx.overview_for_messages([0])
    assert "Dialogue flow #338" in overview
    assert '[msg 400]' in overview and '[msg 402]' in overview


class _FakeBmg:
    def __init__(self, other_sections, messages=(), trailing_data=b"", endianness=">"):
        self.other_sections = other_sections
        self.messages = list(messages)
        self.trailing_data = trailing_data
        self.endianness = endianness


class _FakeMsg:
    def __init__(self, msg_id, text):
        self.id = msg_id
        self.parts = [text]


def test_flow_context_from_bmg_and_missing_sections():
    flw1, fli1 = _sample_sections()
    assert flow_context_from_bmg(_FakeBmg({"FLW1": flw1, "FLI1": fli1})) is not None
    assert flow_context_from_bmg(_FakeBmg({})) is None
    assert flow_context_from_bmg(object()) is None


def test_flow_context_recovers_truncated_fli1_from_bmg_trailing_data():
    flw1, fli1 = _sample_sections()
    # Retail zel_00.bmg declares alignment bytes at the end of FLI1 which are
    # not physically present. BMGFile therefore preserves the section here.
    bmg = _FakeBmg({"FLW1": flw1}, trailing_data=fli1)
    ctx = flow_context_from_bmg(bmg)
    assert ctx is not None
    assert "dialogue flow #338" in ctx.context_for_message(1)


class _MockMW:
    def __init__(self):
        self.data_store = self
        self.show_multiple_spaces_as_dots = False
        self.default_tag_mappings = {}
        self.newline_display_symbol = "↵"


@pytest.fixture
def bmg_rules(qapp):
    from plugins.zelda_bmg.rules import GameRules
    return GameRules(_MockMW())


def test_rules_flow_hooks_via_last_loaded_bmg(bmg_rules):
    flw1, fli1 = _sample_sections()
    messages = [
        _FakeMsg(402, "What are you doing?!"),
        _FakeMsg(403, "Yes, {color:red}exactly{color:white}."),
        _FakeMsg(404, "No way."),
    ]
    bmg_rules.last_loaded_bmg = _FakeBmg({"FLW1": flw1, "FLI1": fli1}, messages)

    line_ctx = bmg_rules.get_ai_flow_context_for_string(0, 1)
    assert line_ctx is not None
    assert "line 2 of 3" in line_ctx

    overview = bmg_rules.get_ai_flow_overview(0, [0, 1, 2])
    assert overview is not None
    # message labels include real IDs and tag-stripped text snippets
    assert '[msg 402] "What are you doing?!"' in overview
    assert '[msg 403] "Yes, exactly."' in overview
    assert EVENT_LABELS[17] in overview


def test_rules_flow_hooks_absent_data(bmg_rules):
    bmg_rules.last_loaded_bmg = None
    assert bmg_rules.get_ai_flow_context_for_string(0, 1) is None
    assert bmg_rules.get_ai_flow_overview(0, [0]) is None


def test_base_rules_flow_hooks_default_none(qapp):
    from plugins.base_game_rules import BaseGameRules
    rules = BaseGameRules(main_window_ref=None)
    assert rules.get_ai_flow_context_for_string(0, 0) is None
    assert rules.get_ai_flow_overview(0, [0]) is None


def test_actor_map_annotates_flow_context():
    flw1, fli1 = _sample_sections()
    flow = parse_flow_sections(flw1, fli1)

    # character name wins over the raw actor code
    ctx = MsgFlowContext(flow, actor_map={0x152: {"actors": ["d_a_npc_kkri"], "character": "Kili"}})
    assert "NPC: Kili" in ctx.context_for_message(0)
    assert "NPC: Kili" in ctx.overview_for_messages([0])

    # without a character name the game actor code is still shown
    ctx2 = MsgFlowContext(flow, actor_map={0x152: {"actors": ["d_a_npc_kkri"], "character": ""}})
    assert "game actor: d_a_npc_kkri" in ctx2.context_for_message(0)


def test_actor_map_requires_explicit_bmg_scope_before_runtime_use():
    actor_map = {
        4: {"actors": ["d_a_npc_kolin"], "character": "Colin"},
        5: {
            "actors": ["d_a_npc_talo"], "character": "Talo",
            "bmg_files": ["zel_01.bmg"],
        },
    }
    assert actor_map_for_bmg(actor_map, "zel_01.bmg") == {5: actor_map[5]}
    assert actor_map_for_bmg(actor_map, "zel_02.bmg") == {}
    assert actor_map_for_bmg(actor_map, None) == {}


def test_flow_actors_json_loads_and_matches_sources():
    from plugins.zelda_bmg.msg_flow import load_flow_actor_map
    actor_map = load_flow_actor_map()
    assert actor_map, "flow_actors.json missing or empty"
    # spot-check IDs hardcoded in dusklight actor sources
    assert "d_a_npc_ks" in actor_map[116]["actors"]      # msg_flow.init(actor, 116, ...)
    assert "d_a_npc_ks" in actor_map[2015]["actors"]     # msg_flow.init(actor, 2015, ...)
    for entry in actor_map.values():
        assert isinstance(entry.get("actors"), list)


def test_flow_context_reaches_ai_translation_prompt(qapp):
    """End to end: the FLW1 conversation graph must land in the AI prompt."""
    from unittest.mock import MagicMock
    from handlers.translation.ai_prompt_composer import AIPromptComposer
    from plugins.zelda_bmg.rules import GameRules

    mw = MagicMock()
    mw.data_store = mw
    main_handler = MagicMock()
    main_handler.mw = mw
    composer = AIPromptComposer(main_handler)
    composer.main_handler._glossary_manager = MagicMock()
    composer.main_handler._glossary_manager.get_relevant_terms.return_value = []

    rules = GameRules(None)
    flw1, fli1 = _sample_sections()
    rules.last_loaded_bmg = _FakeBmg({"FLW1": flw1, "FLI1": fli1}, [
        _FakeMsg(402, "What are you doing?!"),
        _FakeMsg(403, "Yes, exactly."),
        _FakeMsg(404, "No way."),
    ])
    mw.current_game_rules = rules
    mw.default_tag_mappings = {}
    mw.project_manager = None
    mw.block_to_project_file_map = {}

    source_items = [{"id": 1, "text": "Yes, exactly."}]
    _, user_content, _ = composer.compose_batch_request(
        "Translate into {target_lang}.",
        source_items, source_items,
        block_idx=0, mode_description="translation",
    )

    # per-item flow context
    assert '"flow_context"' in user_content
    assert "line 2 of 3" in user_content
    # chunk-level conversation outline with real message IDs and conditions
    assert '"dialogue_flow"' in user_content
    assert "[msg 402]" in user_content
    assert QUERY_LABELS[4] in user_content
    assert EVENT_LABELS[17] in user_content
    # the model is told how to use it
    assert "DIALOGUE FLOW" in user_content


def test_flow_context_reaches_single_and_variation_prompts(qapp):
    from unittest.mock import MagicMock
    from handlers.translation.ai_prompt_composer import AIPromptComposer
    from plugins.zelda_bmg.rules import GameRules

    mw = MagicMock()
    mw.data_store = mw
    mw.data_store.data = [["Question?", "Yes, exactly.", "No way."]]
    mw.default_tag_mappings = {}
    mw.project_manager = None
    mw.block_to_project_file_map = {}
    main_handler = MagicMock()
    main_handler.mw = mw
    main_handler._glossary_manager.get_relevant_terms.return_value = []
    composer = AIPromptComposer(main_handler)

    rules = GameRules(None)
    flw1, fli1 = _sample_sections()
    rules.last_loaded_bmg = _FakeBmg({"FLW1": flw1, "FLI1": fli1}, [
        _FakeMsg(402, "Question?"),
        _FakeMsg(403, "Yes, exactly."),
        _FakeMsg(404, "No way."),
    ])
    mw.current_game_rules = rules

    _, single_user = composer.compose_messages(
        "Translate into {target_lang}.", "Yes, exactly.",
        block_idx=0, string_idx=1, expected_lines=1,
        mode_description="translation", request_type="translation",
    )
    _, variation_user = composer.compose_messages(
        "Translate into {target_lang}.", "Yes, exactly.",
        block_idx=0, string_idx=1, expected_lines=1,
        mode_description="variations", request_type="variation_list",
        current_translation="Так, саме так.",
    )

    for prompt in (single_user, variation_user):
        assert "Dialogue Flow (from game data)" in prompt
        assert "line 2 of 3" in prompt
        assert "[msg 402]" in prompt
        assert "owning NPC/actor" in prompt
