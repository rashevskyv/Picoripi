"""Room client against a real room server: operations, refusals, token identity and removal."""
import pytest

from core.collab.client import RoomClient
from core.collab.server import RoomServer

FP = "fp-client"
PW = "pw-client"


@pytest.fixture
def room(tmp_path):
    server = RoomServer(PW, FP, port=0, host="127.0.0.1", journal=tmp_path / "collab_room.json")
    server.start()
    yield server
    server.stop()


def _client(server, name, token=None):
    return RoomClient(f"127.0.0.1:{server.port}", name, PW, FP, token=token)


def _stop(client):
    client.stop()
    client.wait(5000)


def test_the_first_joiner_with_the_creation_token_is_the_host(qtbot, room):
    host = _client(room, "Host", room.room.owner_token_plain)
    with qtbot.waitSignal(host.joined, timeout=5000) as joined:
        host.start()
    try:
        assert joined.args[0]["role"] == "host" and host.role == "host"
        assert host.token == room.room.owner_token_plain or room.room.who(host.token) == host.participant_id
    finally:
        _stop(host)


def test_a_claim_is_answered_to_its_sender_and_a_claimed_row_is_refused_to_others(qtbot, room):
    host = _client(room, "Host", room.room.owner_token_plain)
    olena = _client(room, "Olena")
    answers, refusals = [], []
    host.op_done.connect(lambda op_id, kind, result: answers.append((kind, result)))
    olena.edits_refused.connect(refusals.append)
    with qtbot.waitSignal(host.joined, timeout=5000):
        host.start()
    with qtbot.waitSignal(olena.joined, timeout=5000):
        olena.start()
    try:
        host.queue_op("claim", scope={"kind": "row", "label": "k"}, keys=["k"])
        qtbot.waitUntil(lambda: bool(answers), timeout=5000)
        assert answers[0][0] == "claim" and "granted" in answers[0][1]
        olena.queue_edit("k", "Olena's text")
        qtbot.waitUntil(lambda: bool(refusals), timeout=5000)
        assert refusals[0]["k"]["reason"] == "claimed" and refusals[0]["k"]["mine"] == "Olena's text"
    finally:
        _stop(olena)
        _stop(host)


def test_a_participant_who_reconnects_keeps_its_token_and_its_member(qtbot, room):
    client = _client(room, "Olena")
    with qtbot.waitSignal(client.joined, timeout=5000) as first:
        client.start()
    token, member = client.token, first.args[0]["id"]
    _stop(client)
    again = _client(room, "Olena", token)
    with qtbot.waitSignal(again.joined, timeout=5000) as second:
        again.start()
    try:
        assert second.args[0]["id"] == member and again.token == token
    finally:
        _stop(again)


def test_a_removed_participant_is_refused_when_it_joins_again(qtbot, room):
    host = _client(room, "Host", room.room.owner_token_plain)
    olena = _client(room, "Olena")
    refusals = []
    olena.refused.connect(refusals.append)
    with qtbot.waitSignal(host.joined, timeout=5000):
        host.start()
    with qtbot.waitSignal(olena.joined, timeout=5000):
        olena.start()
    member = olena.participant_id
    try:
        host.queue_op("kick", target=member)
        qtbot.waitUntil(lambda: bool(refusals), timeout=10000)
        assert "removed" in refusals[0]
    finally:
        _stop(olena)
        _stop(host)
