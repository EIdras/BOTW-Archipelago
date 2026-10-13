"""The Downpour trap's mark in the game's GameData: the volatile bool APDownpour.

The pack holds the trap's weather from its per-frame hook
(tools/build_weather_native.py), in the cave: a reload of the game would not end it.
A death or a reload ends it: the client sets APDownpour when the downpour begins
(botw_client/downpour.py), and gives the game its weather back when Link dies, or
when the flag is down again. Not saved, the flag goes back to false whenever a
save is loaded (as APDeathLinkKill after the reload that follows a death,
botw_patch/death_link.py), and keeps its value across a fast travel, which loads
no save.
"""
from __future__ import annotations

GAMEDATA = "GameData/gamedata.ssarc"
FLAG = "APDownpour"


def add_flag(raw: bytes) -> tuple[bytes, list[str]]:
    """The volatile bool APDownpour in the game's GameData definitions."""
    from tools.build_game_data_mod import modify_gamedata_flags
    return (modify_gamedata_flags(raw, (FLAG,), is_save=False, kind="bool"),
            [f"register volatile bool {FLAG}"])
