"""Call a plugin hook without letting the plugin take the application down.

Plugin code is the part of the program that changes most and is tested least.
A hook called bare from a hot path (painting the editor, opening a file) turns
any mistake in it into an unhandled exception. ``safe_call`` logs the failure
against the plugin and returns a default the caller can carry on with.

Use it where the caller has a sensible answer for "the plugin could not say".
Do not use it to hide a failure the user has to know about: saving, for one,
must fail loudly.
"""
from __future__ import annotations

from typing import Any

from utils.logging_utils import log_error


def safe_call(rules: Any, hook: str, *args: Any, default: Any = None, **kwargs: Any) -> Any:
    """``rules.<hook>(*args, **kwargs)``, or ``default`` when the hook is missing or raises."""
    method = getattr(rules, hook, None)
    if not callable(method):
        return default
    try:
        return method(*args, **kwargs)
    except Exception as error:  # noqa: BLE001 - whatever the plugin raised is the finding
        log_error(f"Plugin hook {hook}() failed: {type(error).__name__}: {error}", exc_info=True)
        return default
