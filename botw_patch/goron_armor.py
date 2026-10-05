"""The Flamebreaker set, a key item: Goron City's armor shop no longer sells it.

Death Mountain's heat needs flame resistance (the item "Flamebreaker Set"),
which the multiworld alone must give. In the game, the shop "Ripped and
Shredded" (Npc_goron004) sells its three pieces on mannequins
(Mannequin_005_Head, _Upper, _Lower in G-2, linked to him by ForSale): buying
one runs his entry ClerkAsk, InitTalkSell then DisplayShop<Armor>, the shared
3D sale of every armor shop. This stage changes his own flow only (one copy, in
his event pack): after InitTalkSell he answers with his own sold-out line
(talk10, "We're actually all sold out!"), framed as DisplayShop<Armor>'s
refusal is (Demo_NoDeleteCurrent first, Demo_ExitEventPlayer last), so the
mannequin stays and nothing is sold. His talk (buying from Link included) is
unchanged. The other pieces found in the game are lent for a trial and taken
back with its pouch (the Champions' Ballad, a chest of the Trial of the Sword);
Kima's gift is waited out by botw_patch/build.py.
"""
from __future__ import annotations

from evfl.event import SubFlowEvent
from evfl.util import Index

from botw_patch.events import add_action_after, graph_snapshot, read_flow, write_flow
from botw_patch.resources import digest

PACK = "Event/Npc_goron004.sbeventpack"
PACKS = {PACK: "bb7fc521a7e0d36940c84faac55cd491e1891ff52f4daa0fb9acab5b489c8b5e"}
FLOW = "EventFlow/Npc_goron004.bfevfl"
FLOW_SHA = "f6d0ad3a7cacce7ddd6eac63b6b7f083425eb4f48f22bec50482e8f2f5f30d7f"
MERCHANT = "Npc_goron004"
ENTRY = "ClerkAsk"
GREETING = "Event9"          # InitTalk<InitTalkSell_ReturnArrivalAnchor>
SALE = "Event66"             # DisplayShop<Armor>
SOLD_OUT = "Event49"         # his talk10, said when the shop is sold out
SOURCE_FILES = ("botw_patch/goron_armor.py",)


def transform(raw: bytes) -> tuple[bytes, list[str]]:
    if digest(raw) != FLOW_SHA:
        raise ValueError("Goron City's armor shop flow changed")
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    events = {event.name: event for event in chart.events}
    entry = next(e for e in chart.entry_points if e.name == ENTRY)
    greeting, sale = events[GREETING], events[SALE]
    sales = [e.name for e in chart.events
             if isinstance(e.data, SubFlowEvent) and e.data.res_flowchart_name == "DisplayShop"]
    if (entry.main_event.v.name != GREETING or greeting.data.nxt.v.name != SALE
            or sales != [SALE] or sale.data.entry_point_name != "Armor"):
        raise ValueError("Goron City's armor sale changed")
    line = dict(events[SOLD_OUT].data.params.data)
    if line.get("MessageId") != f"EventFlowMsg/{MERCHANT}:talk10":
        raise ValueError("Goron City's sold-out line changed")

    add_action_after(flow, GREETING, "APSoldOut_Keep", "EventSystemActor",
                     "Demo_NoDeleteCurrent", {"IsWaitFinish": True})
    add_action_after(flow, "APSoldOut_Keep", "APSoldOut_Talk", MERCHANT, "Demo_Talk", line)
    add_action_after(flow, "APSoldOut_Talk", "APSoldOut_Exit", "EventSystemActor",
                     "Demo_ExitEventPlayer", {"IsWaitFinish": True})
    next(e for e in chart.events if e.name == "APSoldOut_Exit").data.nxt = Index()

    after = graph_snapshot(flow)
    added = {"APSoldOut_Keep", "APSoldOut_Talk", "APSoldOut_Exit"}
    if (set(after["events"]) - set(before["events"]) != added
            or any(after["events"][name] != node for name, node in before["events"].items()
                   if name != GREETING)
            or after["entry_points"] != before["entry_points"]):
        raise ValueError("Goron City's armor shop changed beyond the sale")
    return write_flow(flow), [f"{FLOW}: {ENTRY} says the sold-out line instead of DisplayShop<Armor>"]
