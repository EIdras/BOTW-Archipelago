"""Traps: the EventFlow entries behind the Archipelago trap items.

Each trap is an entry of the resident OperationGuide, registered as the game's
background events are (delivery_flow.QUIET_EVENT_INFO): it pauses nothing and
leaves the HUD alone. The Blood Moon is the exception: a cutscene can only be
called from a demo event, so its entry lives in Demo007_1, the campfire rest,
registered as the rest's sub-flow is (DEMO_HOST_INFO). A received trap item
calls its entry as a sub-flow of its delivery entry (delivery_flow.py), once the
delivery is committed; the entries can also be requested alone.

What each one does, with the game's own actions and queries:
  * Weapon Shatter  the melee weapon in Link's hand is deleted from the pouch,
    Demo_DeletePorchItemInEquip, once CheckEquipment names it (the game's flows
    delete an item by name only), then the weapon slot is unequipped. The Master
    Sword is left alone: it never breaks. Link with empty hands loses nothing.
  * Blood Moon  the Blood Moon cutscene Demo011_0 is called at once, as the
    campfire rest calls it after the time has passed, and WorldMgr at a midnight (zeldamods.org, WorldMgr: "Midnight checks"): it
    contains Demo_OffWaitRevival, which resets the revival flags, so the monsters
    and the weapons on the ground come back (zeldamods.org, Blood moon). The
    Blood Moon timer WM_BloodyMoonTimer goes back to 0, as the game does. Where
    WorldMgr would not allow a Blood Moon (BloodyMoonProhibition, or not in the
    main field: shrines, Divine Beasts...), the next midnight is one instead:
    WM_BloodyDay is set, and the end reserve timer (WM_bloodyEndReserveTimer),
    which clears that flag five game minutes after a midnight, is zeroed first.
  * Rupoor  Demo_IncreaseRupee takes RUPOOR_RUPEES, or the largest of the
    RUPOOR_STEPS the purse holds (CheckRupee, as the game's own payments do).
  * Hearts Down  Demo_ApplyDamage takes HEARTS_DOWN quarter hearts, or all but
    a quarter when Link has fewer (ComparePlayerHeart, the ladder of Demo331_0):
    never lethal.
  * Strip Down  Demo_SwitchPlayerEquipment puts Link's weapon, shield, bow and
    armor back in the pouch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import oead
from evfl.actor import Actor, ActorIdentifier
from evfl.common import StringHolder
from evfl.container import Container
from evfl.entry_point import EntryPoint
from evfl.event import ActionEvent, Event, SwitchEvent
from evfl.util import make_rindex

from botw_patch.delivery_flow import (FLOW_NAME, PLAYER, PLAYER_PARAMS, QUIET_EVENT_INFO,
                                      QUIET_FLOW)
from botw_patch.events import graph_snapshot, read_flow, write_flow
from botw_patch.melee_weapons import MELEE_WEAPONS
from botw_patch.resources import unpack

EVENT_INFO = "Event/EventInfo.product.sbyml"
# Rupoor: the purse is searched from the largest step down.
RUPOOR_STEPS = (1, 5, 10, 20, 50, 100)
RUPOOR_RUPEES = RUPOOR_STEPS[-1]
# Hearts Down, in quarter hearts: two hearts.
HEARTS_DOWN = 8
BLOOD_MOON_DEMO = "Demo011_0"
BLOOD_MOON_TIMER = "WM_BloodyMoonTimer"
BLOOD_MOON_FLAG = "WM_BloodyDay"
BLOOD_MOON_RESERVE = "WM_bloodyEndReserveTimer"
BLOOD_MOON_PROHIBITION = "BloodyMoonProhibition"
# The campfire rest's sub-flow, which calls Demo011_0 (measured: the cutscene
# called from an OperationGuide background event froze Cemu; from Demo007_1 with
# this EventInfo, it plays and the monsters come back).
DEMO_HOST_INFO = f"{FLOW_NAME}<{FLOW_NAME}_Sub>"
EQUIPMENT_SLOTS = ("Weapon", "Shield", "Bow", "ArmorHead", "ArmorUpper", "ArmorLower")


def equipment(*unequipped: str) -> dict:
    """Demo_SwitchPlayerEquipment parameters that unequip the given slots and
    name no item to equip (the game's own flows do the same, e.g. ShieldofKolog)."""
    unknown = set(unequipped) - set(EQUIPMENT_SLOTS)
    if unknown:
        raise ValueError(f"unknown equipment slot: {sorted(unknown)}")
    params = {"IsWaitFinish": True, "PorchItemName_Arrow": ""}
    for slot in EQUIPMENT_SLOTS:
        params[f"Unequip{slot}"] = slot in unequipped
        params[f"PorchItemName_{slot}"] = ""
    return params


class Builder:
    """Appends the events of one entry to the flowchart, under the entry's name."""

    def __init__(self, chart, entry: str, names: set[str]):
        self.chart, self.entry, self.names = chart, entry, names
        self.system = next(a for a in chart.actors if str(a.identifier) == "EventSystemActor")
        self.player = next((a for a in chart.actors
                            if (a.identifier.name, a.identifier.sub_name) == PLAYER), None)
        if self.player is None:
            self.player = Actor()
            self.player.identifier = ActorIdentifier(*PLAYER)
            self.player.params = Container()
            self.player.params.data = dict(PLAYER_PARAMS)
            self.player.concurrent_clips = 1
            chart.actors.append(self.player)

    @staticmethod
    def _holder(collection, name):
        found = next((value for value in collection if str(value) == name), None)
        if found is None:
            found = StringHolder(name)
            collection.append(found)
        return found

    def _name(self, label: str) -> str:
        name = f"{self.entry}_{label}"
        if name in self.names:
            raise ValueError(f"event name already present: {name}")
        self.names.add(name)
        return name

    def action(self, label, actor, command, params, nxt=None):
        event = Event()
        event.name = self._name(label)
        event.data = ActionEvent()
        event.data.actor = make_rindex(actor)
        event.data.actor_action = make_rindex(self._holder(actor.actions, command))
        event.data.params = Container()
        event.data.params.data = params
        if nxt is not None:
            event.data.nxt = make_rindex(nxt)
        self.chart.events.append(event)
        return event

    def switch(self, label, query, params, cases):
        """A query on EventSystemActor; cases maps a result to an event, or to
        None, which ends the entry."""
        event = Event()
        event.name = self._name(label)
        event.data = SwitchEvent()
        event.data.actor = make_rindex(self.system)
        event.data.actor_query = make_rindex(self._holder(self.system.queries, query))
        event.data.params = Container()
        event.data.params.data = params
        event.data.cases = {case: make_rindex(target) for case, target in cases.items()
                            if target is not None}
        self.chart.events.append(event)
        return event


def weapon_shatter(b: Builder, unequip: bool = True):
    after = (b.action("Unequip", b.system, "Demo_SwitchPlayerEquipment", equipment("Weapon"))
             if unequip else None)
    check = None
    for number, weapon in reversed(list(enumerate(MELEE_WEAPONS))):
        delete = b.action(f"Delete{number}", b.system, "Demo_DeletePorchItemInEquip",
                          {"IsWaitFinish": True, "DeleteNum": 1, "PorchItemName": weapon}, after)
        check = b.switch(f"Holds{number}", "CheckEquipment", {"EquipItemName": weapon},
                         {1: delete, 0: check})
    return check


def blood_moon(b: Builder):
    flag = b.action("Flag", b.system, "Demo_FlagON",
                    {"FlagName": BLOOD_MOON_FLAG, "IsWaitFinish": True})
    schedule = b.action("Reserve", b.system, "Demo_SetGameDataInt",
                        {"GameDataIntName": BLOOD_MOON_RESERVE, "Value": 0, "IsWaitFinish": True},
                        flag)
    demo = b.action("Demo", b.system, "Demo_CallDemo",
                    {"DemoName": BLOOD_MOON_DEMO, "EntryPointName": BLOOD_MOON_DEMO,
                     "IsWaitFinish": True, "EndFade": 0})
    timer = b.action("Timer", b.system, "Demo_SetGameDataFloat",
                     {"GameDataFloatName": BLOOD_MOON_TIMER, "Value": 0.0, "IsWaitFinish": True},
                     demo)
    field = b.switch("Field", "IsCurrentMainFieldStage", {}, {1: timer, 0: schedule})
    return b.switch("Prohibited", "CheckFlag", {"FlagName": BLOOD_MOON_PROHIBITION},
                    {1: schedule, 0: field})


def rupoor(b: Builder):
    check = None
    for amount in RUPOOR_STEPS:
        pay = b.action(f"Pay{amount}", b.system, "Demo_IncreaseRupee",
                       {"Value": -amount, "IsWaitFinish": False})
        check = b.switch(f"Has{amount}", "CheckRupee", {"Value": amount}, {1: pay, 0: check})
    return check


def hearts_down(b: Builder):
    check = None
    # At least `quarters` + 1 quarter hearts: take `quarters`, and Link lives.
    for quarters in range(1, HEARTS_DOWN + 1):
        hit = b.action(f"Hit{quarters}", b.player, "Demo_ApplyDamage",
                       {"IsWaitFinish": True, "Value": quarters})
        check = b.switch(f"Has{quarters + 1}", "ComparePlayerHeart", {"Threshold": quarters + 1},
                         {1: hit, 0: check})
    return check


def strip_down(b: Builder):
    return b.action("Strip", b.system, "Demo_SwitchPlayerEquipment", equipment(*EQUIPMENT_SLOTS))


@dataclass(frozen=True)
class Trap:
    item: str                           # the Archipelago item
    entry: str                          # its entry point in `host`
    build: Callable[[Builder], Event]   # builds its events, returns the first
    host: str = QUIET_FLOW


TRAPS = (
    Trap("Weapon Shatter", "APTrapWeaponShatter", weapon_shatter),
    Trap("Blood Moon", "APTrapBloodMoon", blood_moon, FLOW_NAME),
    Trap("Rupoor", "APTrapRupoor", rupoor),
    Trap("Hearts Down", "APTrapHeartsDown", hearts_down),
    Trap("Strip Down", "APTrapStripDown", strip_down),
)


def add_entries(raw: bytes, host: str = QUIET_FLOW) -> tuple[bytes, list[str]]:
    """The flowchart `host` with the entry of every trap it hosts added."""
    hosted = [trap for trap in TRAPS if trap.host == host]
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    if chart.name != host:
        raise ValueError(f"unexpected flow: {chart.name}")
    names = {e.name for e in chart.entry_points} | {e.name for e in chart.events}
    if any(trap.entry in names for trap in hosted):
        raise ValueError("trap entry already present")
    for trap in hosted:
        first = trap.build(Builder(chart, trap.entry, names))
        entry = EntryPoint(trap.entry)
        entry.main_event = make_rindex(first)
        chart.entry_points.append(entry)
    out = write_flow(flow)
    after = graph_snapshot(read_flow(out))
    if any(after["events"].get(name) != node for name, node in before["events"].items()):
        raise ValueError("existing event changed")
    if after["entry_points"][:len(before["entry_points"])] != before["entry_points"]:
        raise ValueError("existing entry points changed")
    return out, [f"{host}<{trap.entry}>: {trap.item}" for trap in hosted]


def demo_host_info(info) -> oead.byml.Hash:
    """A copy of DEMO_HOST_INFO's EventInfo (demo event, its cutscene children)."""
    return oead.byml.from_text(oead.byml.to_text(info[DEMO_HOST_INFO]))


def add_event_info(raw: bytes) -> tuple[bytes, list[str]]:
    """The traps' entries registered: background events, or the rest's sub-flow."""
    info = oead.byml.from_binary(unpack(raw))
    keys = {f"{trap.host}<{trap.entry}>": trap for trap in TRAPS}
    present = [key for key in keys if key in info]
    if present:
        raise ValueError(f"EventInfo already present: {present}")
    for key, trap in keys.items():
        info[key] = (oead.byml.Hash(QUIET_EVENT_INFO) if trap.host == QUIET_FLOW
                     else demo_host_info(info))
    packed = oead.byml.to_binary(info, big_endian=True)
    return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else bytes(packed)), [
        f"register {len(keys)} trap entries"]
