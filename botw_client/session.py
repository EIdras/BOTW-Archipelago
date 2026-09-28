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


def data_package_checksum(game: str, item_name_by_id: dict[int, str],
                          location_id_by_name: dict[str, int]) -> str:
    """The client's checksum of a game's DataPackage (item ids, location ids).

    The world writes the same one into its slot file at generation
    (botw_world generate_output), so a pack can be bound to its seed from
    that file alone, before any server is reached."""
    payload = {"game": game, "items": {int(k): v for k, v in item_name_by_id.items()},
               "locations": {k: int(v) for k, v in location_id_by_name.items()}}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
