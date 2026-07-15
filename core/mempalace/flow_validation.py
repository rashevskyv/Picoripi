"""Validate marked-script alignment against TP's objective BMG flow graphs."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from plugins.zelda_bmg.msg_flow import (
    NODE_BRANCH,
    NODE_MESSAGE,
    _branch_arity,
    load_flow_actor_map,
    parse_flow_sections,
)


def _raw_fli1(bmg: Any) -> bytes | None:
    sections = getattr(bmg, "other_sections", {}) or {}
    fli1 = sections.get("FLI1")
    if fli1:
        return fli1
    trailing = getattr(bmg, "trailing_data", b"")
    if isinstance(trailing, (bytes, bytearray)):
        offset = trailing.find(b"FLI1")
        if offset >= 0:
            return bytes(trailing[offset:])
    return None


def _first_message_targets(flow, node_index: int, visited: set[int]) -> set[int]:
    if node_index == 0xFFFF or node_index >= len(flow.nodes) or node_index in visited:
        return set()
    visited = visited | {node_index}
    node = flow.nodes[node_index]
    if node.kind == NODE_MESSAGE:
        return {node.arg}
    if node.kind == NODE_BRANCH:
        result: set[int] = set()
        for option in range(_branch_arity(node)):
            table_index = node.next_idx + option
            if table_index < len(flow.branch_table):
                result.update(_first_message_targets(
                    flow, flow.branch_table[table_index], visited
                ))
        return result
    return _first_message_targets(flow, node.next_idx, visited)


def validate_flow_alignment(
    alignment_report: dict,
    bmg_blocks: Iterable[tuple[str, Any]],
    *,
    actor_map: dict[int, dict] | None = None,
) -> dict:
    """Compare supported text relations with FLW1/FLI1 graph evidence.

    Flow-row coverage is diagnostic, not the 95% acceptance metric: a walkthrough
    need not quote every optional game flow. The acceptance metric remains marked
    dialogue token coverage from the alignment report.
    """
    relations: dict[tuple[int, int], list[dict]] = defaultdict(list)
    all_relation_nodes: set[int] = set()
    for relation in alignment_report.get("relations", ()):
        key = (int(relation["game_block_id"]), int(relation["string_index"]))
        relations[key].append(relation)
        all_relation_nodes.add(int(relation["dialogue_node_id"]))

    actors = actor_map if actor_map is not None else load_flow_actor_map()
    flow_resources: dict[int, set[str]] = defaultdict(set)
    flow_backed_nodes: set[int] = set()
    totals = Counter()
    blocks = []

    for block_index, (block_name, bmg) in enumerate(bmg_blocks):
        sections = getattr(bmg, "other_sections", {}) or {}
        flow = parse_flow_sections(
            sections.get("FLW1"),
            _raw_fli1(bmg),
            getattr(bmg, "endianness", ">"),
        )
        if flow is None or not flow.flows:
            continue

        invalid_messages = sum(
            node.kind == NODE_MESSAGE and node.arg >= len(getattr(bmg, "messages", ()))
            for node in flow.nodes
        )
        invalid_next_nodes = sum(
            node.kind != NODE_BRANCH
            and node.next_idx != 0xFFFF
            and node.next_idx >= len(flow.nodes)
            for node in flow.nodes
        )
        invalid_branch_targets = sum(
            target != 0xFFFF and target >= len(flow.nodes)
            for target in flow.branch_table
        )

        conversation_rows: list[set[int]] = []
        flow_rows: set[int] = set()
        from plugins.zelda_bmg.msg_flow import build_conversation

        for flow_id in sorted(flow.flows):
            flow_resources[flow_id].add(block_name)
            rows = set(build_conversation(flow, flow_id).msg_indices)
            if rows:
                conversation_rows.append(rows)
                flow_rows.update(rows)

        mapped_rows = {
            row for row in flow_rows if relations.get((block_index, row))
        }
        for row in mapped_rows:
            flow_backed_nodes.update(
                int(relation["dialogue_node_id"])
                for relation in relations[(block_index, row)]
            )

        conversations_any = conversations_80 = conversations_all = 0
        for rows in conversation_rows:
            mapped_count = len(rows & mapped_rows)
            conversations_any += mapped_count > 0
            conversations_80 += mapped_count / len(rows) >= 0.8
            conversations_all += mapped_count == len(rows)

        edges: set[tuple[int, int]] = set()
        for node in flow.nodes:
            if node.kind == NODE_MESSAGE:
                edges.update(
                    (node.arg, target)
                    for target in _first_message_targets(flow, node.next_idx, set())
                    if target != node.arg
                )
        mapped_edges = order_compatible = close_order = 0
        for source, target in edges:
            left = relations.get((block_index, source), ())
            right = relations.get((block_index, target), ())
            if not left or not right:
                continue
            mapped_edges += 1
            gaps = [
                int(after["source_line"]) - int(before["source_line"])
                for before in left
                for after in right
                if before.get("source_line") is not None
                and after.get("source_line") is not None
                and int(after["source_line"]) >= int(before["source_line"])
            ]
            if gaps:
                order_compatible += 1
                close_order += min(gaps) <= 80

        row = {
            "block": block_name,
            "flows": len(conversation_rows),
            "flow_rows": len(flow_rows),
            "mapped_flow_rows": len(mapped_rows),
            "mapped_flow_percent": round(100 * len(mapped_rows) / len(flow_rows), 3)
            if flow_rows else 100.0,
            "conversations_with_mapping": conversations_any,
            "conversations_at_least_80_percent": conversations_80,
            "conversations_fully_mapped": conversations_all,
            "flow_edges": len(edges),
            "mapped_edges": mapped_edges,
            "order_compatible_edges": order_compatible,
            "close_order_edges": close_order,
            "invalid_message_indices": invalid_messages,
            "invalid_next_nodes": invalid_next_nodes,
            "invalid_branch_targets": invalid_branch_targets,
        }
        blocks.append(row)
        for key, value in row.items():
            if isinstance(value, int):
                totals[key] += value

    duplicate_flow_ids = {
        flow_id: sorted(resources)
        for flow_id, resources in flow_resources.items()
        if len(resources) > 1
    }
    unscoped_actor_ids = {
        flow_id for flow_id, entry in actors.items()
        if not entry.get("bmg") and not entry.get("bmg_files")
    }
    unsafe_actor_ids = unscoped_actor_ids & set(duplicate_flow_ids)
    marked = alignment_report.get("eligible_marked_dialogue", {})
    result = {
        "acceptance": {
            "eligible_marked_dialogue_coverage": marked.get(
                "supported_relation_coverage", 0.0
            ),
            "minimum_required": 95.0,
            "passed": float(marked.get("supported_relation_coverage", 0.0)) >= 95.0,
        },
        "blocks": blocks,
        "totals": dict(totals),
        "flow_backed_dialogue_nodes": len(flow_backed_nodes),
        "all_related_dialogue_nodes": len(all_relation_nodes),
        "flow_backed_node_percent": round(
            100 * len(flow_backed_nodes) / len(all_relation_nodes), 3
        ) if all_relation_nodes else 100.0,
        "actor_scope_audit": {
            "actor_map_entries": len(actors),
            "flow_ids_reused_across_bmgs": len(duplicate_flow_ids),
            "unscoped_actor_entries": len(unscoped_actor_ids),
            "unsafe_unscoped_reused_ids": len(unsafe_actor_ids),
            "runtime_policy": "Only BMG-scoped actor entries may enter AI prompts.",
        },
        "integrity_passed": not any(
            totals[key]
            for key in (
                "invalid_message_indices", "invalid_next_nodes",
                "invalid_branch_targets",
            )
        ),
        "order_diagnostic_note": (
            "Order compatibility is diagnostic only: alternate branches, jump-to-flow "
            "events and walkthrough section order can legitimately differ."
        ),
    }
    if totals["flow_rows"]:
        result["totals"]["mapped_flow_percent"] = round(
            100 * totals["mapped_flow_rows"] / totals["flow_rows"], 3
        )
    if totals["mapped_edges"]:
        result["totals"]["order_compatible_percent"] = round(
            100 * totals["order_compatible_edges"] / totals["mapped_edges"], 3
        )
    return result
