"""The Archipelago quest: the seed's fixed information in the Adventure Log.

The player can check which seed and slot the save belongs to, and what ends
the game, without leaving it: a main quest, "Archipelago", started at the first
connection and completed once the goal is sent. It replaces the key item of
packs before 0.2.0 (Obj_AP_Status, cloned from Hestu's maracas).

Read in the game's files: the quests are TitleBG.pack >
Quest/QuestProduct.sbquestpack, a BYML array {Name, Type (Main, Sub: the
shrines' tab, Mini), Location, Orderer, NotPostNote, StepDependencyFlags,
Steps [{Name, MessageName, NextFlag, UpdateStep, AttentionOff}]}; their texts
Message/Msg_<lang>.product.ssarc > QuestMsg/QL_<Name>.msbt (QL_<Name>_Name and
one label per MessageName); their place a label of StaticMsg/LocationMarker.msbt;
their giver an actor, named by <Orderer>_Name in ActorType/<its profile>.msbt.
Measured (lab probe 22, 15/10): a main quest added there appears in the log,
with the game's banner ("Main Quest"), once its step's NextFlag is up; once the
second step's is, the banner says "Quest Complete" and the quest is greyed,
with its Finish text.

Everything is resources, built per seed:
  * the quest QUEST, on flags the game declares for a quest it never shipped
    (TurnTestQuest_*: saved, one-trigger, as FirstTower_*): no new GameData
    flag. Its steps: Ready (Desc), NextFlag START_FLAG; Finish (Finish),
    NextFlag FINISH_FLAG;
  * its texts, in English in every EU language: the title, the place
    ("Multiworld: <slot name>", the label LOCATION), the giver ("BOTW
    Archipelago <world version>": GIVER, declared in ActorInfo as the game's Mysterious
    Voice is, profile DemoNPC, and named in ActorType/DemoNPC.msbt; never
    created), what the quest asks (Desc) and what it says once over (Finish);
  * two idempotent entries, Demo007_1<APQuestStart> and <APQuestFinish>: the
    flag up, nothing; else Demo_FlagON. The client asks the first once per
    game connection, the second once the goal is sent.
"""
from __future__ import annotations

from pathlib import Path
import copy
import tempfile
import textwrap

import oead
from evfl.common import StringHolder
from evfl.container import Container
from evfl.entry_point import EntryPoint
from evfl.event import ActionEvent, Event, SwitchEvent
from evfl.util import Index, make_rindex

from botw_patch import byml_unshared
from botw_patch.events import graph_snapshot, read_flow, write_flow
from botw_patch.resources import ResourceBuilder, digest, unpack
from botw_patch.shop_items import ApShopItem, add_declarations, add_labels

ROOT = Path(__file__).resolve().parents[1]
QUEST = "TurnTestQuest"
START_FLAG, FINISH_FLAG = f"{QUEST}_Activated", f"{QUEST}_Finish"
START, FINISH = "APQuestStart", "APQuestFinish"
LOCATION = "APLocation"
GIVER, GIVER_MODEL = "APQuestGiver", "NPC_GodVoice"
FLOW_NAME = "Demo007_1"
TITLE = "Pack/TitleBG.pack"
BOOTUP = "Pack/Bootup.pack"
ACTOR_INFO = "Actor/ActorInfo.product.sbyml"
EVENT_INFO = "Event/EventInfo.product.sbyml"
QUEST_PACK = "Quest/QuestProduct.sbquestpack"
QUEST_MSBT = f"QuestMsg/QL_{QUEST}.msbt"
QUEST_TEMPLATE, QUEST_TEMPLATE_NAME = "QuestMsg/QL_FirstTower.msbt", "QL_FirstTower_Name"
LOCATIONS, LOCATION_MODEL = "StaticMsg/LocationMarker.msbt", "HopesPlateau"
GIVERS = "ActorType/DemoNPC.msbt"
LANGUAGES = ("EUde", "EUen", "EUes", "EUfr", "EUit", "EUnl", "EUru")
SOURCE_FILES = ("botw_patch/ap_quest.py", "botw_patch/byml_unshared.py")
# The log's text: at most 11 lines (the longest of the game's quests), of
# about 44 characters (theirs reach 50 in a proportional font).
LINES, WIDTH = 11, 44


def _input_hashes() -> dict[str, str]:
    from botw_patch.shops import INPUT_HASHES as SHOP_INPUTS
    return {ACTOR_INFO: SHOP_INPUTS[ACTOR_INFO],
            **{f"Pack/Bootup_{language}.pack": SHOP_INPUTS[f"Pack/Bootup_{language}.pack"]
               for language in LANGUAGES}}


# The update resources read here (the same versions as the shop stage's).
INPUT_HASHES = _input_hashes()

INTRO = ("A voice from beyond Hyrule speaks of a multiworld: many worlds bound together, "
         "their treasures scattered among them.")
FINISHED = ("Your goal is reached. Across the multiworld, other heroes may still be on "
            "their way: may your treasures find them.")


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def sanctum(data: dict) -> str | None:
    """What opens Ganon's sanctum (botw_patch/ganon_gate.py), only what the seed asks."""
    have, hold = [], []
    for key, what in (("sanctum_divine_beasts", "freed {} Divine Beast"),
                      ("sanctum_shrines", "completed {} shrine")):
        count = int(data.get(key, 0))
        if count:
            have.append(what.format(count) + ("s" if count > 1 else ""))
    hold += [name for key, name in (("sanctum_master_sword", "the Master Sword"),
                                    ("sanctum_runes", "the four runes")) if data.get(key)]
    if not have and not hold:
        return None
    until = ("you have " + _join(have) if have else "") + (" and " if have and hold else "") \
        + (("hold " if have else "you hold ") + _join(hold) if hold else "")
    return f"His sanctum stays sealed until {until}."


def goal(data: dict) -> str:
    """What ends the game, as the quest asks it."""
    if "goal" in data:                  # client schema 5 (botw_world/options.py)
        kind, beasts, shrines = int(data["goal"]), 4, data.get("goal_shrines", 60)
    else:
        kind = int(data.get("goal_type", 0))
        beasts, shrines = data.get("divine_beasts_required", 4), data.get("shrines_required", 40)
    if kind == 0:
        text = "Defeat Calamity Ganon in Hyrule Castle."
        seal = sanctum(data) if "goal" in data else None
        return text + (" " + seal if seal else "")
    if kind == 1:
        return ("Free the four Divine Beasts." if beasts == 4
                else f"Free {beasts} of the Divine Beasts.")
    if kind == 2:
        return f"Complete {shrines} shrine{'s' if int(shrines) != 1 else ''}."
    raise ValueError(f"unknown goal: {kind}")


def _wrap(paragraphs: list[str]) -> list[str]:
    lines: list[str] = []
    for paragraph in paragraphs:
        if lines:
            lines.append("")
        for line in paragraph.split("\n"):
            lines += textwrap.wrap(line, WIDTH) or [""]
    return lines


def texts(manifest: dict) -> dict[str, str]:
    """The quest's texts: title, place, giver, what it asks, what it says once over."""
    data = manifest.get("slot_data", {})
    facts = f"Seed {manifest['seed']}\nPlayer: {manifest['slot_name']} (slot {manifest['slot']})"
    asked = _wrap([INTRO, goal(data), facts])
    if len(asked) > LINES:              # the goal and the facts first
        asked = _wrap([goal(data), facts])
    over = _wrap([FINISHED, facts])
    for lines in (asked, over):
        if len(lines) > LINES or any(len(line) > WIDTH for line in lines):
            raise ValueError(f"quest text too long: {lines}")
    version = data.get("world_version")
    return {"title": "Archipelago", "location": f"Multiworld: {manifest['slot_name']}",
            # The version of this game's world (what the player installs), not Archipelago's.
            "giver": f"BOTW Archipelago {version}" if version else "BOTW Archipelago",
            "desc": "\n".join(asked), "finish": "\n".join(over)}


def add_quest(raw: bytes) -> tuple[bytes, dict]:
    """QUEST at the end of the game's quests: a main quest of two steps."""
    quests = oead.byml.from_binary(unpack(raw))
    if QUEST in {str(q["Name"]) for q in quests}:
        raise ValueError(f"{QUEST} already present")

    def step(name, message, flag):
        # AttentionOff would leave the attention (the "A" prompt) to the step's own actors
        # only (ksys::qst: Quest::x_6, Step's links), as the game's minigames do: with none,
        # every terminal refused the Sheikah Slate (seen in play, probes 24 and 25).
        return oead.byml.Hash({"AttentionOff": False, "MessageName": message, "Name": name,
                               "NextFlag": flag, "UpdateStep": True})
    quests.append(oead.byml.Hash({
        "Location": LOCATION, "Name": QUEST, "NotPostNote": False, "Orderer": GIVER,
        "StepDependencyFlags": oead.byml.Array([]),
        "Steps": oead.byml.Array([step("Ready", "Desc", START_FLAG),
                                  step("Finish", "Finish", FINISH_FLAG)]),
        "Type": "Main"}))
    # Every container a node of its own, as the game's file (botw_patch/byml_unshared.py).
    packed = byml_unshared.to_binary(quests)
    return ((bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else bytes(packed)),
            {"quest": QUEST, "type": "Main", "steps": [START_FLAG, FINISH_FLAG]})


def add_entries(raw: bytes) -> tuple[bytes, dict]:
    """Demo007_1<APQuestStart> and <APQuestFinish>: CheckFlag ? end : Demo_FlagON."""
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    if chart.name != FLOW_NAME:
        raise ValueError(f"unexpected flow: {chart.name}")
    names = {entry.name for entry in chart.entry_points} | {e.name for e in chart.events}
    system = next(a for a in chart.actors if str(a.identifier) == "EventSystemActor")

    def holder(collection, command):
        found = next((value for value in collection if str(value) == command), None)
        if found is None:
            found = StringHolder(command)
            collection.append(found)
        return found

    for entry_name, flag in ((START, START_FLAG), (FINISH, FINISH_FLAG)):
        if names & {entry_name, f"{entry_name}_Raise", f"{entry_name}_Up"}:
            raise ValueError(f"{entry_name} already present")
        raise_ = Event()
        raise_.name = f"{entry_name}_Raise"
        raise_.data = ActionEvent()
        raise_.data.actor = make_rindex(system)
        raise_.data.actor_action = make_rindex(holder(system.actions, "Demo_FlagON"))
        raise_.data.params = Container()
        raise_.data.params.data = {"FlagName": flag, "IsWaitFinish": True}
        raise_.data.nxt = Index()
        check = Event()
        check.name = f"{entry_name}_Up"
        check.data = SwitchEvent()
        check.data.actor = make_rindex(system)
        check.data.actor_query = make_rindex(holder(system.queries, "CheckFlag"))
        check.data.params = Container()
        check.data.params.data = {"FlagName": flag}
        # Up: nothing to do (an empty case ends the flow).
        check.data.cases = {0: make_rindex(raise_)}
        chart.events += [raise_, check]
        entry = EntryPoint(entry_name)
        entry.main_event = make_rindex(check)
        chart.entry_points.append(entry)
    out = write_flow(flow)
    after = graph_snapshot(read_flow(out))
    if any(after["events"].get(name) != node for name, node in before["events"].items()):
        raise ValueError("existing event changed")
    return out, {"entries": {START: START_FLAG, FINISH: FINISH_FLAG}}


def add_event_info(raw: bytes) -> tuple[bytes, dict]:
    """Registered like the delivery entries (the APDisplayStandalone donor)."""
    info = oead.byml.from_binary(unpack(raw))
    donor = info[f"{FLOW_NAME}<APDisplayStandalone>"]
    added = []
    for entry in (START, FINISH):
        key = f"{FLOW_NAME}<{entry}>"
        if key in info:
            raise ValueError(f"{key} already present")
        info[key] = oead.byml.Hash({field: copy.deepcopy(donor[field]) for field in (
            "demo_event", "is_timeline", "mode", "slink_user", "special_actor_name")})
        added.append(key)
    return bytes(oead.yaz0.compress(oead.byml.to_binary(info, big_endian=True))), {"added": added}


def messages(raw: bytes, quest: dict[str, str]) -> tuple[bytes, dict]:
    """A language's message archive with the quest's texts, its place and its giver."""
    archive = oead.Sarc(unpack(raw))
    writer = oead.SarcWriter.from_sarc(archive)
    if archive.get_file(QUEST_MSBT) is not None:
        raise ValueError(f"{QUEST_MSBT} already present")
    detail = {}
    writer.files[QUEST_MSBT], detail[QUEST_MSBT] = add_labels(
        bytes(archive.get_file(QUEST_TEMPLATE).data),
        {f"QL_{QUEST}_Name": quest["title"], f"QL_{QUEST}_Desc": quest["desc"],
         f"QL_{QUEST}_Finish": quest["finish"]}, QUEST_TEMPLATE_NAME)
    writer.files[LOCATIONS], detail[LOCATIONS] = add_labels(
        bytes(archive.get_file(LOCATIONS).data), {LOCATION: quest["location"]}, LOCATION_MODEL)
    writer.files[GIVERS], detail[GIVERS] = add_labels(
        bytes(archive.get_file(GIVERS).data), {f"{GIVER}_Name": quest["giver"]},
        f"{GIVER_MODEL}_Name")
    packed = bytes(writer.write()[1])
    return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else packed), detail


def generate(files: dict[str, bytes], content: Path,
             manifest: dict) -> tuple[dict[str, bytes], list[dict]]:
    """Add the quest to an overlay being built (after the delivery and shop
    stages: every resource they already changed is read from `files`)."""
    for name in (TITLE, BOOTUP, "System/Resource/ResourceSizeTable.product.srsizetable"):
        if name not in files:
            raise ValueError(f"{name} expected in the overlay")
    inputs = {}
    for name, expected in INPUT_HASHES.items():
        if name in files:           # already changed by an earlier stage
            inputs[name] = files[name]
            continue
        raw = (content / name).read_bytes()
        if digest(raw) != expected:
            raise ValueError(f"unexpected update resource: {name}")
        inputs[name] = raw
    quest = texts(manifest)
    changes: list[dict] = []
    # A file the antivirus still holds may outlive the build here: the system's
    # temporary folder takes it, rather than failing the pack.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        stage = Path(temp)
        for name, raw in {**inputs, **files}.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        builder = ResourceBuilder(stage)
        giver = ApShopItem(GIVER, None, quest["giver"], "", model_actor=GIVER_MODEL)
        builder.outputs[ACTOR_INFO], detail = add_declarations(inputs[ACTOR_INFO], [giver])
        changes.append({"resource": ACTOR_INFO, "declarations": detail})
        for language in LANGUAGES:
            builder.patch_archive(f"Pack/Bootup_{language}.pack", {
                f"Message/Msg_{language}.product.ssarc": lambda raw: messages(raw, quest)})
        builder.patch_archive(TITLE, {QUEST_PACK: add_quest,
                                      f"EventFlow/{FLOW_NAME}.bfevfl": add_entries})
        builder.patch_archive(BOOTUP, {EVENT_INFO: add_event_info})
        out = builder.finish()
        changes.extend(builder.changes)
    files = dict(files)
    files.update(out)
    return files, changes
