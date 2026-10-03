"""The Gerudo outfit, a key item: Vilia no longer sells it.

Gerudo Town's guards let Link in wearing the three pieces of the Gerudo outfit
(Armor_053_Head, _Upper, _Lower: CheckEquipArmorSeriesType GerudoCloth). In the
game, Vilia sells them at Kara Kara Bazaar: the three for 600 rupees in her quest
(Drag_Hero), then one for 200 rupees (her own flow, copied in the quest's pack).
Every one of these sales first passes a CheckRupee: this stage sets each above
what a purse can hold, so that she never sells them, and the outfit comes from the
multiworld only, as the item "Gerudo Set". Her lines are unchanged: she still
offers it, and Link never has enough.
"""
from __future__ import annotations

from botw_patch.events import graph_snapshot, read_flow, write_flow
from botw_patch.resources import digest

# The purse holds 999,999 rupees at most.
UNPAYABLE = 1_000_000
QUEST = "EventFlow/Drag_Hero.bfevfl"
VILIA = "EventFlow/Npc_SmallOasis008.bfevfl"
PACKS = {"Event/Npc_SmallOasis008.sbeventpack":
         "d8b6f8946fa5d208d67783f5540e51a44100f5116f395b18295a91e5d94756a1",
         "Event/Drag_Hero.sbeventpack":
         "bebcad3d13b95abf2723c87a3a190dba0c9ab4ef9a922912bbf36ba6aa914adf"}
# Each flow, its vanilla digest and the prices of its CheckRupee, in event order.
FLOWS = {QUEST: ("cdcfe2b38655fa75a4e74ceea75e0094f094872c5382eed60beb1af328b0e2a6", [600]),
         VILIA: ("e21f976268a8c0265fb87bf4388b34849787bfeaa7b8008e29dd0657f8c02947", [200, 200, 200])}
STAGES = {"Event/Npc_SmallOasis008.sbeventpack": (VILIA,),
          "Event/Drag_Hero.sbeventpack": (QUEST, VILIA)}
SOURCE_FILES = ("botw_patch/gerudo_outfit.py",)


def transform_for(member: str):
    expected_digest, prices = FLOWS[member]

    def transform(raw: bytes) -> tuple[bytes, list[str]]:
        if digest(raw) != expected_digest:
            raise ValueError(f"Vilia's flow changed: {member}")
        flow = read_flow(raw)
        before = graph_snapshot(flow)
        checks = [event for event in flow.flowchart.events
                  if type(event.data).__name__ == "SwitchEvent"
                  and event.data.actor_query.v.v == "CheckRupee"]
        if [event.data.params.data["Value"] for event in checks] != prices:
            raise ValueError(f"Vilia's prices changed: {member}")
        for event in checks:
            event.data.params.data["Value"] = UNPAYABLE
        after = graph_snapshot(flow)
        if before["entry_points"] != after["entry_points"] or set(before["events"]) != set(after["events"]):
            raise ValueError(f"Vilia's flow graph changed: {member}")
        return write_flow(flow), [f"{member}: {event.name} CheckRupee {price} -> {UNPAYABLE}"
                                  for event, price in zip(checks, prices)]
    return transform
