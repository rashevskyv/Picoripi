"""Room server without Qt: roles, claims, comments, identity, host transfer, operations and the headless entry point."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import requests

from core.collab import roles
from core.collab.roles import allowed
from core.collab.server import COMMENTS_NAME, JOURNAL_NAME, Room, RoomServer, build_server, main, parse_args

FP = "fp-1"
PW = "secret"
REPO = Path(__file__).resolve().parents[2]


def _edit(room, pid, key, text, rev, seq=None):
    op = {"op_id": f"e-{key}-{text}-{rev}-{seq}", "kind": "edit", "key": key, "text": text, "base_rev": rev}
    if seq is not None:
        op["seq"] = seq
    return room.apply_ops(pid, [op])[op["op_id"]]


def _room_with_host(tmp_path=None, journal=True):
    path = (tmp_path / JOURNAL_NAME) if (journal and tmp_path is not None) else None
    room = Room(PW, FP, path)
    token = room.owner_token_plain
    host = room.join("Host", PW, FP, token)
    return room, host, token


def _join(room, name, token=None):
    return room.join(name, PW, FP, token)


# ---- the permission table ---------------------------------------------------------------

@pytest.mark.parametrize("actor, action, target, new, expected", [
    ("host", "edit", None, None, True),
    ("moderator", "edit", None, None, True),
    ("translator", "edit", None, None, True),
    ("reviewer", "edit", None, None, False),
    ("observer", "edit", None, None, False),
    ("host", "approve", None, None, True),
    ("moderator", "approve", None, None, True),
    ("reviewer", "approve", None, None, True),
    ("translator", "approve", None, None, False),
    ("observer", "approve", None, None, False),
    ("host", "claim", None, None, True),
    ("moderator", "claim", None, None, True),
    ("translator", "claim", None, None, True),
    ("reviewer", "claim", None, None, False),
    ("observer", "claim", None, None, False),
    ("host", "claim_decide", None, None, True),
    ("moderator", "claim_decide", None, None, True),
    ("translator", "claim_decide", None, None, False),
    ("moderator", "assign", None, None, True),
    ("translator", "assign", None, None, False),
    ("observer", "comment", None, None, True),
    ("reviewer", "comment", None, None, True),
    ("translator", "resolve_comment", None, None, True),
    ("reviewer", "resolve_comment", None, None, True),
    ("observer", "resolve_comment", None, None, False),
    ("moderator", "reopen_any_comment", None, None, True),
    ("translator", "reopen_any_comment", None, None, False),
    ("host", "delete_any_comment", None, None, True),
    ("moderator", "delete_any_comment", None, None, True),
    ("translator", "delete_any_comment", None, None, False),
    ("host", "kick", "translator", None, True),
    ("host", "kick", "moderator", None, False),
    ("moderator", "kick", "translator", None, True),
    ("moderator", "kick", "host", None, False),
    ("translator", "kick", "observer", None, False),
    ("host", "set_role", "translator", "moderator", True),
    ("host", "set_role", "moderator", "translator", True),
    ("host", "set_role", "translator", "host", False),
    ("host", "set_role", "host", "translator", False),
    ("moderator", "set_role", "translator", "reviewer", True),
    ("moderator", "set_role", "observer", "translator", True),
    ("moderator", "set_role", "translator", "moderator", False),
    ("moderator", "set_role", "reviewer", "observer", False),
    ("moderator", "set_role", "moderator", "translator", False),
    ("translator", "set_role", "observer", "translator", False),
    ("host", "transfer_host", None, None, True),
    ("moderator", "transfer_host", None, None, False),
    ("host", "view_log", None, None, True),
    ("moderator", "view_log", None, None, False),
])
def test_permission_matrix(actor, action, target, new, expected):
    assert allowed(actor, action, target=target, new=new) is expected


def test_an_unknown_action_is_an_error_not_a_default():
    with pytest.raises(ValueError):
        allowed("host", "fly")
    assert set(roles.ROLES) == {"host", "moderator", "reviewer", "translator", "observer"}


# ---- enforcement in the edit path ---------------------------------------------------

def test_a_claimed_row_is_edited_only_by_its_owner(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    ihor = _join(room, "Ihor")
    granted = room.apply_ops(olena["id"], [{"op_id": "c1", "kind": "claim", "scope": {"kind": "row", "label": "k1"},
                                            "keys": ["k1"]}])["c1"]
    assert "granted" in granted
    assert _edit(room, ihor["id"], "k1", "Ihor", 0)["refused"]["reason"] == "claimed"
    assert _edit(room, olena["id"], "k1", "Olena", 0) == {"ok": True, "rev": 1}
    assert _edit(room, host["id"], "k1", "Host", 1)["refused"]["reason"] == "claimed"    # the host takes away first


def test_a_claim_keeps_its_rows_for_the_owner_when_the_owner_is_offline(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    room.apply_ops(olena["id"], [{"op_id": "c", "kind": "claim", "scope": {"kind": "file", "label": "a"},
                                  "keys": ["a::1", "a::2"]}])
    room.leave(olena["id"])
    assert _edit(room, host["id"], "a::1", "Host", 0)["refused"]["reason"] == "claimed"
    claim = next(iter(room.claims.values()))
    assert room._claim_out(claim)["online"] is False


def test_reviewer_and_observer_cannot_change_text(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    reviewer = _join(room, "Rev")
    observer = _join(room, "Obs")
    room.apply_ops(host["id"], [{"op_id": "r1", "kind": "role", "target": reviewer["id"], "role": "reviewer"},
                                {"op_id": "r2", "kind": "role", "target": observer["id"], "role": "observer"}])
    assert _edit(room, reviewer["id"], "k", "x", 0)["refused"]["reason"] == "role"
    assert _edit(room, observer["id"], "k", "x", 0)["refused"]["reason"] == "role"
    assert room.rows == {}


def test_a_refused_edit_carries_the_room_text_so_the_client_can_restore_it(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    _edit(room, host["id"], "k", "Room text", 0)
    olena = _join(room, "Olena")
    room.apply_ops(olena["id"], [{"op_id": "c", "kind": "claim", "scope": {"kind": "row", "label": "k"}, "keys": ["k"]}])
    refused = _edit(room, host["id"], "k", "Mine", 1)["refused"]
    assert refused["row"]["text"] == "Room text"


def test_the_legacy_edit_path_reports_refusals_apart(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    reviewer = _join(room, "Rev")
    room.apply_ops(host["id"], [{"op_id": "r", "kind": "role", "target": reviewer["id"], "role": "reviewer"}])
    result = room.edit(reviewer["id"], [{"key": "k", "text": "x", "base_rev": 0}])
    assert result == {"accepted": {}, "conflicts": {}, "refused": {"k": {"reason": "role", "row": {
        "text": "", "rev": 0, "by": "", "name": ""}}}}


# ---- claims -----------------------------------------------------------------------------

def test_a_free_area_is_granted_and_an_area_held_by_someone_else_is_a_request(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena, ihor = _join(room, "Olena"), _join(room, "Ihor")
    assert "granted" in room.apply_ops(olena["id"], [{"op_id": "a", "kind": "claim",
                                                      "scope": {"kind": "block", "label": "B1"}, "keys": ["b1::1", "b1::2"]}])["a"]
    result = room.apply_ops(ihor["id"], [{"op_id": "b", "kind": "claim",
                                          "scope": {"kind": "row", "label": "b1::2"}, "keys": ["b1::2"]}])["b"]
    assert "requested" in result and len(room.requests) == 1
    assert "granted" in room.apply_ops(ihor["id"], [{"op_id": "c", "kind": "claim",
                                                     "scope": {"kind": "row", "label": "b1::9"}, "keys": ["b1::9"]}])["c"]
    types = [e["type"] for e in room.events]
    assert "claim_requested" in types and types.count("claim_granted") == 2


def test_a_host_approving_a_request_takes_the_area_away_from_its_owner(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena, ihor = _join(room, "Olena"), _join(room, "Ihor")
    room.apply_ops(olena["id"], [{"op_id": "a", "kind": "claim", "scope": {"kind": "file", "label": "f"},
                                  "keys": ["f::1"]}])
    rid = room.apply_ops(ihor["id"], [{"op_id": "b", "kind": "claim", "scope": {"kind": "row", "label": "f::1"},
                                       "keys": ["f::1"]}])["b"]["requested"]
    room.apply_ops(host["id"], [{"op_id": "d", "kind": "decide", "rid": rid, "approve": True}])
    assert room.row_claim["f::1"] and room.claims[room.row_claim["f::1"]]["owner"] == ihor["id"]
    assert [c["owner"] for c in room.claims.values()] == [ihor["id"]]
    assert any(e["type"] == "claim_released" and e["reason"] == "reassigned" for e in room.events)


def test_a_translator_cannot_decide_or_assign_and_a_moderator_can(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena, ihor = _join(room, "Olena"), _join(room, "Ihor")
    room.apply_ops(olena["id"], [{"op_id": "a", "kind": "claim", "scope": {"kind": "row", "label": "x"}, "keys": ["x"]}])
    refused = room.apply_ops(ihor["id"], [{"op_id": "as", "kind": "assign", "target": ihor["id"],
                                           "scope": {"kind": "row", "label": "x"}, "keys": ["x"]}])["as"]
    assert refused["refused"]["reason"] == "role"
    assert "granted" in room.apply_ops(host["id"], [{"op_id": "as2", "kind": "assign", "target": ihor["id"],
                                                     "scope": {"kind": "row", "label": "x"}, "keys": ["x"]}])["as2"]


def test_the_owner_releases_its_claim_and_a_host_can_take_away_a_claim_of_someone_offline(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    cid = room.apply_ops(olena["id"], [{"op_id": "a", "kind": "claim", "scope": {"kind": "row", "label": "k"},
                                        "keys": ["k"]}])["a"]["granted"]
    ihor = _join(room, "Ihor")
    assert room.apply_ops(ihor["id"], [{"op_id": "x", "kind": "release", "cid": cid}])["x"]["error"] == "not allowed"
    room.leave(olena["id"])
    assert room.apply_ops(host["id"], [{"op_id": "y", "kind": "release", "cid": cid}])["y"] == {"ok": True}
    assert room.claims == {}


# ---- comments ---------------------------------------------------------------------------

def test_comments_resolve_reopen_and_delete_by_role(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena, ihor = _join(room, "Olena"), _join(room, "Ihor")
    cid = room.apply_ops(olena["id"], [{"op_id": "c", "kind": "comment", "scope": {"kind": "row", "label": "k"},
                                        "keys": ["k"], "text": "Check the tone"}])["c"]["comment"]
    assert room.apply_ops(ihor["id"], [{"op_id": "r", "kind": "comment_resolve", "id": cid, "resolved": True}])["r"] == {"ok": True}
    assert room.comments[cid]["resolved"]["name"] == "Ihor"
    assert room.apply_ops(ihor["id"], [{"op_id": "r2", "kind": "comment_resolve", "id": cid, "resolved": False}])["r2"] == {"ok": True}
    assert room.comments[cid]["resolved"] is None
    refused = room.apply_ops(ihor["id"], [{"op_id": "d", "kind": "comment_delete", "id": cid}])["d"]
    assert refused["error"] == "not allowed"
    assert room.apply_ops(olena["id"], [{"op_id": "d2", "kind": "comment_delete", "id": cid}])["d2"] == {"ok": True}
    cid2 = room.apply_ops(ihor["id"], [{"op_id": "c2", "kind": "comment", "scope": {"kind": "project", "label": ""},
                                        "text": "General remark"}])["c2"]["comment"]
    assert room.apply_ops(host["id"], [{"op_id": "d3", "kind": "comment_delete", "id": cid2}])["d3"] == {"ok": True}
    assert any(l["action"] == "comment_deleted" for l in room.log)


def test_an_observer_cannot_resolve_and_a_translator_cannot_reopen_anothers_resolution(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena, ihor, ivan = _join(room, "Olena"), _join(room, "Ihor"), _join(room, "Ivan")
    observer = _join(room, "Obs")
    room.apply_ops(host["id"], [{"op_id": "ro", "kind": "role", "target": observer["id"], "role": "observer"}])
    cid = room.apply_ops(olena["id"], [{"op_id": "c", "kind": "comment", "scope": {"kind": "project", "label": ""},
                                        "text": "Hi"}])["c"]["comment"]
    refused = room.apply_ops(observer["id"], [{"op_id": "r0", "kind": "comment_resolve", "id": cid, "resolved": True}])
    assert refused["r0"] == {"refused": {"reason": "role"}} and room.comments[cid]["resolved"] is None
    assert room.apply_ops(ihor["id"], [{"op_id": "r1", "kind": "comment_resolve", "id": cid, "resolved": True}])["r1"] == {"ok": True}
    refused = room.apply_ops(ivan["id"], [{"op_id": "r2", "kind": "comment_resolve", "id": cid, "resolved": False}])
    assert refused["r2"] == {"refused": {"reason": "role"}} and room.comments[cid]["resolved"]["name"] == "Ihor"
    assert room.apply_ops(olena["id"], [{"op_id": "r3", "kind": "comment_resolve", "id": cid, "resolved": False}])["r3"] == {"ok": True}
    assert room.comments[cid]["resolved"] is None


def test_an_operation_without_seq_is_applied_once_when_it_is_sent_again(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    op = {"op_id": "c-once", "kind": "comment", "scope": {"kind": "project", "label": ""}, "text": "Once"}
    assert "comment" in room.apply_ops(olena["id"], [op])["c-once"]
    assert room.apply_ops(olena["id"], [dict(op)])["c-once"] == {"duplicate": True}
    assert [c["text"] for c in room.comments.values()].count("Once") == 1
    # The same op_id from another member is another operation.
    assert "comment" in room.apply_ops(host["id"], [dict(op)])["c-once"]
    assert [c["text"] for c in room.comments.values()].count("Once") == 2


def test_a_comment_of_another_rooms_file_is_adopted_once_and_a_deleted_one_stays_deleted(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    imported = {"id": "old9", "scope": {"kind": "file", "label": "f"}, "keys": ["f::1"], "author_name": "Ihor",
                "time": 1.0, "text": "Earlier", "resolved": None}
    assert room.apply_ops(olena["id"], [{"op_id": "i0", "kind": "comment_import", "comment": imported}])["i0"] == {
        "refused": {"reason": "role"}}
    assert room.apply_ops(host["id"], [{"op_id": "i1", "kind": "comment_import", "comment": imported}])["i1"] == {
        "comment": "old9"}
    assert room.comments["old9"]["keys"] == {"f::1"} and room.comments["old9"]["author_name"] == "Ihor"
    assert room.apply_ops(host["id"], [{"op_id": "i2", "kind": "comment_import", "comment": imported}])["i2"] == {
        "skipped": "known"}
    assert room.apply_ops(host["id"], [{"op_id": "i3", "kind": "comment_import", "comment": {"id": 5}}])["i3"] == {
        "error": "bad comment"}
    assert room.apply_ops(host["id"], [{"op_id": "d", "kind": "comment_delete", "id": "old9"}])["d"] == {"ok": True}
    assert room.apply_ops(host["id"], [{"op_id": "i4", "kind": "comment_import", "comment": imported}])["i4"] == {
        "skipped": "deleted"}
    assert "old9" not in room.comments
    room.write_journal()
    assert "old9" in Room(PW, FP, tmp_path / JOURNAL_NAME).deleted_comments


def test_an_empty_comment_is_refused(tmp_path):
    room, _, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    assert room.apply_ops(olena["id"], [{"op_id": "c", "kind": "comment",
                                         "scope": {"kind": "row", "label": "k"}, "keys": ["k"],
                                         "text": "   "}])["c"] == {"error": "a comment needs text up to 4000 characters"}


# ---- identity -----------------------------------------------------------------------------

def test_the_same_token_gets_the_same_member_and_its_role_back(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    first = _join(room, "Olena")
    room.apply_ops(host["id"], [{"op_id": "r", "kind": "role", "target": first["id"], "role": "reviewer"}])
    room.leave(first["id"])
    again = _join(room, "Olena", first["token"])
    assert again["id"] == first["id"] and again["role"] == "reviewer" and again["token"] == first["token"]


def test_a_different_token_with_a_name_in_use_online_is_refused(tmp_path):
    room, _, _ = _room_with_host(tmp_path)
    _join(room, "Olena")
    with pytest.raises(ValueError, match="in use"):
        _join(room, "Olena")


def test_a_wrong_password_is_a_permission_error(tmp_path):
    room, _, _ = _room_with_host(tmp_path)
    with pytest.raises(PermissionError):
        room.join("Olena", "nope", FP)


def test_another_project_is_refused(tmp_path):
    room, _, _ = _room_with_host(tmp_path)
    with pytest.raises(ValueError, match="another project"):
        room.join("Olena", PW, "other")


def test_a_kicked_token_cannot_join_again(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    assert room.apply_ops(host["id"], [{"op_id": "k", "kind": "kick", "target": olena["id"]}])["k"] == {"ok": True}
    assert room.who(olena["token"]) is None
    with pytest.raises(ValueError, match="removed"):
        _join(room, "Olena", olena["token"])


def test_the_host_can_lift_a_removal_and_the_member_joins_again(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    room.apply_ops(host["id"], [{"op_id": "k", "kind": "kick", "target": olena["id"]}])
    assert room.apply_ops(host["id"], [{"op_id": "u", "kind": "unban", "target": olena["id"]}])["u"] == {"ok": True}
    again = _join(room, "Olena", olena["token"])
    assert again["id"] == olena["id"]
    assert room.apply_ops(again["id"], [{"op_id": "u2", "kind": "unban", "target": olena["id"]}])["u2"] == {"error": "not allowed"}


def test_a_removed_name_cannot_join_with_a_new_token_until_it_is_allowed_back(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    room.apply_ops(host["id"], [{"op_id": "k", "kind": "kick", "target": olena["id"]}])
    with pytest.raises(ValueError, match="removed"):
        _join(room, "Olena")                                  # a new token, the same name
    with pytest.raises(ValueError, match="removed"):
        _join(room, "OLENA")                                  # the name is compared without case
    room.write_journal()
    with pytest.raises(ValueError, match="removed"):          # the ban survives a restart of the room
        Room(PW, FP, tmp_path / JOURNAL_NAME).join("Olena", PW, FP)
    assert room.apply_ops(host["id"], [{"op_id": "u", "kind": "unban", "target": olena["id"]}])["u"] == {"ok": True}
    assert _join(room, "Olena")["id"] != olena["id"]          # allowed back: the name joins as a new member


def test_a_host_cannot_be_kicked_and_a_moderator_cannot_kick_a_moderator(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    mod = _join(room, "Mod")
    room.apply_ops(host["id"], [{"op_id": "m", "kind": "role", "target": mod["id"], "role": "moderator"}])
    other = _join(room, "Other")
    room.apply_ops(host["id"], [{"op_id": "m2", "kind": "role", "target": other["id"], "role": "moderator"}])
    assert room.apply_ops(mod["id"], [{"op_id": "k", "kind": "kick", "target": host["id"]}])["k"] == {"error": "not allowed"}
    assert room.apply_ops(mod["id"], [{"op_id": "k2", "kind": "kick", "target": other["id"]}])["k2"] == {"error": "not allowed"}


def test_a_moderator_moves_translators_only_between_translator_and_observer_or_reviewer(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    mod = _join(room, "Mod")
    tr = _join(room, "Tr")
    room.apply_ops(host["id"], [{"op_id": "m", "kind": "role", "target": mod["id"], "role": "moderator"}])
    assert room.apply_ops(mod["id"], [{"op_id": "a", "kind": "role", "target": tr["id"], "role": "observer"}])["a"] == {"ok": True}
    assert room.apply_ops(mod["id"], [{"op_id": "b", "kind": "role", "target": tr["id"], "role": "moderator"}])["b"] == {"error": "not allowed"}


# ---- host transfer ------------------------------------------------------------------------

def test_the_host_transfers_the_role_with_confirmation_and_becomes_a_moderator(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    successor = _join(room, "Next")
    without = room.apply_ops(host["id"], [{"op_id": "t0", "kind": "transfer_host", "target": successor["id"]}])["t0"]
    assert "error" in without and room._role(host["id"]) == "host"
    assert room.apply_ops(host["id"], [{"op_id": "t1", "kind": "transfer_host", "target": successor["id"],
                                        "confirm": True}])["t1"] == {"ok": True}
    assert room._role(successor["id"]) == "host" and room._role(host["id"]) == "moderator"
    again = room.apply_ops(host["id"], [{"op_id": "t2", "kind": "transfer_host", "target": host["id"],
                                         "confirm": True}])["t2"]
    assert again == {"error": "not allowed"}              # the old host no longer transfers


def test_the_host_of_a_room_stays_the_host_after_the_journal_is_reloaded(tmp_path):
    room, host, token = _room_with_host(tmp_path)
    room.write_journal()
    again = Room(PW, FP, tmp_path / JOURNAL_NAME)
    assert again.who(token) is None                        # not online yet
    rejoined = again.join("Host", PW, FP, token)
    assert rejoined["role"] == "host" and rejoined["id"] == host["id"]
    assert again.owner_hash is None                        # the creation token is spent


# ---- operations: idempotency and batches -----------------------------------------------

def test_an_operation_applied_twice_changes_nothing(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    op = {"op_id": "x", "seq": 1, "kind": "edit", "key": "k", "text": "A", "base_rev": 0}
    assert room.apply_ops(olena["id"], [op])["x"] == {"ok": True, "rev": 1}
    assert room.apply_ops(olena["id"], [dict(op)])["x"] == {"duplicate": True}
    assert room.rows["k"]["rev"] == 1
    assert [e["type"] for e in room.events].count("edit") == 1


def test_a_rejoin_returns_the_high_water_mark_so_the_client_goes_on_from_it(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    room.apply_ops(olena["id"], [{"op_id": "a", "seq": 5, "kind": "edit", "key": "k", "text": "A", "base_rev": 0}])
    room.leave(olena["id"])
    back = _join(room, "Olena", olena["token"])
    assert back["op_hw"] == 5
    assert room.apply_ops(back["id"], [{"op_id": "b", "seq": 3, "kind": "edit", "key": "j", "text": "x",
                                        "base_rev": 0}])["b"] == {"duplicate": True}


def test_a_bad_operation_is_an_error_for_that_operation_only(tmp_path):
    room, _, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    results = room.apply_ops(olena["id"], [{"op_id": "ok", "kind": "edit", "key": "k", "text": "A", "base_rev": 0},
                                           {"op_id": "bad", "kind": "nonsense"}, {"kind": "edit"}])
    assert results["ok"] == {"ok": True, "rev": 1}
    assert results["bad"] == {"error": "unknown operation"}
    assert results["#2"] == {"error": "bad op id"}


def test_an_approve_with_a_key_that_is_not_text_is_a_plain_error_and_the_batch_goes_on(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    _edit(room, host["id"], "k", "A", 0)
    results = room.apply_ops(host["id"], [{"op_id": "bad", "kind": "approve", "key": ["k"]},
                                          {"op_id": "ok", "kind": "approve", "key": "k"}])
    assert results["bad"] == {"error": "bad key"}
    assert results["ok"] == {"ok": True}
    assert room.rows["k"]["approved"]["name"] == "Host"


# ---- persistence ------------------------------------------------------------------------

def test_the_journal_and_comments_json_keep_members_claims_and_comments(tmp_path):
    room, host, _ = _room_with_host(tmp_path)
    olena = _join(room, "Olena")
    room.apply_ops(olena["id"], [{"op_id": "c", "kind": "claim", "scope": {"kind": "folder", "label": "Shared"},
                                  "keys": ["s::1", "s::2"]}])
    room.apply_ops(olena["id"], [{"op_id": "m", "kind": "comment", "scope": {"kind": "row", "label": "s::1"},
                                  "keys": ["s::1"], "text": "Keep the name"}])
    room.close()
    data = json.loads((tmp_path / JOURNAL_NAME).read_text(encoding="utf-8"))
    assert data["protocol"] == 2 and data["claims"][0]["keys"] == ["s::1", "s::2"]
    assert json.loads((tmp_path / COMMENTS_NAME).read_text(encoding="utf-8"))["comments"][0]["text"] == "Keep the name"
    assert "token_hash" in next(iter(data["members"].values()))
    assert olena["token"] not in (tmp_path / JOURNAL_NAME).read_text(encoding="utf-8")   # the token itself is not stored

    again = Room(PW, FP, tmp_path / JOURNAL_NAME)
    assert len(again.claims) == 1 and len(again.comments) == 1
    assert again.row_claim["s::1"] in again.claims
    assert again.who(olena["token"]) is None and again.join("Olena", PW, FP, olena["token"])["id"] == olena["id"]


def test_an_old_journal_without_members_still_loads_its_rows(tmp_path):
    (tmp_path / JOURNAL_NAME).write_text(json.dumps({"fingerprint": FP, "rows": {"k": {"text": "Так", "rev": 2,
                                                                                    "by": "x", "name": "Olena"}},
                                                     "stats": {}}), encoding="utf-8")
    room = Room(PW, FP, tmp_path / JOURNAL_NAME)
    assert room.rows["k"]["text"] == "Так" and room.rows["k"]["rev"] == 2
    assert room.owner_hash is not None                     # no host yet: a creation token is issued
    room.close()


def test_a_journal_of_another_project_is_not_loaded(tmp_path):
    (tmp_path / JOURNAL_NAME).write_text(json.dumps({"fingerprint": "other", "rows": {"k": {"text": "x"}}}),
                                         encoding="utf-8")
    assert Room(PW, FP, tmp_path / JOURNAL_NAME).rows == {}


# ---- HTTP: no anonymous access, /ops --------------------------------------------------

def test_every_endpoint_needs_a_token_or_the_password(tmp_path):
    server = RoomServer(PW, FP, port=0, host="127.0.0.1", journal=tmp_path / JOURNAL_NAME,
                        owner_token=None).start()
    base = f"http://127.0.0.1:{server.port}"
    try:
        assert requests.get(base + "/events?since=0").status_code == 401
        assert requests.get(base + "/ops?since=0").status_code == 401
        assert requests.post(base + "/ops", json={"room_id": "x", "ops": []}).status_code == 401
        assert requests.post(base + "/edits", json={"edits": []}).status_code == 401
        assert requests.get(base + "/hello").status_code == 404
        assert requests.post(base + "/join", json={"name": "A", "password": "bad", "fingerprint": FP}).status_code == 401
        assert requests.post(base + "/join", json={"name": "A", "password": PW, "fingerprint": FP}).status_code == 200
    finally:
        server.stop()


def test_post_ops_checks_the_room_id_and_the_batch_size(tmp_path):
    server = RoomServer(PW, FP, port=0, host="127.0.0.1").start()
    base = f"http://127.0.0.1:{server.port}"
    try:
        token = server.room.owner_token_plain
        joined = requests.post(base + "/join", json={"name": "Host", "password": PW, "fingerprint": FP,
                                                     "token": token}).json()
        headers = {"X-Room-Token": joined["token"]}
        op = {"op_id": "a", "seq": 1, "kind": "edit", "key": "k", "text": "A", "base_rev": 0}
        wrong = requests.post(base + "/ops", headers=headers, json={"room_id": "other", "ops": [op]})
        assert wrong.status_code == 409
        ok = requests.post(base + "/ops", headers=headers, json={"room_id": joined["room_id"], "ops": [op]})
        assert ok.json()["results"]["a"] == {"ok": True, "rev": 1}
        many = [{"op_id": str(i), "kind": "edit", "key": "k", "text": "x", "base_rev": 0} for i in range(501)]
        assert requests.post(base + "/ops", headers=headers,
                             json={"room_id": joined["room_id"], "ops": many}).status_code == 400
        feed = requests.get(base + "/ops", headers=headers, params={"since": 0}).json()
        assert any(e["type"] == "edit" for e in feed["events"])
    finally:
        server.stop()


# ---- headless entry point ------------------------------------------------------------------

def test_the_headless_server_starts_with_a_host_token_file_and_stops_writing_its_journal(tmp_path):
    password = tmp_path / "pw.txt"
    password.write_text(PW + "\n", encoding="utf-8")
    token_file = tmp_path / "owner.txt"
    args = parse_args(["--headless", "--port", "0", "--password-file", str(password),
                       "--project-dir", str(tmp_path / "project"), "--owner-token-file", str(token_file)])
    server, issued = build_server(args)
    assert issued is None and token_file.read_text(encoding="utf-8")       # the file holds the token, not stdout
    server.start()
    try:
        base = f"http://127.0.0.1:{server.port}"
        joined = requests.post(base + "/join", json={"name": "Host", "password": PW, "fingerprint": FP,
                                                     "token": token_file.read_text(encoding="utf-8")}).json()
        assert joined["role"] == "host"
    finally:
        server.stop()
    assert (tmp_path / "project" / JOURNAL_NAME).is_file()


def test_the_headless_server_without_a_journal_binds_its_project_to_the_host_join(tmp_path):
    password = tmp_path / "pw.txt"
    password.write_text(PW, encoding="utf-8")
    args = parse_args(["--headless", "--password-file", str(password), "--project-dir", str(tmp_path / "p"),
                       "--port", "0", "--owner-name", "Ihor"])
    server, issued = build_server(args)
    try:
        assert issued and server.room.fingerprint is None
        with pytest.raises(ValueError, match="host joins first"):
            server.room.join("Olena", PW, FP)
        host = server.room.join("Olena", PW, FP, issued)
        assert host["role"] == "host" and host["id"] in server.room.members
        assert server.room.members[host["id"]]["name"] == "Ihor"     # the owner name wins over the joiner's
    finally:
        server.stop()


def test_a_headless_room_that_would_lose_its_new_token_does_not_start_and_prints_nothing(tmp_path, capsys):
    password = tmp_path / "pw.txt"
    password.write_text(PW, encoding="utf-8")
    code = main(["--headless", "--port", "0", "--password-file", str(password), "--project-dir", str(tmp_path / "p")])
    captured = capsys.readouterr()
    assert code == 2 and captured.out == "" and "--print-token" in captured.err


def test_the_headless_module_runs_as_a_process_and_imports_no_qt(tmp_path):
    check = subprocess.run([sys.executable, "-c", "import sys, core.collab.server as s;"
                           "assert not any(m.startswith('PyQt') for m in sys.modules), 'Qt imported'"],
                           cwd=REPO, capture_output=True, text=True, timeout=60)
    assert check.returncode == 0, check.stderr
    password = tmp_path / "pw.txt"
    password.write_text(PW, encoding="utf-8")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen([sys.executable, "-m", "core.collab.server", "--headless", "--port", "0",
                             "--password-file", str(password), "--project-dir", str(tmp_path / "p"), "--print-token"],
                            cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        line = json.loads(proc.stdout.readline())
        assert line["port"] > 0 and line["owner_token"]
        base = f"http://127.0.0.1:{line['port']}"
        joined = requests.post(base + "/join", json={"name": "Host", "password": PW, "fingerprint": "fp",
                                                     "token": line["owner_token"]}, timeout=10)
        assert joined.status_code == 200 and joined.json()["role"] == "host"
    finally:
        proc.kill()
        proc.wait(timeout=10)
