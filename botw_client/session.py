"""Stable, signed-s32 identity for a native AP save and its resource build."""
from __future__ import annotations

import hashlib
import json


def session_token(identity: tuple[str, int, int, str]) -> int:
    seed, team, slot, checksum = identity
    if (not isinstance(seed, str) or not seed or not isinstance(team, int)
            or team < 0 or not isinstance(slot, int) or slot < 1
            or not isinstance(checksum, str) or not checksum):
        raise ValueError("incomplete AP seed/team/slot/DataPackage identity")
    encoded = json.dumps(identity, ensure_ascii=False).encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:4], "big") & 0x7FFFFFFF or 1
