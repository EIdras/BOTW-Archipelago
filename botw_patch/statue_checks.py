"""The Goddess Statues' trades as locations (the world's spirit_orbs on statue_checks).

Every Goddess Statue runs one flow, Demo034_0, whose only copy is the update's
Event/Demo034_0.sbeventpack. Its entry GetMatome makes the trade chosen in GetUtuwa:
the four Spirit Orbs taken (Demo_IncreaseNumDungeonClrSeal -4), then the heart
container or the stamina vessel given (GIFT, the subflow GetDemo:GetItemByName on the
CheckTargetActorName argument), the argument flag IsGet_Utuwa, and COUNTER raised by
four. Both branches of the first trade's flag (FirstGetUtsuwaFlag) reach GIFT.

This stage makes GIFT a one-frame wait: the statue takes the orbs, counts the trade
and plays its scene, and gives nothing. The client reads COUNTER: the k-th trade is
offering k, whose item the multiworld gives (botw_client/locations.py).
"""
from __future__ import annotations

from pathlib import Path
import tempfile

from evfl.event import ActionEvent, SubFlowEvent

ARCHIVE = "Event/Demo034_0.sbeventpack"
FLOW_NAME = "Demo034_0"
GIFT = "Event501"
COUNTER = "Npc_Goddess_UtuwaSum"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
# The world's spirit_orbs value whose trades are locations.
STATUE_CHECKS = 2
SOURCE_FILES = ("botw_patch/statue_checks.py",)


def enabled(status: dict | None) -> bool:
    """The slot's statue trades are locations (the world's spirit_orbs on statue_checks)."""
    return bool(status and int(status.get("slot_data", {}).get("spirit_orbs", 0)) == STATUE_CHECKS)


def _gives(event) -> bool:
    data = event.data
    return (isinstance(data, SubFlowEvent) and data.res_flowchart_name == "GetDemo"
            and data.entry_point_name == "GetItemByName")


def transform(raw: bytes) -> tuple[bytes, dict]:
    """Demo034_0 with GIFT a wait, checked against what was studied."""
    from botw_patch.events import read_flow, wait_instead, write_flow
    flow = read_flow(raw)
    if flow.flowchart.name != FLOW_NAME:
        raise ValueError(f"expected the flow {FLOW_NAME}")
    gifts = [event for event in flow.flowchart.events if _gives(event)]
    if [event.name for event in gifts] != [GIFT]:
        raise ValueError(f"{FLOW_NAME}: GetItemByName in {[event.name for event in gifts]}, not {GIFT} alone")
    # GIFT, the argument flag, then the trade counted.
    event, path = gifts[0], []
    while len(path) < 3 and not (isinstance(event.data, ActionEvent)
                                 and str(event.data.actor_action.v) == "Demo_IncreaseGameDataInt"):
        event = event.data.nxt.v
        path.append(event.name)
    params = event.data.params.data if isinstance(event.data, ActionEvent) and event.data.params else {}
    if params.get("GameDataIntName") != COUNTER or params.get("Value") != 4:
        raise ValueError(f"{FLOW_NAME}: {GIFT} is not followed by {COUNTER} + 4 ({path})")
    wait_instead(flow, gifts[0])
    return write_flow(flow), {"wait": GIFT, "counter": COUNTER}


def generate(files: dict[str, bytes], content) -> tuple[dict[str, bytes], list[dict]]:
    """The statue flow with its gift a wait (the size table is read from `files`).
    content: the update folder, or the game's files (botw_patch/game_files.py)."""
    from botw_patch.game_files import GameFiles
    from botw_patch.resources import ResourceBuilder
    game = GameFiles.of(content)
    if TABLE not in files:
        raise ValueError(f"{TABLE} expected in the overlay")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        stage = Path(temp)
        for name in (ARCHIVE, TABLE):
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(files[name] if name in files else game.read(name))
        builder = ResourceBuilder(stage)
        builder.patch_archive(ARCHIVE, {f"EventFlow/{FLOW_NAME}.bfevfl": transform})
        out = builder.finish()
    files = dict(files)
    files.update(out)
    return files, builder.changes
