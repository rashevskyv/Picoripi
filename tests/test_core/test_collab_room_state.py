"""The window's mirror of roles, claims, comments and approvals, and its actions, with two windows in one room."""
import pytest

from handlers.collab_handler import saved_token
from test_core.test_collab import _project_window, _wait_joined


@pytest.fixture
def pair(tmp_path, qtbot):
    a, b = _project_window(tmp_path, "a"), _project_window(tmp_path, "b")
    yield a, b
    for mw in (a, b):
        mw.collab_handler.leave()


def _host_and_guest(qtbot, pair):
    a, b = pair
    port = a.collab_handler.host(0, "pw", "Host", bind="127.0.0.1")
    _wait_joined(qtbot, a)
    b.collab_handler.join(f"127.0.0.1:{port}", "pw", "Guest")
    _wait_joined(qtbot, b)
    qtbot.waitUntil(lambda: len(b.collab_handler.members) == 2, timeout=5000)
    qtbot.waitUntil(lambda: len(a.collab_handler.members) == 2, timeout=5000)   # the host learns of the guest by its join event
    return a, b


def test_a_claim_reaches_the_other_window_and_its_edit_is_put_back(qtbot, pair):
    a, b = _host_and_guest(qtbot, pair)
    ha, hb = a.collab_handler, b.collab_handler
    key = ha._key(0, 0)
    ha.client.queue_edit(key, "Hello in the room")          # a row the room holds: the guest keeps its text
    qtbot.waitUntil(lambda: hb._room_text.get(key) == "Hello in the room", timeout=5000)
    ha.claim("row", "Hello", [key])
    qtbot.waitUntil(lambda: bool(hb.claims), timeout=5000)
    assert hb.claim_owner(key) == ha.client.participant_id
    assert hb.row_notes(key)["claimed_by"] == "Host" and not hb.can_edit(key)
    hb._apply(0, 0, "Changed by Guest")                     # what the editor shows after a keystroke
    hb.on_local_edit(0, 0, "Changed by Guest", "USER_EDIT")
    assert hb._current(0, 0) == "Hello in the room"         # the room's text goes back in place


def test_a_comment_is_seen_resolved_and_only_its_author_or_a_moderator_deletes_it(qtbot, pair):
    a, b = _host_and_guest(qtbot, pair)
    ha, hb = a.collab_handler, b.collab_handler
    key = ha._key(0, 0)
    ha.comment("row", "Hello", [key], "Check the tone")
    qtbot.waitUntil(lambda: bool(hb.comments), timeout=5000)
    cid = next(iter(hb.comments))
    qtbot.waitUntil(lambda: cid in ha.comments, timeout=5000)     # the author's own window learns it on its next poll
    assert hb.row_notes(key)["comments_open"] == 1
    hb.resolve_comment(cid, True)
    qtbot.waitUntil(lambda: ha.comments[cid]["resolved"] is not None, timeout=5000)
    assert ha.row_notes(key)["comments_open"] == 0
    hb.delete_comment(cid)                                  # not the author, and a translator
    qtbot.waitUntil(lambda: "not allowed" in hb.last_message, timeout=5000)
    assert cid in ha.comments
    ha.delete_comment(cid)                                  # the author deletes its own
    qtbot.waitUntil(lambda: cid not in hb.comments, timeout=5000)


def test_the_host_transfers_the_role_and_becomes_a_moderator(qtbot, pair):
    a, b = _host_and_guest(qtbot, pair)
    a.collab_handler.transfer_host(b.collab_handler.client.participant_id)
    qtbot.waitUntil(lambda: b.collab_handler.role == "host", timeout=5000)
    qtbot.waitUntil(lambda: a.collab_handler.role == "moderator", timeout=5000)
    qtbot.waitUntil(lambda: any(e["action"] == "host_transferred" for e in b.collab_handler.log), timeout=5000)


def test_the_token_is_kept_for_the_name_and_saved_on_this_computer(qtbot, pair):
    a, b = _host_and_guest(qtbot, pair)
    assert saved_token("Guest") == b.collab_handler.client.token
    assert saved_token("Host") == a.collab_handler.client.token


def test_a_refused_edit_puts_the_room_text_back_and_says_why(qtbot, pair):
    a, b = _host_and_guest(qtbot, pair)
    hb = b.collab_handler
    hb._apply(0, 0, "Typed by Guest")
    hb._on_edits_refused({hb._key(0, 0): {"reason": "claimed", "owner": "Host",
                                          "row": {"text": "Hello", "rev": 1}, "mine": "Typed by Guest"}})
    assert hb._current(0, 0) == "Hello"
    assert hb._room_text[hb._key(0, 0)] == "Hello"
    hb._apply(0, 1, "Local only")                          # a row the room does not hold keeps its local text
    hb._on_edits_refused({hb._key(0, 1): {"reason": "claimed", "owner": "Host",
                                          "row": {"text": "", "rev": 0}, "mine": "Local only"}})
    assert hb._current(0, 1) == "Local only"
    assert hb.claim_owner_name(hb._key(0, 0)) is None       # no claim in this mirror: the refusal came from the room


def test_a_snapshot_replaces_the_mirror_in_a_turn(qtbot, pair):
    a, b = _host_and_guest(qtbot, pair)
    hb = b.collab_handler
    hb._on_remote_events([{"type": "snapshot", "seq": 999, "state": {
        "members": [{"id": "m1", "name": "Ihor", "role": "moderator", "online": True, "banned": False}],
        "claims": [], "requests": [], "comments": []}}])
    qtbot.waitUntil(lambda: not hb._turns, timeout=5000)
    assert hb.members == {"m1": {"name": "Ihor", "role": "moderator", "online": True, "banned": False}}
    assert hb.claims == {} and hb.comments == {}
