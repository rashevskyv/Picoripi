"""Wii discs, identify only: the game ID and the magic at the start of the disc header.

Every Wii disc keeps its partitions encrypted with the common key from the console's key file, which Picoripi does not
read yet. The reader for these discs raises ``encrypted_error``. RVZ and WIA images are not recognised here.
"""
from __future__ import annotations

import struct
from typing import Any, Dict, Optional

WII_MAGIC_AT = 0x18
WII_MAGIC = 0x5D1C9EA3


def locate(head: bytes) -> Optional[Dict[str, Any]]:
    """``{"kind": "wii", "game_id", ...}`` for a Wii disc header, or None."""
    if len(head) < 0x20 or struct.unpack_from(">I", head, WII_MAGIC_AT)[0] != WII_MAGIC:
        return None
    game_id = head[:6].decode("ascii", "replace")
    return {"kind": "wii", "game_id": game_id, "title_id": game_id, "encrypted": True, "title_kind": ""}
