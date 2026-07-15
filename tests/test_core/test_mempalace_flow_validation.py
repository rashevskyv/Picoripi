import struct

from core.mempalace.flow_validation import validate_flow_alignment
from plugins.zelda_bmg.msg_flow import NODE_MESSAGE


class _Bmg:
    endianness = ">"

    def __init__(self):
        nodes = [
            struct.pack(">BBHHH", NODE_MESSAGE, 0, 0, 1, 0),
            struct.pack(">BBHHH", NODE_MESSAGE, 0, 1, 0xFFFF, 0),
        ]
        body = struct.pack(">HH", 2, 0) + b"\0" * 4 + b"".join(nodes)
        flw1 = struct.pack(">4sI", b"FLW1", 8 + len(body)) + body
        fli_body = struct.pack(">H", 1) + b"\0" * 6 + struct.pack(">IHH", 4 << 16, 0, 0)
        fli1 = struct.pack(">4sI", b"FLI1", 8 + len(fli_body)) + fli_body
        self.other_sections = {"FLW1": flw1, "FLI1": fli1}
        self.trailing_data = b""
        self.messages = [object(), object()]


def test_flow_validation_reports_acceptance_integrity_and_actor_scope():
    alignment = {
        "eligible_marked_dialogue": {"supported_relation_coverage": 97.5},
        "relations": [
            {
                "game_block_id": "0", "string_index": 0,
                "dialogue_node_id": 10, "source_line": 100,
            },
            {
                "game_block_id": "0", "string_index": 1,
                "dialogue_node_id": 11, "source_line": 101,
            },
        ],
    }
    report = validate_flow_alignment(
        alignment,
        [("zel_01", _Bmg()), ("zel_02", _Bmg())],
        actor_map={4: {"actors": ["d_a_npc_kolin"], "character": ""}},
    )
    assert report["acceptance"]["passed"] is True
    assert report["integrity_passed"] is True
    assert report["totals"]["flow_rows"] == 4
    assert report["totals"]["mapped_flow_rows"] == 2
    assert report["actor_scope_audit"]["flow_ids_reused_across_bmgs"] == 1
    assert report["actor_scope_audit"]["unsafe_unscoped_reused_ids"] == 1
