"""Check that a translated chunk answers the items it was asked about."""
from __future__ import annotations

from typing import Any, List, Sequence


def _item_id(item: Any) -> Any:
    value = item.get("id") if isinstance(item, dict) else None
    return None if value is None else str(value)


def verify_chunk_ids(translated_items: Sequence[Any], chunk_items: Sequence[Any]) -> None:
    """Raise ``ValueError`` unless the reply's ids line up with the chunk's.

    Translations are written back by position, so a reply whose ids are in a
    different order, or name other strings, would put text into the wrong rows
    without any error. A reply is accepted when its ids equal the chunk's in
    order, or when the model plainly did not echo them (none at all, or its own
    0- or 1-based numbering) -- then position is the only reading there is.
    """
    returned: List[Any] = [_item_id(item) for item in translated_items]
    expected: List[Any] = [_item_id(item) for item in chunk_items]
    if len(returned) != len(expected):
        raise ValueError(f"Expected {len(expected)} translated items, got {len(returned)}.")
    if returned == expected or all(value is None for value in returned):
        return
    count = len(returned)
    if returned in ([str(n) for n in range(count)], [str(n) for n in range(1, count + 1)]):
        return
    raise ValueError(
        f"Translated ids do not match the request (expected {expected}, got {returned}); "
        "the reply is reordered or answers other strings."
    )
