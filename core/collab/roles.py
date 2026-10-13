"""Room roles and the one permission table the room server asks for every operation.

Roles: host (one; transferred by the host), moderator (any number), reviewer, translator (default), observer.
The server checks ``allowed`` before it applies an operation; the UI only hides what ``allowed`` would refuse.
Stdlib only: the headless room server imports this module.
"""
from __future__ import annotations

HOST = "host"
MODERATOR = "moderator"
REVIEWER = "reviewer"
TRANSLATOR = "translator"
OBSERVER = "observer"
ROLES = (HOST, MODERATOR, REVIEWER, TRANSLATOR, OBSERVER)
# Roles a host or moderator can give. The host role only moves by transfer.
ASSIGNABLE = (MODERATOR, REVIEWER, TRANSLATOR, OBSERVER)
# Roles a moderator may move between (translator <-> observer or reviewer).
MOVABLE = (TRANSLATOR, REVIEWER, OBSERVER)
# Roles that can own a claim (a row, file, folder, project or any set of rows).
CLAIM_OWNERS = (HOST, MODERATOR, TRANSLATOR)

ACTIONS = ("edit", "approve", "claim", "claim_decide", "assign", "comment", "resolve_comment", "reopen_any_comment",
           "delete_any_comment", "kick", "set_role", "transfer_host", "view_log")


def allowed(actor: str, action: str, target: str | None = None, new: str | None = None) -> bool:
    """May a member with role ``actor`` do ``action``?

    ``target`` is the current role of the member the action is about; ``new`` the role it would become.
    Unknown actions raise ``ValueError``: the table has no default.
    """
    if action == "edit":
        return actor in (HOST, MODERATOR, TRANSLATOR)
    if action == "approve":
        return actor in (HOST, MODERATOR, REVIEWER)
    if action == "claim":
        return actor in CLAIM_OWNERS
    if action in ("claim_decide", "assign"):
        return actor in (HOST, MODERATOR)
    if action == "comment":
        return actor in ROLES
    if action == "resolve_comment":                     # observers read and comment; they do not resolve
        return actor in (HOST, MODERATOR, REVIEWER, TRANSLATOR)
    if action == "reopen_any_comment":                  # reopen a comment another member resolved
        return actor in (HOST, MODERATOR)
    if action == "delete_any_comment":
        return actor in (HOST, MODERATOR)
    if action == "kick":
        return actor in (HOST, MODERATOR) and target not in (HOST, MODERATOR)
    if action == "set_role":
        if target == HOST or new not in ASSIGNABLE:
            return False
        if actor == HOST:
            return True
        if actor == MODERATOR:
            return target in MOVABLE and new in MOVABLE and TRANSLATOR in (target, new)
        return False
    if action == "transfer_host":
        return actor == HOST
    if action == "view_log":
        return actor == HOST
    raise ValueError(f"unknown room action: {action}")
