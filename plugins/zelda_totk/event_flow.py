"""TotK event flows (``romfs/Event/EventFlow/*.bfevfl.zs``): which actor says which message.

BFEVFL (EventFlow, version 3; layout as in leoetlino/evfl): a file holds flowcharts; a flowchart has
actors, events and entry points. An *action* event names an actor and one of its actions and carries a
parameter container. Talk actions (``Talk``, ``TalkAsync``, ``Demo_Talk``...) carry the message as a
string parameter ``EventFlowMsg/<file>:<label>``. So every talk action is evidence that its actor says
that message; the actor's name (``Npc_Kakariko008``, ``Npc_Goron018``) is the speaker.

Offline tool: ``python -m plugins.zelda_totk.event_flow <romfs> plugins/zelda_totk/speakers.json`` writes
``{"names": {actor: English name}, "files": {member: {"flows": [...], "speakers": {label: actor}}}}``;
the plugin reads it for the Speaker field and the scene context.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from utils.atomic_io import atomic_write_text

from . import sarc

_ACTION, _SWITCH, _FORK, _JOIN, _SUBFLOW = range(5)
# Actors that are not a character: the message comes from the game, a sign, an item window.
EVENT_STARTER = "Npc_EventStarter"
ACTOR_PREFIXES = ("Npc_", "NPC_", "Enemy_", "Dm_Npc_")
# The main cast appears under several actor ids (a sage form, a cutscene double); the token in the id ->
# the actor whose ``_Name`` the character directory has.
SAME_CHARACTER = {"Tulin": "Npc_HighMountain001", "Yunbo": "Npc_Goron020", "Zora_Prince": "Npc_ZoraB001",
                  "Gerudo_Queen": "Npc_oasis003", "Zelda": "Dm_Npc_Zelda_Search_Improve", "Raul": "Dm_Npc_Raul",
                  "Raumi": "Dm_Npc_Raumi", "Ganondorf": "Enemy_Ganondorf", "Kohga": "Enemy_Assassin_Senior"}
NAME_FILES = ("ActorMsg/Npc.msbt", "ActorMsg/CharaDirectory.msbt", "ActorMsg/Boss.msbt", "ActorMsg/PictureBook.msbt")
NON_CHARACTERS = ("EventSystemActor", "GameSystemActor", "SystemTextNPC", "GameROMPlayer", "SceneSoundCtrlTag")


class _Reader:
    def __init__(self, data: bytes):
        self.data = data

    def u8(self, at: int) -> int:
        return self.data[at]

    def u16(self, at: int) -> int:
        return struct.unpack_from("<H", self.data, at)[0]

    def u32(self, at: int) -> int:
        return struct.unpack_from("<I", self.data, at)[0]

    def u64(self, at: int) -> int:
        return struct.unpack_from("<Q", self.data, at)[0]

    def string(self, pointer: int) -> str:
        """A pool string: u16 length, the bytes, a null."""
        if not pointer:
            return ""
        length = self.u16(pointer)
        return self.data[pointer + 2:pointer + 2 + length].decode("utf-8", "replace")

    def dic(self, pointer: int) -> List[str]:
        """The names of a ``DIC `` (radix tree), in entry order."""
        if not pointer or self.data[pointer:pointer + 4] != b"DIC ":
            return []
        count = self.u32(pointer + 4)
        return [self.string(self.u64(pointer + 8 + 16 * (index + 1) + 8)) for index in range(count)]

    def container(self, pointer: int) -> Any:
        """A parameter container as Python values (strings, numbers, nested dicts, lists)."""
        if not pointer:
            return {}
        kind, count, dic = self.u8(pointer), self.u16(pointer + 2), self.u64(pointer + 8)
        at = pointer + 0x10
        if kind == 1:
            names = self.dic(dic)
            return {names[i] if i < len(names) else str(i): self.container(self.u64(at + 8 * i))
                    for i in range(count)}
        if kind in (0, 5):
            return self.string(self.u64(at))
        if kind == 2:
            return struct.unpack_from("<i", self.data, at)[0]
        if kind == 3:
            return self.u32(at) != 0
        if kind == 4:
            return struct.unpack_from("<f", self.data, at)[0]
        if kind == 10:
            return [self.string(self.u64(at + 8 * i)) for i in range(count)]
        if kind == 7:
            return list(struct.unpack_from(f"<{count}i", self.data, at))
        return None


def _actors(r: "_Reader", actors_at: int, count: int) -> List[Tuple[str, List[str]]]:
    """``[(name, [action names])]``; an actor is 0x38 bytes: name, secondary, argument, actions, queries,
    params, counts (version 3 as TotK has it)."""
    actors = []
    for a in range(count):
        base = actors_at + 0x38 * a
        actions_at, num_actions = r.u64(base + 0x18), r.u16(base + 0x30)
        actors.append((r.string(r.u64(base)), [r.string(r.u64(actions_at + 8 * i)) for i in range(num_actions)]))
    return actors


def flowcharts(data: bytes) -> Iterator[Dict[str, Any]]:
    """Every flowchart and timeline of a BFEVFL: ``{"name", "actors": [names], "talks": [(actor, action, message)]}``.

    Cutscenes (``Dm_*``) are timelines: their subtitles are clips and one-shots (0x18 bytes each: time,
    duration or padding, actor and action index, parameters) instead of events.
    """
    if data[:8] != b"BFEVFL\x00\x00":
        raise ValueError("Not a BFEVFL event flow")
    r = _Reader(data)
    yield from _timelines(r)
    count = r.u16(0x20)
    table = r.u64(0x28)
    for index in range(count):
        at = r.u64(table + 8 * index)
        if data[at:at + 4] != b"EVFL":
            continue
        num_actors, _actions, _queries, num_events = (r.u16(at + 0x10 + 2 * i) for i in range(4))
        name = r.string(r.u64(at + 0x20))
        actors_at, events_at = r.u64(at + 0x28), r.u64(at + 0x30)
        actors = _actors(r, actors_at, num_actors)
        talks = []
        for e in range(num_events):
            base = events_at + 0x28 * e
            if r.u8(base + 8) != _ACTION:
                continue
            actor_idx, action_idx = r.u16(base + 0x0C), r.u16(base + 0x0E)
            if actor_idx >= len(actors):
                continue
            actor, actions = actors[actor_idx]
            action = actions[action_idx] if action_idx < len(actions) else ""
            talks.extend(_talks(actor, action, r.container(r.u64(base + 0x10))))
        yield {"name": name, "actors": [a for a, _ in actors], "talks": talks}


def _timelines(r: "_Reader") -> Iterator[Dict[str, Any]]:
    data = r.data
    table = r.u64(0x38)
    for index in range(r.u16(0x22)):
        at = r.u64(table + 8 * index)
        if data[at:at + 4] != b"TLIN":
            continue
        num_actors, _actions, num_clips, num_oneshots = (r.u16(at + 0x14 + 2 * i) for i in range(4))
        name = r.string(r.u64(at + 0x20))
        actors = _actors(r, r.u64(at + 0x28), num_actors)
        records = [(r.u64(at + 0x30) + 0x18 * i, 8) for i in range(num_clips)]
        records += [(r.u64(at + 0x38) + 0x18 * i, 4) for i in range(num_oneshots)]
        talks = []
        for base, actor_at in records:
            actor_idx, action_idx = r.u16(base + actor_at), r.u16(base + actor_at + 2)
            if actor_idx >= len(actors):
                continue
            actor, actions = actors[actor_idx]
            action = actions[action_idx] if action_idx < len(actions) else ""
            talks.extend(_talks(actor, action, r.container(r.u64(base + 0x10))))
        yield {"name": name, "actors": [a for a, _ in actors], "talks": talks}


def _talks(actor: str, action: str, params: Any) -> Iterator[Tuple[str, str, str]]:
    """The messages an action shows; a ``Speaker`` parameter (cutscene voice clips) names who says them."""
    if isinstance(params, dict) and isinstance(params.get("Speaker"), str) and params["Speaker"]:
        actor = params["Speaker"]
    for message in _messages(params):
        yield actor, action, message


def _messages(params: Any) -> Iterator[str]:
    """Message references (``EventFlowMsg/X:Label``) anywhere in an event's parameters."""
    if isinstance(params, dict):
        for value in params.values():
            yield from _messages(value)
    elif isinstance(params, list):
        for value in params:
            yield from _messages(value)
    elif isinstance(params, str) and ":" in params and "Msg/" in params:
        yield params


def message_key(reference: str) -> Optional[Tuple[str, str]]:
    """``EventFlowMsg/Npc_A:Talk_00`` -> ``("EventFlowMsg/Npc_A.msbt", "Talk_00")`` (archive member, label)."""
    path, _, label = reference.partition(":")
    if not path or not label:
        return None
    return f"{path}.msbt", label


def build_index(romfs: Path) -> Dict[str, Dict[str, Any]]:
    """``{member: {"flows": [flowchart...], "actors": {label: {actor: count}}}}`` over every event flow.

    ``Npc_EventStarter`` is the character the player talked to: the flowchart's own NPC (TotK names an
    NPC's flowchart after its actor, ``Npc_Goron018.bfevfl``), so it is recorded under the flowchart name
    when that name is an actor's; in a quest or system flow (``BuildHouse``) the starter stays unknown.
    """
    sarc.dictionary_dirs = lambda: [romfs]
    index: Dict[str, Dict[str, Any]] = {}
    for path in sorted((romfs / "Event" / "EventFlow").glob("*.bfevfl*")):
        raw = path.read_bytes()
        if raw[:4] == sarc.ZSTD_MAGIC:
            raw = sarc.decompress(raw)[0]
        try:
            charts = list(flowcharts(raw))
        except (ValueError, struct.error, IndexError) as error:
            print(f"{path.name}: {error}", file=sys.stderr)
            continue
        for chart in charts:
            for actor, _action, reference in chart["talks"]:
                key = message_key(reference)
                if not key:
                    continue
                if actor == EVENT_STARTER and chart["name"].startswith(ACTOR_PREFIXES):
                    actor = chart["name"]
                entry = index.setdefault(key[0], {"flows": [], "actors": defaultdict(lambda: defaultdict(int))})
                entry["actors"][key[1]][actor] += 1
                if chart["name"] not in entry["flows"]:
                    entry["flows"].append(chart["name"])
    return index


def speaker_of(actors: Dict[str, int]) -> Optional[str]:
    """The one character among a message's actors, or None when several are, or only the game."""
    people = [actor for actor in actors if actor not in NON_CHARACTERS and actor != EVENT_STARTER]
    return people[0] if len(people) == 1 else None


def display_names(romfs: Path, actors) -> Dict[str, str]:
    """``{actor: name}`` from the English ``ActorMsg`` files (labels ``<actor>_Name``).

    An actor variant without its own name (``Npc_Kakariko002_01``) takes the name of the shortest
    prefix that has one (``Npc_Kakariko002`` -> Paya).
    """
    from plugins.common.msbt import Msbt
    from .tags import to_editor
    archives = sorted((romfs / "Mals").glob("USen.Product.*.sarc.zs"))
    if not archives:
        return {}
    container = sarc.SarcContainer(archives[-1].read_bytes())
    known: Dict[str, str] = {}
    for member in NAME_FILES:
        if member not in container.list_files():
            continue
        msbt = Msbt(container.read_file(member))
        for index, label in msbt.labels.items():
            text = to_editor(msbt.messages[index]).strip()
            if label.endswith("_Name") and text and "{" not in text:
                known.setdefault(label[:-5], text)
    names: Dict[str, str] = {}
    for actor in actors:
        parts = actor.split("_")
        for end in range(len(parts), 1, -1):
            if "_".join(parts[:end]) in known:
                names[actor] = known["_".join(parts[:end])]
                break
        else:
            same = next((known[other] for token, other in SAME_CHARACTER.items() if token in actor and other in known),
                        None)
            if same:
                names[actor] = same
    return names


def speaker_table(romfs: Path) -> Dict[str, Any]:
    """What the plugin ships as ``speakers.json``: speakers per message, flows per file, display names."""
    index = build_index(romfs)
    files: Dict[str, Any] = {}
    used = set()
    for member, entry in sorted(index.items()):
        speakers = {label: who for label, actors in sorted(entry["actors"].items()) if (who := speaker_of(actors))}
        used.update(speakers.values())
        files[member] = {"flows": entry["flows"], "speakers": speakers}
    return {"names": dict(sorted(display_names(romfs, used).items())), "files": files}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("romfs", type=Path, help="romfs with Event/EventFlow, Mals and Pack/ZsDic.pack.zs")
    parser.add_argument("output", type=Path, help="usually plugins/zelda_totk/speakers.json")
    args = parser.parse_args(argv)
    table = speaker_table(args.romfs)
    atomic_write_text(args.output, json.dumps(table, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    lines = sum(len(entry["speakers"]) for entry in table["files"].values())
    print(f"{args.output}: {len(table['files'])} message files, {lines} lines with one speaker, "
          f"{len(table['names'])} display names")
    return 0


if __name__ == "__main__":
    sys.exit(main())