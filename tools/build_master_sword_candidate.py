"""Remove the vanilla Master Sword grant of the pedestal flow (Get_MasterSword).

A stage of the native build chain, like tools/build_plateau_sensor_candidate.py.
The pedestal is the AP check "Master Sword Pedestal" (flag Get_MasterSword_Finish,
set at Event67 after the grant); the sword itself is an AP item.

Entry NukiGameFinish, after the pull cutscene:
* Event181 GetDemo:GetItemByName(Weapon_Sword_070): pouch entry, equipment
  creation, get window and IsGet_Weapon_Sword_070. Replaced by a wait;
* Event182 Demo_EquipLastSetItem: equips the item just added. Replaced by
  GameROMPlayer Demo_PlayerReleaseMasterSword (vanilla: Link lets go of the
  Master Sword, Demo202_0/Demo605_0).
Why: the pull cutscene itself puts the pedestal sword actor on Link (hand or
back), outside the pouch; vanilla only registers it afterwards. Measured:
* with waits only, Link keeps a usable, unregistered sword;
* GameROMPlayer Demo_UpdateEquip does not remove it;
* each action requested after the scene: Demo_Unequip only sheathes it,
  Demo_SwitchPlayerEquipment (weapon) does nothing,
  Demo_PlayerReleaseMasterSword detaches it: inert in the air, Link can no
  longer draw it; the AP sword delivered next works normally.
The released actor then hangs inert in the air and Link keeps an empty Master
Sword scabbard until the next load. EventSystemActor Demo_KillSelectActor aimed
at the actor makes it disappear, adds nothing to the pouch and leaves the game
stable (measured). Three events are added after Event213 for that: APKillWait
(30 frames, the scene's own Demo_SuccessGet is fire-and-forget), APKillSword
and APKillSheath. The scabbard is its own actor, Weapon_Sheath_070, bound by
the same pull demo. Bracketing the release with 100enemy_Sheath_BindUpdateSkip,
as both vanilla users do, changes nothing, so that framing is not kept.
Event213 Demo_SuccessGet on the pedestal actor is kept, and still runs on the
released actor: for a picked-up world actor it ends its presence in the world.
It adds nothing (no itemGet, IsGet_Weapon_Sword_070 still 0).
The check flag, the talk, the life reset and the autosave stay.

The flow is embedded in two packs (Event/Get_MasterSword.sbeventpack and
Event/Demo300_0.sbeventpack), identical; both are patched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path
                            if Path(p).resolve() != ROOT / "tools"]

import oead  # noqa: E402

from botw_patch.events import (  # noqa: E402
    action_instead, add_action_after, graph_snapshot, read_flow, wait_instead,
    write_flow)
from botw_patch.resources import ResourceBuilder, digest, unpack  # noqa: E402
from tools.build_seed_bound_candidate import verified_files  # noqa: E402

SOURCE = ROOT / ".build/world-heart-withhold-candidates/46e4845b7b518949"
OUTPUT = ROOT / ".build/master-sword-candidates"
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
FLOW = "EventFlow/Get_MasterSword.bfevfl"
PACKS = {"Event/Get_MasterSword.sbeventpack":
         "e5e4b3bd57ad598fd12ec516ee36e3aedc5c3a4a14307d60bb1d5562e1f50966",
         "Event/Demo300_0.sbeventpack":
         "bf9906427513668c2d5ff5d64b6025fef174b7494179ad9f0b51ecec591e991a"}
EXPECTED_FLOW_SHA = "9301c1c52b8f0436e3576302a5675029d252ddd7da93a9f678ce671b4b5a9c88"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
SWORD = "Weapon_Sword_070"
REPLACED = {"Event181", "Event182"}
# The released sword and the scabbard are two bound actors of the pull
# demo; Demo_KillSelectActor (vanilla parameter set of Demo605_0 Event135)
# removes the sword, measured. The scabbard is Weapon_Sheath_070.
SHEATH = "Weapon_Sheath_070"
KILL_DELAY = 30
ADDED = {"APKillWait": ("Demo_WaitFrame", "Event213"),
         "APKillSword": ("Demo_KillSelectActor", "APKillWait"),
         "APKillSheath": ("Demo_KillSelectActor", "APKillSword")}
KILLED = {"APKillSword": SWORD, "APKillSheath": SHEATH}
KEPT = {"Event213": "Demo_SuccessGet", "Event67": "Demo_FlagON",
        "Event120": "Demo_AutoSave", "Event225": "CheckGameDataInt"}


def transform(raw: bytes) -> tuple[bytes, list[str]]:
    if digest(raw) != EXPECTED_FLOW_SHA:
        raise ValueError("Master Sword flow changed")
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    grant = before["events"]["Event181"]
    equip = before["events"]["Event182"]
    if (grant.get("res_flowchart_name") != "GetDemo"
            or grant.get("entry_point_name") != "GetItemByName"
            or grant.get("params", {}).get("CheckTargetActorName") != SWORD
            or equip.get("actor_action") != "Demo_EquipLastSetItem"
            or grant.get("nxt") != "Event182" or equip.get("nxt") != "Event213"
            or before["events"]["Event67"].get("params", {}).get("FlagName")
            != "Get_MasterSword_Finish"):
        raise ValueError("Master Sword grant layout changed")
    events = {event.name: event for event in flow.flowchart.events}
    wait_instead(flow, events["Event181"], frames=5)
    action_instead(flow, events["Event182"], "GameROMPlayer",
                   "Demo_PlayerReleaseMasterSword", {"IsWaitFinish": True})
    # Remove the two actors the pull demo left bound to Link, after the
    # kept Demo_SuccessGet has had time to run (it does not wait for itself).
    add_action_after(flow, "Event213", "APKillWait", "EventSystemActor",
                     "Demo_WaitFrame", {"Frame": KILL_DELAY, "IsWaitFinish": True})
    previous = "APKillWait"
    for name, actor_name in KILLED.items():
        add_action_after(flow, previous, name, "EventSystemActor", "Demo_KillSelectActor",
                         {"IsWaitFinish": True, "ActorName": actor_name, "UniqueName": ""})
        previous = name
    after = graph_snapshot(flow)
    if (before["entry_points"] != after["entry_points"]
            or set(after["events"]) - set(before["events"]) != set(ADDED)
            or set(before["events"]) - set(after["events"])):
        raise ValueError("Master Sword graph structure changed")
    changed = {name for name in before["events"]
               if before["events"][name] != after["events"][name]}
    if changed != REPLACED | {"Event213"}:
        raise ValueError(f"unexpected Master Sword events changed: {changed}")
    # The two replaced events keep their successor; Event213 changes nothing but
    # its edge, and the inserted chain ends where it used to go (Event225).
    for name in REPLACED:
        if before["events"][name].get("nxt") != after["events"][name].get("nxt"):
            raise ValueError(f"Master Sword edge changed: {name}")
    kept = dict(before["events"]["Event213"], nxt="APKillWait")
    if after["events"]["Event213"] != kept:
        raise ValueError("Master Sword Event213 changed beyond its edge")
    if (after["events"]["APKillWait"].get("params") != {"Frame": KILL_DELAY,
                                                        "IsWaitFinish": True}
            or after["events"]["APKillSheath"].get("nxt")
            != before["events"]["Event213"].get("nxt")):
        raise ValueError("Master Sword removal not inserted in place")
    previous = "APKillWait"
    for name, actor_name in KILLED.items():
        node = after["events"][name]
        if (after["events"][previous].get("nxt") != name
                or node.get("actor") != "EventSystemActor"
                or node.get("actor_action") != "Demo_KillSelectActor"
                or node.get("params", {}).get("ActorName") != actor_name):
            raise ValueError(f"Master Sword inserted event wrong: {name}")
        previous = name
    if (after["events"]["Event181"].get("actor_action") != "Demo_WaitFrame"
            or after["events"]["Event182"].get("actor") != "GameROMPlayer"
            or after["events"]["Event182"].get("actor_action")
            != "Demo_PlayerReleaseMasterSword"):
        raise ValueError("Master Sword replacement actions not applied")
    for name, action in KEPT.items():
        node = after["events"][name]
        if (node.get("actor_action") or node.get("actor_query")) != action:
            raise ValueError(f"Master Sword kept event changed: {name}")
    return write_flow(flow), sorted(changed)


def build(source: Path = SOURCE, output: Path = OUTPUT, update: Path = UPDATE) -> Path:
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if (any(pack in manifest["files"] for pack in PACKS)
            or not manifest.get("native_delivery_entries")
            or manifest.get("master_sword_source")):
        raise ValueError("source is not a verified native candidate without the sword stage")
    files = verified_files(source, manifest)
    raw_packs = {}
    for pack, expected in PACKS.items():
        raw_packs[pack] = (update / pack).read_bytes()
        if digest(raw_packs[pack]) != expected:
            raise ValueError(f"mounted Master Sword source changed: {pack}")
    stage = output / "_input"
    (stage / "Event").mkdir(parents=True, exist_ok=True)
    (stage / "System/Resource").mkdir(parents=True, exist_ok=True)
    for pack, raw in raw_packs.items():
        (stage / pack).write_bytes(raw)
    (stage / TABLE).write_bytes(files["content/" + TABLE])
    builder = ResourceBuilder(stage)
    for pack in PACKS:
        builder.patch_archive(pack, {FLOW: transform})
    outputs = builder.finish()
    if set(outputs) != {*PACKS, TABLE} or len(builder.changes) != len(PACKS):
        raise ValueError("unexpected source outputs")
    for pack, raw in raw_packs.items():
        before = oead.Sarc(unpack(raw))
        after = oead.Sarc(unpack(outputs[pack]))
        names = {item.name for item in before.get_files()}
        if names != {item.name for item in after.get_files()}:
            raise ValueError(f"{pack} members changed")
        changed = {name for name in names if bytes(before.get_file(name).data)
                   != bytes(after.get_file(name).data)}
        if changed != {FLOW}:
            raise ValueError(f"unexpected {pack} members changed: {changed}")
    files.update({"content/" + name: raw for name, raw in outputs.items()})
    hashes = {name: digest(raw) for name, raw in sorted(files.items())}
    build_id = hashlib.sha256(json.dumps(hashes, sort_keys=True,
                              separators=(",", ":")).encode()).hexdigest()[:16]
    target = (output / build_id).resolve()
    if not target.is_relative_to(output.resolve()):
        raise ValueError("candidate escaped output root")
    for name, raw in files.items():
        path = (target / name).resolve()
        if not path.is_relative_to(target):
            raise ValueError("candidate member escaped output root")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"immutable candidate changed: {name}")
        path.write_bytes(raw)
    result = dict(manifest)
    result.update({
        "status": "requires_in_game_validation",
        "master_sword_source": {
            "parent_build": source.name,
            "parent_path": source.relative_to(ROOT).as_posix(),
            "packs": PACKS,
            "flow_sha256": EXPECTED_FLOW_SHA,
            "flow": FLOW,
            "replacements": {"Event181": "EventSystemActor Demo_WaitFrame 5",
                             "Event182": "GameROMPlayer Demo_PlayerReleaseMasterSword"},
            "inserted_events": {name: f"EventSystemActor {action} after {anchor}"
                                for name, (action, anchor) in ADDED.items()},
            "killed_actors": KILLED,
            "kept_events": KEPT,
            "source_changes": builder.changes,
        },
        "files": {name[8:]: value for name, value in hashes.items()
                  if name.startswith("content/")},
        "native_files": {name: hashes[name] for name in manifest["native_files"]},
    })
    manifest_path = target / "manifest.json"
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    if manifest_path.exists() and manifest_path.read_bytes() != encoded:
        raise ValueError("immutable candidate manifest changed")
    manifest_path.write_bytes(encoded)
    return target


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    print(build(arguments.source, arguments.output))
