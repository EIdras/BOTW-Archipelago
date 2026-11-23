"""What the lines the project's tools print tell the launcher.

The tools report to a console: a pack build prints its steps, a play session
its client's log. A job (botw_launcher/jobs.py) reads those lines as they come
and turns the ones listed here into events for the window. This module is the
only place that knows their wording: tests/test_launcher_output.py checks each
pattern against the line its tool really prints.
"""
from __future__ import annotations

import re

# A session's client log starts each line with the time (tools/play_session.py Tee).
_TIME = r"^(?:\d\d:\d\d:\d\d )?"
PROGRESS = re.compile(r"^\s*\[(\d+)/(\d+)\]\s+(.+)$")     # tools/play_seed.py prepare

# The steps of a session, in the order a player sees them.
PACK, CEMU, ROOM, GAME = "pack", "cemu", "room", "game"
STAGES = (PACK, CEMU, ROOM, GAME)
OFFLINE, CLOSING = "offline", "closing"

_STAGE_LINES = (
    (re.compile(r"^Archipelago session: Cemu starts"), CEMU),               # tools/play_session.py run
    (re.compile(_TIME + r"connected to .+, slot "), ROOM),                   # botw_client/protocol.py
    (re.compile(_TIME + r"Archipelago reconnected"), ROOM),                  # botw_client/runtime.py
    (re.compile(_TIME + r"Archipelago (?:offline|unavailable): "), OFFLINE),
    (re.compile(_TIME + r"BOTW save bound to the AP session"), GAME),
    (re.compile(_TIME + r"Cemu closed: "), CLOSING),                         # tools/play_session.py play
)
# Items given in the game when it can take them; while some wait, the client says so every few seconds.
_WAITING = re.compile(_TIME + r"deliveries waiting \((\d+)\): ")        # botw_client/runtime.py
_COUNTED_LINES = (
    (re.compile(_TIME + r"check detected: "), "check"),                      # botw_client/runtime.py
    (re.compile(_TIME + r"item applied #"), "item"),
)


def untimed(line: str) -> str:
    """The line without the time a session's log starts it with."""
    return re.sub(_TIME, "", line, count=1)


def interpret(line: str) -> dict | None:
    """The event a printed line stands for, None for an ordinary line."""
    progress = PROGRESS.match(line)
    if progress:
        return {"event": "progress", "step": int(progress[1]), "steps": int(progress[2]),
                "label": progress[3].strip()}
    for pattern, stage in _STAGE_LINES:
        if pattern.search(line):
            return {"event": "stage", "stage": stage}
    waiting = _WAITING.search(line)
    if waiting:
        return {"event": "waiting", "count": int(waiting[1])}
    for pattern, counted in _COUNTED_LINES:
        if pattern.search(line):
            return {"event": "count", "what": counted}
    return None
