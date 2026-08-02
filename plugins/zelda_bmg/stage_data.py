"""Twilight Princess stage-data extraction for AI translation context.

This is game-specific and lives entirely inside the zelda_bmg plugin. It reads
the retail ``res/Stage/<STAGE>/*.arc`` archives (Yaz0+RARC, via the project's
generic ``RarcContainer``) and pulls out the per-scene "who speaks where"
evidence that plain BMG text + FLW1/FLI1 flow (see ``msg_flow.py``) cannot give:

- ``dzs/stage.dzs`` -> **STAG** chunk: ``mMsgGroup`` = which ``bmgres<N>.arc``
  this stage loads. This is the stage->BMG link that lets local flow IDs be
  scoped to a concrete message resource. Also ``mStageTitleNo`` (title msg id).
- ``dzs/stage.dzs`` / ``dzr/room.dzr`` -> **SCLS** chunk: room/stage exits
  (adjacency, for chronological orientation).
- ``dzr/room.dzr`` (+ room ``.dzs``) -> **ACTR/ACTn/TGOB** (actors, 0x20) and
  **SCOB/TGSC/TGDR** (tag+scale object-actors, 0x24): which entities are
  physically placed in which room = location roster.
- ``evt/event_list.dat`` -> named events and their participating staff/actors
  (the cast of each scripted scene / cutscene).

Binary layouts are from dusklight (``include/d/d_stage.h``,
``include/d/d_event_data.h``, chunk tables in ``src/d/d_stage.cpp``):

    DZX (DZR/DZS): u32 num_chunks, then num_chunks * (char tag[4], u32 count,
                   u32 offset). All big-endian.
    ACTR-family element (0x20): char name[8]; u32 parameters; cXyz pos;
                                csXyz angle @0x18 (angle.x = dialogue flow node)
    SCOB/TGSC element   (0x24): char name[8]; u32 parameters; ... + scale
    SCLS element        (0x0D): char stage[8]; u8 spawn; s8 room; ...
    STAG (in stage.dzs, 0x3C): ... u8 mMsgGroup @0x28; u16 mStageTitleNo @0x2A
    event_list.dat header (0x40): 7 (offset,count) BE pairs -> Event/Staff/Cut/
                   Data/FData/IData/SData chunks.
    Event element (0xB0): char name[32]; ...; s32 mStaff[20] @0x2C; s32 mNStaff @0x7C
    Staff element (0x50): char name[8] @0x00; ...

The offline entry point (``main``) writes ``stage_scene_data.json`` next to this
module; the runtime side reads it via ``load_stage_scene_data``.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import os
import re
import struct

# --- chunk tag classification -------------------------------------------------

# Actors: base "ACTR", layer tags "ACT0".."ACT9"/"ACTa"/"ACTb" (layerNo + '0'
# or 'W'), and "TGOB" (also routed through dStage_actorInit).
_ACTOR_TAG_RE = re.compile(r"^(ACTR|TGOB|ACT[0-9ab])$")
# Tag+scale object-actors (signs, statues, gossip stones, doors...).
_TGSC_TAG_RE = re.compile(r"^(SCOB|TGSC|TGDR|SCO[0-9ab])$")

_ACTOR_STRIDE = 0x20
# angle.x inside fopAcM_prmBase_class: the NPC's dialogue flow node number.
_ACTOR_ANGLE_X_OFF = 0x18
_TGSC_STRIDE = 0x24
_SCLS_STRIDE = 0x0D
_STAG_MSGGROUP_OFF = 0x28
_STAG_TITLE_OFF = 0x2A


def _cstr(data: bytes, off: int, n: int) -> str:
    raw = data[off:off + n]
    return raw.split(b"\x00", 1)[0].decode("shift_jis", "replace")


def parse_dzx_chunks(data: bytes) -> List[Tuple[str, int, int]]:
    """Return [(tag, count, offset)] for a DZR/DZS blob (big-endian)."""
    if len(data) < 4:
        return []
    num = struct.unpack_from(">I", data, 0)[0]
    if num > 0x1000:  # sanity guard against a non-DZX file
        return []
    out: List[Tuple[str, int, int]] = []
    off = 4
    for _ in range(num):
        if off + 12 > len(data):
            break
        tag = data[off:off + 4].decode("ascii", "replace")
        count, dof = struct.unpack_from(">II", data, off + 4)
        out.append((tag, count, dof))
        off += 12
    return out


def _read_named_entries(data: bytes, offset: int, count: int, stride: int) -> Counter:
    names: Counter = Counter()
    for i in range(count):
        b = offset + i * stride
        if b + 8 > len(data):
            break
        nm = _cstr(data, b, 8)
        if nm:
            names[nm] += 1
    return names


def _read_actor_flows(data: bytes, offset: int, count: int) -> Dict[str, List[int]]:
    """Placement name -> the dialogue flow nodes those placements talk with.

    An NPC's talk flow is not in the game's code: ``getFlowNodeNo()`` reads
    ``home.angle.x``, which is the X rotation of this placement record
    (``fopAcM_prmBase_class.angle`` @0x18, s16 big-endian). So the room's actor
    list IS the map from a conversation to the character who holds it.

    0xFFFF (-1) means "no dialogue" and 0 is the unset default, so both are
    dropped. One NPC normally has several placements, one per story state, each
    with its own flow -- that is how its lines change as the game progresses.
    """
    flows: Dict[str, List[int]] = {}
    for i in range(count):
        b = offset + i * _ACTOR_STRIDE
        if b + _ACTOR_STRIDE > len(data):
            break
        name = _cstr(data, b, 8)
        if not name:
            continue
        node = struct.unpack_from(">h", data, b + _ACTOR_ANGLE_X_OFF)[0]
        if node <= 0:
            continue
        bucket = flows.setdefault(name, [])
        if node not in bucket:
            bucket.append(node)
    return flows


@dataclass
class DzxData:
    actors: Counter = field(default_factory=Counter)   # ACTR/ACTn/TGOB
    actor_flows: Dict[str, List[int]] = field(default_factory=dict)  # name -> flow nodes
    objects: Counter = field(default_factory=Counter)   # SCOB/TGSC/TGDR
    scls: List[Dict[str, Any]] = field(default_factory=list)
    msg_group: Optional[int] = None
    stage_title_no: Optional[int] = None


def parse_dzx(data: bytes) -> DzxData:
    """Parse one DZR/DZS blob into actor rosters + SCLS links + STAG info."""
    res = DzxData()
    for tag, count, off in parse_dzx_chunks(data):
        if _ACTOR_TAG_RE.match(tag):
            res.actors.update(_read_named_entries(data, off, count, _ACTOR_STRIDE))
            for name, nodes in _read_actor_flows(data, off, count).items():
                bucket = res.actor_flows.setdefault(name, [])
                bucket.extend(n for n in nodes if n not in bucket)
        elif _TGSC_TAG_RE.match(tag):
            res.objects.update(_read_named_entries(data, off, count, _TGSC_STRIDE))
        elif tag == "SCLS":
            for i in range(count):
                b = off + i * _SCLS_STRIDE
                if b + _SCLS_STRIDE > len(data):
                    break
                stage = _cstr(data, b, 8)
                spawn, room = struct.unpack_from(">Bb", data, b + 8)
                if stage:
                    res.scls.append({"stage": stage, "room": room, "spawn": spawn})
        elif tag == "STAG":
            if off + 0x3C <= len(data):
                res.msg_group = data[off + _STAG_MSGGROUP_OFF]
                res.stage_title_no = struct.unpack_from(">H", data, off + _STAG_TITLE_OFF)[0]
    return res


# --- event_list.dat -----------------------------------------------------------

_EVT_HEADER = ">IiIiIiIiIiIiIi"  # 7 (top,count) big-endian pairs
_EVT_EVENT_STRIDE = 0xB0
_EVT_STAFF_STRIDE = 0x50


def parse_event_list(data: bytes) -> List[Dict[str, Any]]:
    """Return [{name, staff:[...]}] for one evt/event_list.dat blob."""
    if len(data) < 0x38:
        return []
    (eT, eN, sT, sN, cT, cN, dT, dN, fT, fN, iT, iN, sdT, sdN) = struct.unpack_from(_EVT_HEADER, data, 0)

    def staff_name(idx: int) -> str:
        b = sT + idx * _EVT_STAFF_STRIDE
        if idx < 0 or b + 8 > len(data):
            return ""
        return _cstr(data, b, 8)

    events: List[Dict[str, Any]] = []
    for i in range(max(eN, 0)):
        b = eT + i * _EVT_EVENT_STRIDE
        if b + _EVT_EVENT_STRIDE > len(data):
            break
        name = _cstr(data, b, 32)
        nstaff = struct.unpack_from(">i", data, b + 0x7C)[0]
        idxs = struct.unpack_from(">20i", data, b + 0x2C)
        staff = [staff_name(idxs[k]) for k in range(min(max(nstaff, 0), 20))]
        staff = [s for s in staff if s]
        events.append({"name": name, "staff": staff})
    return events


# --- OBJNAME: which placement names are talking NPCs --------------------------

# src/d/d_stage.cpp: OBJNAME("<placement>", fpcNm_<PROC>_e, <sub>) maps the 8-char
# name in a room's ACTR record to the actor class that gets created.
_OBJNAME_RE = re.compile(
    r'OBJNAME\(\s*"([^"]+)"\s*,\s*fpcNm_([A-Za-z0-9_]+?)_e\s*,', re.M
)


def parse_npc_placement_names(decomp_root: str) -> set:
    """Placement names that create an NPC actor.

    Needed because angle.x only means "dialogue flow node" for actors whose
    ``getFlowNodeNo()`` reads it -- the NPCs. For a clump of grass or a pot the
    same field is what it looks like, an actual rotation, and reading it as a
    conversation invents speakers that do not exist.
    """
    path = os.path.join(decomp_root, "src", "d", "d_stage.cpp")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return set()
    return {
        name for name, proc in _OBJNAME_RE.findall(text)
        if proc.startswith("NPC") or proc.endswith("NPC")
    }


# --- TelopData (place-name captions), optional, from decomp source ------------

_TELOP_RE = re.compile(r"\{\s*'([^']{1,8})'\s*,\s*(\d+)\s*,")


def parse_telop_data(decomp_root: str) -> Dict[str, int]:
    """Extract the TelopData[] table (stage-code -> telopNo message id) from
    dusklight ``src/d/d_event_data.cpp``. Optional enrichment only."""
    path = os.path.join(decomp_root, "src", "d", "d_event_data.cpp")
    result: Dict[str, int] = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return result
    m = re.search(r"TelopData\[\]\s*=\s*\{(.*?)\};", text, re.S)
    if not m:
        return result
    for code, telop in _TELOP_RE.findall(m.group(1)):
        code = code.replace("\\0", "").strip()
        if code and code not in result:
            result[code] = int(telop)
    return result


# --- extraction ---------------------------------------------------------------

def _room_label(arc_name: str) -> str:
    stem = os.path.splitext(os.path.basename(arc_name))[0]
    return re.sub(r"_\d+$", "", stem)  # R00_00 -> R00, STG_00 -> STG


def _load_rarc(path: str):
    from core.containers.rarc_container import RarcContainer
    with open(path, "rb") as f:
        return RarcContainer(f.read())


def extract_stage(stage_dir: str) -> Dict[str, Any]:
    """Aggregate one stage folder (all its .arc files) into a scene record."""
    rooms: Dict[str, Dict[str, Any]] = {}
    scls: List[Dict[str, Any]] = []
    msg_group: Optional[int] = None
    stage_title_no: Optional[int] = None

    for arc_name in sorted(os.listdir(stage_dir)):
        if not arc_name.lower().endswith(".arc"):
            continue
        arc_path = os.path.join(stage_dir, arc_name)
        try:
            arc = _load_rarc(arc_path)
            files = arc.list_files()
        except Exception:
            continue
        room = _room_label(arc_name)
        room_rec = rooms.setdefault(
            room,
            {"actors": Counter(), "objects": Counter(), "events": [], "actor_flows": {}},
        )

        for f in files:
            low = f.lower()
            try:
                if low.endswith((".dzr", ".dzs")):
                    dz = parse_dzx(arc.read_file(f))
                    room_rec["actors"].update(dz.actors)
                    for nm, nodes in dz.actor_flows.items():
                        bucket = room_rec["actor_flows"].setdefault(nm, [])
                        bucket.extend(n for n in nodes if n not in bucket)
                    room_rec["objects"].update(dz.objects)
                    scls.extend(dz.scls)
                    if dz.msg_group is not None:
                        msg_group = dz.msg_group
                    if dz.stage_title_no:
                        stage_title_no = dz.stage_title_no
                elif low.endswith("event_list.dat"):
                    evs = [e for e in parse_event_list(arc.read_file(f)) if e["name"]]
                    room_rec["events"].extend(evs)
            except Exception:
                continue

    # collapse Counters to plain dicts + a per-stage union
    stage_actors: Counter = Counter()
    for room, rec in rooms.items():
        stage_actors.update(rec["actors"])
        stage_actors.update(rec["objects"])
        rec["actors"] = dict(rec["actors"])
        rec["actor_flows"] = {k: sorted(v) for k, v in rec["actor_flows"].items() if v}
        rec["objects"] = dict(rec["objects"])
        # dedupe events by name (same event repeats across room layers)
        seen = {}
        for e in rec["events"]:
            seen.setdefault(e["name"], e)
        rec["events"] = list(seen.values())

    # unique SCLS
    uniq_scls, seen_scls = [], set()
    for s in scls:
        key = (s["stage"], s["room"], s["spawn"])
        if key not in seen_scls:
            seen_scls.add(key)
            uniq_scls.append(s)

    # Stage-wide flow -> placement name, the map a message needs to name its
    # speaker. Flow nodes are unique within a stage's message group, so rooms
    # merge without collision.
    stage_flow_owner: Dict[int, str] = {}
    for rec_room in rooms.values():
        for nm, nodes in (rec_room.get("actor_flows") or {}).items():
            for node in nodes:
                stage_flow_owner.setdefault(node, nm)

    rec: Dict[str, Any] = {
        "rooms": rooms,
        "scls": uniq_scls,
        "actors": dict(stage_actors),
        "flow_owner": {str(k): v for k, v in sorted(stage_flow_owner.items())},
    }
    if msg_group is not None:
        rec["msg_group"] = msg_group
        rec["bmgres"] = f"bmgres{msg_group}"
    if stage_title_no:
        rec["stage_title_no"] = stage_title_no
    return rec


def _find_stage_root(root: str) -> Optional[str]:
    for cand in (os.path.join(root, "res", "Stage"), os.path.join(root, "Stage"), root):
        if os.path.isdir(cand) and any(
            os.path.isdir(os.path.join(cand, d)) for d in os.listdir(cand)
        ):
            # heuristic: a stage dir contains .arc files
            for d in os.listdir(cand):
                sub = os.path.join(cand, d)
                if os.path.isdir(sub) and any(x.lower().endswith(".arc") for x in os.listdir(sub)):
                    return cand
    return None


def extract_all(game_root: str, decomp_root: Optional[str] = None) -> Dict[str, Any]:
    stage_root = _find_stage_root(game_root)
    if not stage_root:
        raise FileNotFoundError(f"Could not find res/Stage under {game_root!r}")

    # Only NPC placements use angle.x as a dialogue flow node; for scenery it is
    # a real rotation. Without the decomp we cannot tell them apart, so the
    # flow->speaker map is dropped rather than filled with invented speakers.
    npc_names = parse_npc_placement_names(decomp_root) if decomp_root else set()

    stages: Dict[str, Any] = {}
    for name in sorted(os.listdir(stage_root)):
        sub = os.path.join(stage_root, name)
        if os.path.isdir(sub):
            stages[name] = extract_stage(sub)

    for rec in stages.values():
        owner = rec.get("flow_owner") or {}
        rec["flow_owner"] = (
            {k: v for k, v in owner.items() if v in npc_names} if npc_names else {}
        )
        for room in (rec.get("rooms") or {}).values():
            flows = room.get("actor_flows") or {}
            room["actor_flows"] = (
                {k: v for k, v in flows.items() if k in npc_names} if npc_names else {}
            )

    # reverse index: placement name -> stages + msg groups it appears in
    actor_index: Dict[str, Dict[str, Any]] = {}
    for stage, rec in stages.items():
        grp = rec.get("msg_group")
        for actor in rec.get("actors", {}):
            entry = actor_index.setdefault(actor, {"stages": [], "msg_groups": []})
            if stage not in entry["stages"]:
                entry["stages"].append(stage)
            if grp is not None and grp not in entry["msg_groups"]:
                entry["msg_groups"].append(grp)

    doc: Dict[str, Any] = {
        "_comment": (
            "Generated by plugins/zelda_bmg/stage_data.py from res/Stage. "
            "msg_group = bmgres<N>.arc the stage loads (scopes local flow IDs). "
            "rooms.*.actors/objects = placement rosters (who is physically where). "
            "rooms.*.events = event_list.dat cast (staff) per scripted scene. "
            "flow_owner = dialogue flow node -> NPC placement name, read from "
            "ACTR angle.x (fopAcM_prmBase_class.angle @0x18), which is what "
            "daNpc*::getFlowNodeNo() returns. Scoped by the stage's msg_group."
        ),
        "source": os.path.abspath(stage_root),
        "stages": stages,
        "actor_index": actor_index,
    }
    if decomp_root:
        telop = parse_telop_data(decomp_root)
        if telop:
            doc["telop_data"] = telop
    return doc


# --- runtime loader -----------------------------------------------------------

_DATA_FILENAME = "stage_scene_data.json"


def load_stage_scene_data(plugin_dir: Optional[str] = None) -> Dict[str, Any]:
    """Load the generated stage_scene_data.json (empty dict if absent)."""
    import json
    if plugin_dir is None:
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(plugin_dir, _DATA_FILENAME)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def msg_group_for_stage(doc: Dict[str, Any], stage: str) -> Optional[int]:
    return (doc.get("stages", {}).get(stage) or {}).get("msg_group")


def flow_speaker_index(doc: Dict[str, Any]) -> Dict[Tuple[int, int], str]:
    """``(msg_group, flow_node) -> NPC placement name``.

    Flow node numbers are only unique within a message group, so the group is
    part of the key. A node claimed by two different NPCs inside one group is
    dropped: an ambiguous speaker is worse than none.
    """
    claims: Dict[Tuple[int, int], set] = {}
    for rec in (doc.get("stages") or {}).values():
        group = rec.get("msg_group")
        if group is None:
            continue
        for node, name in (rec.get("flow_owner") or {}).items():
            try:
                key = (int(group), int(node))
            except (TypeError, ValueError):
                continue
            claims.setdefault(key, set()).add(name)
    return {key: next(iter(names)) for key, names in claims.items() if len(names) == 1}


def stages_for_actor(doc: Dict[str, Any], actor: str) -> List[str]:
    return list((doc.get("actor_index", {}).get(actor) or {}).get("stages", []))


# --- offline CLI --------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Extract TP stage scene data.")
    parser.add_argument("game_root", help="Path to the retail dump 'root' (or its res/Stage).")
    parser.add_argument("--decomp", help="Path to dusklight decomp (for TelopData).", default=None)
    parser.add_argument("-o", "--out", default=None,
                        help="Output JSON path (default: alongside this module).")
    args = parser.parse_args(argv)

    doc = extract_all(args.game_root, decomp_root=args.decomp)
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), _DATA_FILENAME)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    stages = doc["stages"]
    with_grp = sum(1 for s in stages.values() if "msg_group" in s)
    n_actors = len(doc["actor_index"])
    print(f"stages={len(stages)} (with msg_group={with_grp})  distinct placement names={n_actors}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
