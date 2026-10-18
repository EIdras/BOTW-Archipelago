"""DeathLink: the EventFlow entry that kills Link when another player dies.

OperationGuide<APDeathLink> runs the game's own damage action on the player,
GameROMPlayer.Demo_ApplyDamage {Value: quarter hearts, IsWaitFinish}, the
action of Demo331_0 (whose flow compares the player's hearts first and never
applies a lethal value). With a lethal value, measured in game:
  * Link dies at once, as in a natural death: CurrentHart 0, the game's death
    cutscene Demo006_0, the Game Over screen, then the reload of the last save;
  * the game's own protections apply: Mipha's Grace, ready, saves him (the
    received DeathLink is then spent); fairies are expected to as well.
A lower value removes hearts with no animation and no sound.

The entry marks its own deaths: it sets the volatile flag APDeathLinkKill,
applies the damage, then clears the flag only if Link is still alive
(EventSystemActor.ComparePlayerHeart, as Demo331_0 uses it). A death that
finds the flag set is the received DeathLink's, never sent back; the flag,
not saved, is gone after the reload that follows the death.

The entry is registered as the game's background events are
(delivery_flow.QUIET_EVENT_INFO): it pauses nothing and leaves the HUD alone.
OperationGuide declares only EventSystemActor, so the player is declared as
Demo007_1 declares it. Every pack has the entry; the client requests it only
when the seed has DeathLink on.

The pack also carries the English names of the actors that can kill Link
(attacker_names), read from the player's own game files: the client names the
last attacker in the DeathLink it sends.
"""
from __future__ import annotations

import re

import oead
from evfl.actor import Actor, ActorIdentifier
from evfl.common import StringHolder
from evfl.container import Container
from evfl.entry_point import EntryPoint
from evfl.event import ActionEvent, Event, SwitchEvent
from evfl.util import Index, make_rindex

from botw_patch.delivery_flow import PLAYER, PLAYER_PARAMS, QUIET_EVENT_INFO, QUIET_FLOW
from botw_patch.events import graph_snapshot, read_flow, write_flow
from botw_patch.resources import unpack
from botw_patch.shop_items import read_labels

ENTRY = "APDeathLink"
FLOW_NAME = QUIET_FLOW
# Quarter hearts: above any life (30 hearts and 10 extra hearts are 160).
LETHAL_DAMAGE = 1000
EVENT_INFO = "Event/EventInfo.product.sbyml"
GAMEDATA = "GameData/gamedata.ssarc"
FLAG = "APDeathLinkKill"
MESSAGES = "Pack/Bootup_EUen.pack"
MESSAGE_ARCHIVE = "Message/Msg_EUen.product.ssarc"
# The message files naming what can hurt Link (<actor>_Name labels).
NAME_FILES = ("Enemy", "GelEnemy", "GiantEnemy", "Guardian", "Sandworm", "Swarm", "Dragon",
              "SiteBoss", "LastBoss", "Prey", "Bullet")


def add_entry(raw: bytes) -> tuple[bytes, list[str]]:
    """OperationGuide<APDeathLink>: flag on, one lethal Demo_ApplyDamage on the
    player, then the flag off if Link survived."""
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    if chart.name != FLOW_NAME:
        raise ValueError(f"unexpected flow: {chart.name}")
    names = {entry.name for entry in chart.entry_points} | {e.name for e in chart.events}
    if ENTRY in names:
        raise ValueError(f"{ENTRY} already present")
    system = next(a for a in chart.actors if str(a.identifier) == "EventSystemActor")
    player = next((a for a in chart.actors
                   if (a.identifier.name, a.identifier.sub_name) == PLAYER), None)
    if player is None:
        player = Actor()
        player.identifier = ActorIdentifier(*PLAYER)
        player.params = Container()
        player.params.data = dict(PLAYER_PARAMS)
        player.concurrent_clips = 1
        chart.actors.append(player)

    def holder(collection, name):
        found = next((value for value in collection if str(value) == name), None)
        if found is None:
            found = StringHolder(name)
            collection.append(found)
        return found

    def action(name, actor, command, params, nxt=None):
        event = Event()
        event.name = name
        event.data = ActionEvent()
        event.data.actor = make_rindex(actor)
        event.data.actor_action = make_rindex(holder(actor.actions, command))
        event.data.params = Container()
        event.data.params.data = params
        event.data.nxt = make_rindex(nxt) if nxt is not None else Index()
        chart.events.append(event)
        return event

    clear = action(f"{ENTRY}_Survived", system, "Demo_FlagOFF",
                   {"FlagName": FLAG, "IsWaitFinish": True})
    alive = Event()
    alive.name = f"{ENTRY}_Alive"
    alive.data = SwitchEvent()
    alive.data.actor = make_rindex(system)
    alive.data.actor_query = make_rindex(holder(system.queries, "ComparePlayerHeart"))
    alive.data.params = Container()
    alive.data.params.data = {"Threshold": 1}
    # 1: at least one quarter heart left. 0 (dead): the flag stays set.
    alive.data.cases = {1: make_rindex(clear)}
    chart.events.append(alive)
    hit = action(f"{ENTRY}_Hit", player, "Demo_ApplyDamage",
                 {"IsWaitFinish": True, "Value": LETHAL_DAMAGE}, alive)
    mark = action(ENTRY, system, "Demo_FlagON", {"FlagName": FLAG, "IsWaitFinish": True}, hit)
    if names & {e.name for e in (clear, alive, hit)}:
        raise ValueError("DeathLink event already present")
    entry = EntryPoint(ENTRY)
    entry.main_event = make_rindex(mark)
    chart.entry_points.append(entry)
    out = write_flow(flow)
    after = graph_snapshot(read_flow(out))
    if any(after["events"].get(name) != node for name, node in before["events"].items()):
        raise ValueError("existing event changed")
    if after["entry_points"][:len(before["entry_points"])] != before["entry_points"]:
        raise ValueError("existing entry points changed")
    return out, [f"{FLOW_NAME}<{ENTRY}>: {FLAG} on, GameROMPlayer.Demo_ApplyDamage "
                 f"{LETHAL_DAMAGE}, {FLAG} off if Link survived"]


def add_event_info(raw: bytes) -> tuple[bytes, list[str]]:
    info = oead.byml.from_binary(unpack(raw))
    key = f"{FLOW_NAME}<{ENTRY}>"
    if key in info:
        raise ValueError(f"EventInfo already present: {key}")
    info[key] = oead.byml.Hash(QUIET_EVENT_INFO)
    packed = oead.byml.to_binary(info, big_endian=True)
    return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else bytes(packed)), [
        f"register {key} as a background event"]


def add_flag(raw: bytes) -> tuple[bytes, list[str]]:
    """The volatile bool APDeathLinkKill in the game's GameData definitions."""
    from tools.build_game_data_mod import modify_gamedata_flags
    return (modify_gamedata_flags(raw, (FLAG,), is_save=False, kind="bool"),
            [f"register volatile bool {FLAG}"])


def plain(text: str) -> str:
    """A message text without its control tags (U+000E, group, type, size, data)."""
    out, i = [], 0
    while i < len(text):
        char = text[i]
        if char == "\x0e" and i + 3 < len(text):
            i += 4 + ord(text[i + 3]) // 2
            continue
        if char not in "\x00\x0f":
            out.append(char)
        i += 1
    return "".join(out).strip()


def attacker_names(messages_pack: bytes, language: str = "EUen") -> dict[str, str]:
    """{actor: English name} of every actor named in NAME_FILES, from the
    English message archive of the game's version (`language`)."""
    archive = oead.Sarc(unpack(bytes(oead.Sarc(unpack(messages_pack)).get_file(
        f"Message/Msg_{language}.product.ssarc").data)))
    names = {}
    for name in NAME_FILES:
        member = archive.get_file(f"ActorType/{name}.msbt")
        if member is None:
            raise ValueError(f"missing message file: ActorType/{name}.msbt")
        for label, text in read_labels(bytes(member.data)).items():
            # "Stone Talus (Rare)" reads "Stone Talus" in a sentence.
            name = re.sub(r"\s*\([^)]*\)$", "", plain(text))
            if label.endswith("_Name") and name:
                names[label[:-len("_Name")]] = name
    return dict(sorted(names.items()))
