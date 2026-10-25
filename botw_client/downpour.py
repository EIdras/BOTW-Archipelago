"""The Downpour trap: rain, or a thunderstorm, over Link for a while.

The pack holds the weather (tools/build_weather_native.py): the game's own
setter, called every frame from the per-frame hook while the cave's frame count
lasts, in frames of the world (a menu should stop it), three times as many
passes of the hook at most. The client only writes which weather and for how
long (tools/cemu/mailbox.py, Cave.force_weather), in frames at the game's pace:
twice as many under FPS++ at 60 frames a second (botw_client/game_pace.py).

A death or a reload ends it (BotwClientRuntime._downpour_tick): the client
marks the downpour with the pack's volatile flag APDownpour (botw_patch/downpour.py),
which a loaded save resets, and gives the game its weather back when Link
dies or the flag is down.

Rain wets the walls: Link slides down them. The thunderstorm brings its
lightning, which strikes Link if he carries metal. Measured in the lab (probe
19, 09/10): the rain sets in within 5 to 10 s, the storm holds across a fast
travel, and the climate's weather comes back within a few seconds. Inside a
shrine, nothing shows.
"""
from __future__ import annotations

import random

FRAMES_PER_SECOND = 30
# zeldaret/botw worldDefines.h: 2 Rain, 7 ThunderRain.
RAIN = (2, 120)             # (weather type, seconds)
STORM = (7, 90)
WEATHERS = (RAIN, STORM)


def choose(rng: random.Random | None = None) -> tuple[int, int]:
    """The weather of one Downpour: (type, frames of the world)."""
    kind, seconds = (rng or random.Random()).choice(WEATHERS)
    return kind, seconds * FRAMES_PER_SECOND


def name(kind: int) -> str:
    return "thunderstorm" if kind == STORM[0] else "rain"
