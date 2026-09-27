"""The Archipelago key item: the seed's fixed information in the inventory.

The player can check which seed and slot the save belongs to without
leaving the game. Everything is resources, built per seed:
  * one key item actor, Obj_AP_Status, cloned from Hestu's maracas (a key item
    with no use): ActorInfo declaration, actor pack with its ActorLink
    renamed, the Archipelago icon (UI/StockItem/<actor>.sbitemico);
  * its name and description (English, in every EU language), the seed's fixed facts:
    seed, slot, goal;
  * one idempotent EventFlow entry, Demo007_1<APStatusItem>: if the pouch
    does not hold the item, put it there. No cursor, no guard: granting it
    twice is impossible and missing it only waits for the next request. The
    client asks for it once per game connection.
"""
from __future__ import annotations

from pathlib import Path
import copy
import tempfile

import oead
from evfl.common import StringHolder
from evfl.container import Container
from evfl.entry_point import EntryPoint
from evfl.event import ActionEvent, Event, SwitchEvent
from evfl.util import Index, make_rindex

from botw_patch.events import graph_snapshot, read_flow, write_flow
from botw_patch.resources import ResourceBuilder, digest, unpack
from botw_patch.shop_items import (DESCRIPTION_LINES, DESCRIPTION_WIDTH, MSBT, ApShopItem,
                                   add_declarations, add_item_texts, clone_actor_pack)

ROOT = Path(__file__).resolve().parents[1]
ACTOR = "Obj_AP_Status"
MODEL_ACTOR = "Obj_Maracas"
ENTRY = "APStatusItem"
FLOW_NAME = "Demo007_1"
TITLE = "Pack/TitleBG.pack"
BOOTUP = "Pack/Bootup.pack"
ACTOR_INFO = "Actor/ActorInfo.product.sbyml"
EVENT_INFO = "Event/EventInfo.product.sbyml"
MODEL_PACK = f"Actor/Pack/{MODEL_ACTOR}.sbactorpack"
MODEL_PACK_SHA256 = "c52f3ba97d77aaf25f8aa2d435acf7f850a679d2fe6b85768b69205a275b8241"
ICON = ROOT / "assets/wiiu/Item_AP.sbitemico"
ICON_TABLE_MARGIN = 8192
LANGUAGES = ("EUde", "EUen", "EUes", "EUfr", "EUit", "EUnl", "EUru")
SOURCE_FILES = ("botw_patch/status_item.py", "assets/wiiu/Item_AP.sbitemico")


def _input_hashes() -> dict[str, str]:
    from botw_patch.shops import INPUT_HASHES as SHOP_INPUTS
    return {MODEL_PACK: MODEL_PACK_SHA256, ACTOR_INFO: SHOP_INPUTS[ACTOR_INFO],
            **{f"Pack/Bootup_{language}.pack": SHOP_INPUTS[f"Pack/Bootup_{language}.pack"]
               for language in LANGUAGES}}


# The update resources read here (the same versions as the shop stage's).
INPUT_HASHES = _input_hashes()

GOALS = {0: "defeat Ganon", 1: "free {beasts} Divine Beasts",
         2: "complete {shrines} shrines"}


def texts(manifest: dict) -> tuple[str, str]:
    """(name, description): the seed's fixed facts, in English in every language."""
    data = manifest.get("slot_data", {})
    goal = int(data.get("goal_type", 0))
    values = {"beasts": data.get("divine_beasts_required", 4),
              "shrines": data.get("shrines_required", 40)}
    goals = GOALS
    if goal not in goals:
        raise ValueError(f"unknown goal: {goal}")
    slot = f"{manifest['slot_name']} (slot {manifest['slot']})"
    lines = [f"Seed {manifest['seed']}", f"Player: {slot}",
             f"Goal: {goals[goal].format(**values)}"]
    if len(lines) > DESCRIPTION_LINES or any(len(line) > DESCRIPTION_WIDTH for line in lines):
        raise ValueError(f"status description too long: {lines}")
    return "Archipelago", "\n".join(lines)


def item(manifest: dict) -> ApShopItem:
    return ApShopItem(ACTOR, -1, *texts(manifest), model_actor=MODEL_ACTOR)


def add_status_entry(raw: bytes) -> tuple[bytes, dict]:
    """Demo007_1<APStatusItem>: HasPorchItem ? end : Demo_SetItemDataToPouch."""
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    if chart.name != FLOW_NAME:
        raise ValueError(f"unexpected flow: {chart.name}")
    if ENTRY in {entry.name for entry in chart.entry_points}:
        raise ValueError(f"{ENTRY} already present")
    system = next(a for a in chart.actors if str(a.identifier) == "EventSystemActor")

    def holder(collection, command):
        found = next((value for value in collection if str(value) == command), None)
        if found is None:
            found = StringHolder(command)
            collection.append(found)
        return found

    grant = Event()
    grant.name = f"{ENTRY}_Grant"
    grant.data = ActionEvent()
    grant.data.actor = make_rindex(system)
    grant.data.actor_action = make_rindex(holder(system.actions, "Demo_SetItemDataToPouch"))
    grant.data.params = Container()
    grant.data.params.data = {"IsWaitFinish": False, "TargetActorName": ACTOR}
    grant.data.nxt = Index()
    check = Event()
    check.name = f"{ENTRY}_Held"
    check.data = SwitchEvent()
    check.data.actor = make_rindex(system)
    check.data.actor_query = make_rindex(holder(system.queries, "HasPorchItem"))
    check.data.params = Container()
    check.data.params.data = {"Count": 1, "PorchItemName": ACTOR}
    # Held: nothing to do (an empty case ends the flow).
    check.data.cases = {0: make_rindex(grant)}
    if any(e.name in (grant.name, check.name) for e in chart.events):
        raise ValueError("status event already present")
    chart.events += [grant, check]
    entry = EntryPoint(ENTRY)
    entry.main_event = make_rindex(check)
    chart.entry_points.append(entry)
    out = write_flow(flow)
    after = graph_snapshot(read_flow(out))
    if any(after["events"].get(name) != node for name, node in before["events"].items()):
        raise ValueError("existing event changed")
    return out, {"entry": ENTRY, "grants": ACTOR}


def add_event_info(raw: bytes) -> tuple[bytes, dict]:
    """Registered like the delivery entries (the APDisplayStandalone donor)."""
    info = oead.byml.from_binary(unpack(raw))
    donor = info[f"{FLOW_NAME}<APDisplayStandalone>"]
    key = f"{FLOW_NAME}<{ENTRY}>"
    if key in info:
        raise ValueError(f"{key} already present")
    info[key] = oead.byml.Hash({field: copy.deepcopy(donor[field]) for field in (
        "demo_event", "is_timeline", "mode", "slink_user", "special_actor_name")})
    return bytes(oead.yaz0.compress(oead.byml.to_binary(info, big_endian=True))), {"added": key}


def generate(files: dict[str, bytes], content: Path,
             manifest: dict) -> tuple[dict[str, bytes], list[dict]]:
    """Add the status item to an overlay being built (after the delivery and
    shop stages: every resource they already changed is read from `files`)."""
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
    model_pack = inputs.pop(MODEL_PACK)
    status = item(manifest)
    changes: list[dict] = []
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        for name, raw in {**inputs, **files}.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        builder = ResourceBuilder(stage)
        builder.outputs[ACTOR_INFO], detail = add_declarations(inputs[ACTOR_INFO], [status])
        changes.append({"resource": ACTOR_INFO, "declarations": detail})

        table = builder.table
        pack = f"Actor/Pack/{ACTOR}.sbactorpack"
        builder.outputs[pack], detail = clone_actor_pack(model_pack, MODEL_ACTOR, ACTOR)
        for kind, ext in (("Actor/Pack", "bactorpack"), ("Actor/ActorLink", "bxml")):
            table.set_size(f"{kind}/{ACTOR}.{ext}",
                           table.get_size(f"{kind}/{MODEL_ACTOR}.{ext}"))
        icon = ICON.read_bytes()
        builder.outputs[f"UI/StockItem/{ACTOR}.sbitemico"] = icon
        table.set_size(f"UI/StockItem/{ACTOR}.bitemico", len(unpack(icon)) + ICON_TABLE_MARGIN)
        changes.append({"resource": pack, "clone": detail, "icon_sha256": digest(icon)})

        for language in LANGUAGES:
            entry = status

            def messages(raw, entry=entry, language=language):
                archive = oead.Sarc(unpack(raw))
                writer = oead.SarcWriter.from_sarc(archive)
                new, detail = add_item_texts(bytes(archive.get_file(MSBT).data), [entry])
                writer.files[MSBT] = new
                packed = bytes(writer.write()[1])
                return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else packed), detail

            builder.patch_archive(f"Pack/Bootup_{language}.pack",
                                  {f"Message/Msg_{language}.product.ssarc": messages})

        builder.patch_archive(TITLE, {f"EventFlow/{FLOW_NAME}.bfevfl": add_status_entry})
        builder.patch_archive(BOOTUP, {EVENT_INFO: add_event_info})
        out = builder.finish()
        changes.extend(builder.changes)
    files = dict(files)
    files.update(out)
    return files, changes
