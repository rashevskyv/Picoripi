"""Twilight Princess message flow (FLW1/FLI1) parsing for AI translation context.

TP stores NPC conversation graphs alongside the message text inside the same
BMG file (dusklight: src/d/d_msg_flow.cpp, dMsgFlow_c):

- FLW1: a table of 8-byte nodes. Node types (d_msg_flow.h):
    1 = message  (msg_index -> INF1 entry / string index, next_node)
    2 = branch   (query_idx -> one of 53 condition functions, param,
                  next_node = base offset into the u16 branch-target table)
    3 = event    (event_idx -> one of 43 game actions, next_node)
- FLI1: 8-byte entries mapping a flow ID (used by NPC actors) to the entry
  node of its conversation graph.

This module parses those sections and renders compact, English conversation
outlines used as extra context in AI translation prompts.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import struct

# Condition labels extracted from the debug strings of dMsgFlow_c::query001..053
# (index = query_idx used by branch nodes, i.e. mQueryList[query_idx]).
QUERY_LABELS: Dict[int, str] = {
    0: "Story Flag Check",
    1: "Player Appearance Check (0=human, 1=wolf, 2=riding)",
    2: "Random variation",
    3: "Rupee Check (has less than N rupees)",
    4: "Player Choice (2 options)",
    5: "Player Choice (3 options)",
    6: "Conversation Distance Check",
    7: "Sword Tutorial Step Check",
    8: "Sword Tutorial Success Check",
    9: "Sword Tutorial Count Check",
    10: "Temporary Flag Check",
    11: "Treasure Chest Opened Check",
    12: "Save Switch Check",
    13: "Save Item Check",
    14: "Dungeon Switch Check",
    15: "Dungeon Item Check",
    16: "Zone Switch Check",
    17: "Zone Item Check",
    18: "One-Zone Switch Check",
    19: "One-Zone Item Check",
    20: "Equipment Check (player has item equipped)",
    21: "Item Obtained Check",
    22: "Bomb Bag Count Check",
    23: "Arrow Count Check",
    24: "Empty Bottle Count Check",
    25: "Shop Conversation Check",
    26: "Light Drop (Tears of Light) Check",
    27: "Goat-Herding Time Check",
    28: "Lantern Contents Check",
    29: "Cash Register Check",
    30: "Runaway Goats Remaining Check",
    31: "Player Health Check",
    32: "Holding Lantern Check",
    33: "Time of Day Check",
    34: "Magic Check",
    35: "Player Choice (2 options, B cancels)",
    36: "Player Choice (3 options, B cancels)",
    37: "Bomb Bag Contents Check",
    38: "Normal Bombs at Max Check",
    39: "Bomb Count Check",
    40: "Water Bombs at Max Check",
    41: "Transform Range Check",
    42: "Bugs at Max Check",
    43: "Warp Area Available Check",
    44: "Captured Insect Check",
    45: "Insect-in-Bottle Check",
    46: "Landmines at Max Check",
    47: "Letter Count Check",
    48: "Collected Poe Souls Count",
    49: "Donation Total Amount",
    50: "Balloon Minigame Score",
    51: "Player In Water Check",
    52: "Wearing Iron Boots Check",
}

# Action labels from dMsgFlow_c::event000..042 (index = event_idx).
EVENT_LABELS: Dict[int, str] = {
    0: "set story flag",
    2: "give rupees",
    3: "take rupees",
    4: "restore hearts",
    5: "take hearts",
    6: "restore magic",
    7: "take magic",
    8: "start cutscene/event",
    9: "jump to another dialogue flow",
    10: "set temporary flag",
    11: "clear temporary flag",
    12: "open door",
    14: "set switch",
    15: "clear switch",
    16: "open item selection",
    17: "give item",
    18: "event direction",
    20: "warp player",
    21: "wait",
    22: "refill lantern",
    23: "fill bottle",
    24: "mark item sold out",
    25: "set cash register",
    26: "unattended-tent purchase",
    27: "refill bombs",
    28: "bomb purchase",
    29: "horizontal choice select",
    30: "refill arrows",
    31: "return rental bomb bag",
    32: "fade in",
    33: "fade out",
    34: "give trade item",
    35: "remove item",
    36: "set save bit",
    37: "clear save bit",
    38: "receive mail",
    39: "resistance map scene",
    40: "empty bottle",
    41: "donation",
}

# Branch arity: how many consecutive entries of the branch-target table a
# branch node consumes. Most queries are yes/no (2); a few return 3 values.
_QUERY_ARITY: Dict[int, int] = {
    1: 3,   # appearance: human / wolf / riding
    5: 3,   # 3-way choice
    36: 3,  # 3-way choice with B
}
_RANDOM_QUERY = 2  # arity = param

NODE_MESSAGE = 1
NODE_BRANCH = 2
NODE_EVENT = 3


@dataclass
class FlowNode:
    """One 8-byte FLW1 node."""
    kind: int
    # message: msg_index; branch: query_idx; event: event_idx
    arg: int = 0
    # branch: param
    param: int = 0
    # message/event: next node; branch: base offset into branch table
    next_idx: int = 0xFFFF


@dataclass
class FlowData:
    nodes: List[FlowNode] = field(default_factory=list)
    branch_table: List[int] = field(default_factory=list)
    flows: Dict[int, int] = field(default_factory=dict)  # flow_id -> entry node


def parse_flow_sections(flw1: Optional[bytes], fli1: Optional[bytes],
                        endianness: str = ">") -> Optional[FlowData]:
    """Parse raw FLW1/FLI1 section bytes (including their 8-byte headers)."""
    if not flw1 or len(flw1) < 0x10:
        return None
    se = endianness if endianness in (">", "<") else ">"

    data = FlowData()
    num_nodes, num_branches = struct.unpack_from(se + "HH", flw1, 8)
    nodes_start = 0x10
    nodes_end = nodes_start + num_nodes * 8
    if nodes_end > len(flw1):
        return None

    for i in range(num_nodes):
        off = nodes_start + i * 8
        kind = flw1[off]
        if kind == NODE_BRANCH:
            _, _, query_idx, param, nxt = struct.unpack_from(se + "BBHHH", flw1, off)
            data.nodes.append(FlowNode(kind=NODE_BRANCH, arg=query_idx, param=param, next_idx=nxt))
        elif kind == NODE_EVENT:
            _, event_idx, nxt = struct.unpack_from(se + "BBH", flw1, off)
            data.nodes.append(FlowNode(kind=NODE_EVENT, arg=event_idx, next_idx=nxt))
        else:
            _, _, msg_index, nxt, _ = struct.unpack_from(se + "BBHHH", flw1, off)
            data.nodes.append(FlowNode(kind=kind, arg=msg_index, next_idx=nxt))

    # The u16 branch-target table follows the node table. FLW1 often contains
    # non-zero alignment bytes after it, so use the explicit header count.
    table_bytes = flw1[nodes_end:nodes_end + num_branches * 2]
    count = min(num_branches, len(table_bytes) // 2)
    if count:
        data.branch_table = list(struct.unpack(f"{se}{count}H", table_bytes[:count * 2]))

    if fli1 and len(fli1) >= 0x10:
        num_flows = struct.unpack_from(se + "H", fli1, 8)[0]
        for i in range(num_flows):
            off = 0x10 + i * 8
            if off + 8 > len(fli1):
                break
            word, node_idx = struct.unpack_from(se + "IH", fli1, off)
            data.flows[word >> 16] = node_idx

    return data


@dataclass
class Conversation:
    flow_id: int
    # ordered outline lines (indented, human readable)
    outline: List[str] = field(default_factory=list)
    # message string indices in walk order (unique)
    msg_indices: List[int] = field(default_factory=list)
    # msg_index -> list of condition strings on the path to that message
    msg_conditions: Dict[int, List[str]] = field(default_factory=dict)
    # msg_index -> list of event strings directly following the message
    msg_events: Dict[int, List[str]] = field(default_factory=dict)


def _branch_arity(node: FlowNode) -> int:
    if node.arg == _RANDOM_QUERY:
        return max(2, min(int(node.param) or 2, 8))
    return _QUERY_ARITY.get(node.arg, 2)


def _query_label(query_idx: int) -> str:
    return QUERY_LABELS.get(query_idx, f"condition #{query_idx}")


def _event_label(event_idx: int) -> str:
    return EVENT_LABELS.get(event_idx, f"action #{event_idx}")


def build_conversation(flow: FlowData, flow_id: int, msg_label=None,
                       max_nodes: int = 200) -> Conversation:
    """Walk one conversation graph into a readable outline.

    msg_label: optional callable msg_index -> str used for outline lines
    (e.g. injecting message IDs or text snippets).
    """
    conv = Conversation(flow_id=flow_id)
    entry = flow.flows.get(flow_id, 0xFFFF)

    def label_for(msg_index: int) -> str:
        if msg_label:
            try:
                text = msg_label(msg_index)
                if text:
                    return text
            except Exception:
                pass
        return f"line #{msg_index}"

    visited: Set[int] = set()
    steps = 0

    def walk(node_idx: int, depth: int, conditions: List[str]):
        nonlocal steps
        indent = "  " * depth
        while node_idx != 0xFFFF and steps < max_nodes:
            if node_idx >= len(flow.nodes):
                return
            if node_idx in visited:
                conv.outline.append(f"{indent}-> (continues at an earlier step)")
                return
            visited.add(node_idx)
            steps += 1
            node = flow.nodes[node_idx]

            if node.kind == NODE_MESSAGE:
                msg_index = node.arg
                conv.outline.append(f"{indent}{label_for(msg_index)}")
                if msg_index not in conv.msg_indices:
                    conv.msg_indices.append(msg_index)
                    if conditions:
                        conv.msg_conditions[msg_index] = list(conditions)
                node_idx = node.next_idx
            elif node.kind == NODE_EVENT:
                label = _event_label(node.arg)
                conv.outline.append(f"{indent}(game action: {label})")
                if conv.msg_indices:
                    conv.msg_events.setdefault(conv.msg_indices[-1], []).append(label)
                node_idx = node.next_idx
            elif node.kind == NODE_BRANCH:
                q_label = _query_label(node.arg)
                arity = _branch_arity(node)
                conv.outline.append(f"{indent}[{q_label}]")
                base = node.next_idx
                for opt in range(arity):
                    t_idx = base + opt
                    if t_idx >= len(flow.branch_table):
                        break
                    target = flow.branch_table[t_idx]
                    conv.outline.append(f"{indent}  option {opt + 1}:")
                    walk(target, depth + 2, conditions + [f"{q_label} = option {opt + 1}"])
                return
            else:
                node_idx = node.next_idx

    walk(entry, 0, [])
    return conv


class MsgFlowContext:
    """Per-BMG-file flow context: conversations + per-message renderings.

    actor_map: optional dict flow_id -> {"actors": [...], "character": str}
    (from flow_actors.json) naming the NPC that runs each conversation.
    """

    def __init__(self, flow: Optional[FlowData], msg_label=None,
                 actor_map: Optional[Dict[int, Dict[str, Any]]] = None):
        self.conversations: List[Conversation] = []
        self._by_msg: Dict[int, List[Conversation]] = {}
        self._actor_map = actor_map or {}
        if flow:
            for flow_id in sorted(flow.flows):
                conv = build_conversation(flow, flow_id, msg_label=msg_label)
                if conv.msg_indices:
                    self.conversations.append(conv)
                    for m in conv.msg_indices:
                        self._by_msg.setdefault(m, []).append(conv)

    def _actor_note(self, flow_id: int) -> str:
        entry = self._actor_map.get(flow_id)
        if not entry:
            return ""
        character = str(entry.get("character") or "").strip()
        if character:
            return f", NPC: {character}"
        actors = entry.get("actors") or []
        if actors:
            return f", game actor: {', '.join(str(a) for a in actors[:2])}"
        return ""

    def context_for_message(self, msg_index: int) -> Optional[str]:
        """Compact per-line context for the AI prompt."""
        convs = self._by_msg.get(msg_index)
        if not convs:
            return None
        parts: List[str] = []
        for conv in convs[:2]:
            pos = conv.msg_indices.index(msg_index) + 1
            bits = [f"dialogue flow #{conv.flow_id}{self._actor_note(conv.flow_id)}: "
                    f"line {pos} of {len(conv.msg_indices)}"]
            conds = conv.msg_conditions.get(msg_index)
            if conds:
                bits.append("shown when: " + "; ".join(conds[-2:]))
            events = conv.msg_events.get(msg_index)
            if events:
                bits.append("followed by: " + ", ".join(events[:3]))
            parts.append("; ".join(bits))
        return " | ".join(parts)

    def overview_for_messages(self, msg_indices, max_conversations: int = 4,
                              max_lines: int = 60) -> Optional[str]:
        """Readable outlines of every conversation touching the given lines."""
        wanted = set(msg_indices)
        picked: List[Conversation] = []
        for conv in self.conversations:
            if wanted.intersection(conv.msg_indices):
                picked.append(conv)
            if len(picked) >= max_conversations:
                break
        if not picked:
            return None

        blocks: List[str] = []
        for conv in picked:
            lines = conv.outline[:max_lines]
            body = "\n".join("  " + ln for ln in lines)
            if len(conv.outline) > max_lines:
                body += "\n  ..."
            blocks.append(f"Dialogue flow #{conv.flow_id}{self._actor_note(conv.flow_id)} "
                          f"(in-game conversation order):\n{body}")
        return "\n\n".join(blocks)


def load_flow_actor_map(plugin_dir: Optional[str] = None) -> Dict[int, Dict[str, Any]]:
    """Load flow_actors.json (flow_id -> owning game actor / character name).

    The file is generated from the game sources (hardcoded msg_flow.init IDs in
    src/d/actor/*.cpp) and is user-editable: filling "character" gives the AI
    a real speaker name for the whole conversation.
    """
    import json
    import os
    if plugin_dir is None:
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(plugin_dir, "flow_actors.json")
    result: Dict[int, Dict[str, Any]] = {}
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        for key, entry in (doc.get("flows") or {}).items():
            try:
                result[int(key, 0)] = entry
            except (TypeError, ValueError):
                continue
    except Exception:
        pass
    return result


def actor_map_for_bmg(actor_map: Dict[int, Dict[str, Any]],
                      resource_name: Optional[str]) -> Dict[int, Dict[str, Any]]:
    """Return only actor evidence explicitly scoped to one BMG resource.

    Flow IDs are local to a BMG resource: the same numeric ID occurs in several
    zel_XX files. Older extracted entries contain only a flow ID and actor class;
    applying them globally can therefore name the wrong NPC. Such legacy entries
    remain useful research evidence but are deliberately excluded from prompts
    until a stage/ACTR source records ``bmg_files`` (or ``bmg``) explicitly.
    """
    if not resource_name:
        return {}
    wanted = str(resource_name).replace("\\", "/").rsplit("/", 1)[-1].casefold()
    wanted_stem = wanted.rsplit(".", 1)[0]
    scoped: Dict[int, Dict[str, Any]] = {}
    for flow_id, entry in actor_map.items():
        raw_scopes = entry.get("bmg_files")
        if raw_scopes is None:
            raw_scope = entry.get("bmg")
            raw_scopes = [raw_scope] if raw_scope else []
        if isinstance(raw_scopes, str):
            raw_scopes = [raw_scopes]
        scopes = {
            str(scope).replace("\\", "/").rsplit("/", 1)[-1].casefold()
            for scope in (raw_scopes or [])
        }
        stems = {scope.rsplit(".", 1)[0] for scope in scopes}
        if wanted in scopes or wanted_stem in stems:
            scoped[flow_id] = entry
    return scoped


def flow_context_from_bmg(bmg: Any, msg_label=None,
                          actor_map: Optional[Dict[int, Dict[str, Any]]] = None) -> Optional[MsgFlowContext]:
    """Build MsgFlowContext from a loaded bmg_tool.BMGFile (uses the raw
    FLW1/FLI1 sections preserved in other_sections)."""
    sections = getattr(bmg, "other_sections", None)
    if not isinstance(sections, dict):
        return None
    flw1 = sections.get("FLW1")
    fli1 = sections.get("FLI1")
    # Some retail TP files omit the final alignment bytes declared by FLI1.
    # BMGFile intentionally preserves such a truncated last section as trailing
    # data to keep binary round-trips exact, so recover it here for read-only
    # flow analysis without changing the repacked file.
    if not fli1:
        trailing = getattr(bmg, "trailing_data", b"")
        if isinstance(trailing, (bytes, bytearray)):
            pos = trailing.find(b"FLI1")
            if pos >= 0:
                fli1 = bytes(trailing[pos:])
    flow = parse_flow_sections(flw1, fli1, getattr(bmg, "endianness", ">"))
    if flow is None or not flow.flows:
        return None
    ctx = MsgFlowContext(flow, msg_label=msg_label, actor_map=actor_map)
    return ctx if ctx.conversations else None
