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

The scene shows the Archipelago item instead of the container. The two containers
(CONTAINERS, the same actors as the Divine Beasts' heart containers) are drawn with
the Archipelago model, in their model list and ActorInfo; their names, AS and
physics stay. The scene moves them by an animation of their bone Root, which the
game applies only to the model whose name the scene's AS carries
(Demo034_0-C05-Item_HeartUtuwa-A-0): both containers play SCENE_AS instead, a copy
of the heart's named after the model, listed in EventInfo beside the others. A
container received from the multiworld shows its usual icon, not the model.
"""
from __future__ import annotations

from pathlib import Path
import tempfile

import oead
from evfl.event import ActionEvent, SubFlowEvent

from botw_patch.shop_items import MODEL_PARTS
from botw_patch.shops import MODEL_FOLDER

ARCHIVE = "Event/Demo034_0.sbeventpack"
FLOW_NAME = "Demo034_0"
GIFT = "Event501"
COUNTER = "Npc_Goddess_UtuwaSum"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
BOOTUP = "Pack/Bootup.pack"
EVENT_INFO = "Event/EventInfo.product.sbyml"
ACTOR_INFO = "Actor/ActorInfo.product.sbyml"
# Each container and the scene's AS it plays.
CONTAINERS = {"Obj_HeartUtuwa_A_01": "Demo034_0-C05-Item_HeartUtuwa-A-0",
              "Obj_StaminaUtuwa_A_01": "Demo034_0-C05-Item_StaminaUtuwa-A-0"}
SCENE_AS = f"Demo034_0-C05-{MODEL_FOLDER}-A-0"
AS_PATH = "Actor/AS/Demo034_0/{}.bas"
# The world's spirit_orbs value whose trades are locations.
STATUE_CHECKS = 2
SOURCE_FILES = ("botw_patch/statue_checks.py",
                *(f"assets/models/ap_item/wiiu/AP_Item{part}.sbfres" for part in MODEL_PARTS))


def enabled(status: dict | None) -> bool:
    """The slot's statue trades are locations (the world's spirit_orbs on statue_checks)."""
    return bool(status and int(status.get("slot_data", {}).get("spirit_orbs", 0)) == STATUE_CHECKS)


def _gives(event) -> bool:
    data = event.data
    return (isinstance(data, SubFlowEvent) and data.res_flowchart_name == "GetDemo"
            and data.entry_point_name == "GetItemByName")


def transform(raw: bytes) -> tuple[bytes, dict]:
    """Demo034_0 with GIFT a wait and the containers playing SCENE_AS, checked against what was studied."""
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
    # The containers' scene, played under the model's name.
    played = {}
    for event in flow.flowchart.events:
        data = event.data
        if isinstance(data, ActionEvent) and str(data.actor_action.v) == "Demo_PlayASForDemo" \
                and data.params and data.params.data.get("ASName") in CONTAINERS.values():
            played[str(data.actor.v.identifier.name)] = data.params.data["ASName"]
            data.params.data["ASName"] = SCENE_AS
    if played != CONTAINERS:
        raise ValueError(f"{FLOW_NAME}: the containers play {played}")
    return write_flow(flow), {"wait": GIFT, "counter": COUNTER, "scene_as": SCENE_AS}


def ap_model(raw: bytes, actor: str) -> tuple[bytes, dict]:
    """A container's actor pack with its model list on the Archipelago model."""
    from botw_patch.resources import unpack
    archive = oead.Sarc(unpack(raw))
    writer = oead.SarcWriter.from_sarc(archive)
    path = f"Actor/ModelList/{actor}.bmodellist"
    models = oead.aamp.ParameterIO.from_binary(bytes(archive.get_file(path).data))
    data = models.lists["ModelData"].lists["ModelData_0"]
    units = data.lists["Unit"].objects
    if len(models.lists["ModelData"].lists) != 1 or len(units) != 1:
        raise ValueError(f"{actor}: one model and one unit expected")
    before = str(data.objects["Base"].params["Folder"].v)
    data.objects["Base"].params["Folder"] = oead.aamp.Parameter(oead.FixedSafeString64(MODEL_FOLDER))
    for unit in units.values():
        unit.params["UnitName"] = oead.aamp.Parameter(oead.FixedSafeString64(MODEL_FOLDER))
    writer.files[path] = bytes(models.to_binary())
    packed = bytes(writer.write()[1])
    return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else packed), {"actor": actor, "model": before}


def actor_info(raw: bytes) -> bytes:
    """ActorInfo with the containers' model (bfres, mainModel) the Archipelago one."""
    from botw_patch.resources import unpack
    info = oead.byml.from_binary(unpack(raw))
    found = []
    for entry in info["Actors"]:
        if str(entry["name"]) in CONTAINERS:
            found.append(str(entry["name"]))
            entry["bfres"] = entry["mainModel"] = MODEL_FOLDER
    if sorted(found) != sorted(CONTAINERS):
        raise ValueError(f"ActorInfo: containers {found}")
    data = bytes(oead.byml.to_binary(info, big_endian=True))
    return bytes(oead.yaz0.compress(data)) if raw[:4] == b"Yaz0" else data


def event_info(raw: bytes) -> tuple[bytes, list[str]]:
    """EventInfo with SCENE_AS beside the heart's AS, in every entry of the flow."""
    from botw_patch.resources import unpack
    info = oead.byml.from_binary(unpack(raw))
    heart = CONTAINERS["Obj_HeartUtuwa_A_01"]
    keys = []
    for key, entry in info.items():
        if key.startswith(f"{FLOW_NAME}<") and "as" in entry:
            files = [str(item["file"]) for item in entry["as"]]
            if heart in files and SCENE_AS not in files:
                entry["as"].append(oead.byml.Hash({"file": SCENE_AS}))
                keys.append(key)
    if not keys:
        raise ValueError(f"EventInfo: no {FLOW_NAME} entry lists {heart}")
    data = bytes(oead.byml.to_binary(info, big_endian=True))
    return (bytes(oead.yaz0.compress(data)) if raw[:4] == b"Yaz0" else data), keys


def generate(files: dict[str, bytes], content, model: dict[str, bytes] | None = None
             ) -> tuple[dict[str, bytes], list[dict]]:
    """The statue flow with its gift a wait and the Archipelago item in its scene
    (the size table is read from `files`, and the model when an earlier stage added it).
    content: the update folder, or the game's files (botw_patch/game_files.py)."""
    from botw_patch.game_files import GameFiles
    from botw_patch.resources import ResourceBuilder, unpack
    from botw_patch.shop_items import check_model, model_size, rename_model
    from botw_patch.shops import MODEL_ACTOR, MODEL_REFERENCE, model_files
    game = GameFiles.of(content)
    if TABLE not in files:
        raise ValueError(f"{TABLE} expected in the overlay")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        stage = Path(temp)
        for name in (ARCHIVE, TABLE, BOOTUP):
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(files[name] if name in files else game.read(name))
        builder = ResourceBuilder(stage)
        table = builder.table
        builder.patch_archive(ARCHIVE, {f"EventFlow/{FLOW_NAME}.bfevfl": transform})
        # SCENE_AS, the heart's AS under the model's name; its size entry is the heart's.
        before = builder.outputs[ARCHIVE]
        scene = oead.Sarc(unpack(before))
        copies = {bytes(scene.get_file(AS_PATH.format(name)).data) for name in CONTAINERS.values()}
        if len(copies) != 1 or scene.get_file(AS_PATH.format(SCENE_AS)) is not None:
            raise ValueError(f"{ARCHIVE}: the containers' AS differ, or {SCENE_AS} exists")
        writer = oead.SarcWriter.from_sarc(scene)
        writer.files[AS_PATH.format(SCENE_AS)] = copies.pop()
        after = bytes(oead.yaz0.compress(bytes(writer.write()[1])))
        table.set_size(AS_PATH.format(SCENE_AS), table.get_size(AS_PATH.format(CONTAINERS["Obj_HeartUtuwa_A_01"])))
        builder.account(ARCHIVE, after, before)
        builder.outputs[ARCHIVE] = after
        builder.patch_archive(BOOTUP, {EVENT_INFO: event_info})
        for actor in CONTAINERS:
            pack = f"Actor/Pack/{actor}.sbactorpack"
            original = files[pack] if pack in files else game.read(pack)
            builder.outputs[pack], detail = ap_model(original, actor)
            builder.account(pack, builder.outputs[pack], original)
            builder.changes.append({"resource": pack, **detail})
        builder.outputs[ACTOR_INFO] = actor_info(files[ACTOR_INFO] if ACTOR_INFO in files else game.read(ACTOR_INFO))
        builder.changes.append({"resource": ACTOR_INFO, "models": sorted(CONTAINERS)})
        if not all(f"Model/{MODEL_FOLDER}{part}.sbfres" in files for part in MODEL_PARTS):
            # The Archipelago model, as the shops' and chests' stages add it.
            model = model if model is not None else model_files()
            report = check_model(model, {part: MODEL_REFERENCE[part]["summary"] for part in MODEL_PARTS})
            renamed, rename_detail = rename_model(model, MODEL_ACTOR, MODEL_FOLDER)
            for part in MODEL_PARTS:
                builder.outputs[f"Model/{MODEL_FOLDER}{part}.sbfres"] = renamed[part]
                table.set_size(f"Model/{MODEL_FOLDER}{part}.bfres", model_size(
                    table.get_size(f"Model/{MODEL_ACTOR}{part}.bfres"),
                    MODEL_REFERENCE[part]["unpacked_size"], renamed[part]))
            builder.changes.append({"resource": "model", "check": report, "renamed": rename_detail})
        out = builder.finish()
    files = dict(files)
    files.update(out)
    return files, builder.changes
