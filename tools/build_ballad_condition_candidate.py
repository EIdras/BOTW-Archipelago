"""Condition the DLC champion upgrade of the Champions' Ballad end (Demo622_0..3).

A stage of the native build chain (Simon, 18/09: "Ballade DLC : conditionner").
At the end of each Ballad dungeon, the entry Demo622_N_GetUI deletes the base
power from the pouch (Demo_DeletePorchItemInEquip Obj_HeroSoul_X, DeleteNum -1)
and grants the upgraded one (GetDemo:GetItemByName Obj_DLC_HeroSoul_X), without
checking that the base power is owned. In AP the base powers are items of the
pool; granting the upgrade before the base item would hand out the power early.

The stage inserts, in front of the delete, the vanilla query
EventSystemActor HasPorchItem {PorchItemName: Obj_HeroSoul_X, Count: 1}: owned
-> vanilla delete + upgrade; not owned -> a one-frame wait and the entry ends
as it did after the grant. The pouch is the right ledger: it is what the AP
delivery of the power fills, and what the vanilla delete just below empties.

Measured, in this order:
* 9l (20260919T163003, 163822): the first form of the probe crashed Cemu, which
  looked like HasPorchItem's fault. 9l (165315) then showed the real cause: the
  vanilla DLC grant run outside its Ballad. The query was never guilty;
* 9l (165315) validated the guard on both branches with CheckFlag
  {IsGet_Obj_HeroSoul_X}, which looked equivalent and was kept;
* 9p (20260920T151602) refuted that flag in context: loading a save where the
  beast is freed (Clear_RemainsWater) and the power withheld, as every AP game
  has it, comes up with IsGet_Obj_HeroSoul_Zora already at 1, although the save
  file holds 0 and no itemGet ran. Simon had no power in the menu: the flag is
  set without the pouch item. The guard let the upgrade through.
Nothing else of the flows changes. The second visit (BalladOfHeroX_Finish)
never reaches GetUI and is untouched.
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

from botw_patch.events import graph_snapshot, guard_with_query, read_flow, write_flow  # noqa: E402
from botw_patch.resources import ResourceBuilder, digest, unpack  # noqa: E402
from tools.build_seed_bound_candidate import verified_files  # noqa: E402

# 28bda513736cc12e = 396e8197caa8ff65 + the removal of the two actors the
# pull demo leaves bound to Link (validated 9o, 20260920T011817.421113Z).
SOURCE = ROOT / ".build/master-sword-candidates/28bda513736cc12e"
OUTPUT = ROOT / ".build/ballad-condition-candidates"
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
# flow -> (race, pack sha256, flow sha256), measured on the mounted Wii U EUR v208 update.
FLOWS = {
    "Demo622_0": ("Goron", "e4a24a8f3759fd6827d5483ff9f274500a5f1c1b1cfbd9d5c73989a79bd153f7",
                  "b2333437ee4ae92cd3baaa488e8b46e4fa96e78ab0c760c0cd8bb31dae1279b1"),
    "Demo622_1": ("Rito", "67b12303d489b5e879449674d4caea9e497e7d45ff9af4e9dad591c4de9567d7",
                  "25c348f010c2f041d4cfd93aeec7e42455e0f0935d792719a23c95e78737bcb7"),
    "Demo622_2": ("Zora", "c111e50d05760ad49fab65e95e643e0365e4915f340cb3fd0de01267e22840d8",
                  "77b98dfd996b5bb26c4c19bb77879c43de278846761aabfcbef1ead201aedefd"),
    "Demo622_3": ("Gerudo", "9a3efdc0064a942b9b356b379ba9ba20c2e8a4aa140fa8668e10431bebe3d340",
                  "9bc2d64a1e2cffe9a4803170b6cc344b6125bddc576f1fa09d7436369cdae77f"),
}
SWITCH = "APBalladHasBasePower"
# Vanilla parameter set of this query (BalladOfHeroGoron Event237,
# BalladOfHeroRito Event203/213, on EventSystemActor).
QUERY = "HasPorchItem"


def guard_params(race: str) -> dict:
    return {"PorchItemName": f"Obj_HeroSoul_{race}", "Count": 1}


def pack(flow: str) -> str:
    return f"Event/{flow}.sbeventpack"


def member(flow: str) -> str:
    return f"EventFlow/{flow}.bfevfl"


def upgrade_events(graph: dict, race: str) -> tuple[str, str]:
    """(delete, grant): the unique base delete directly followed by the DLC grant."""
    found = []
    for name, node in graph["events"].items():
        if (node.get("actor") == "EventSystemActor"
                and node.get("actor_action") == "Demo_DeletePorchItemInEquip"
                and node.get("params", {}).get("PorchItemName") == f"Obj_HeroSoul_{race}"):
            grant = graph["events"].get(node.get("nxt"), {})
            if (grant.get("res_flowchart_name") == "GetDemo"
                    and grant.get("entry_point_name") == "GetItemByName"
                    and grant.get("params", {}).get("CheckTargetActorName")
                    == f"Obj_DLC_HeroSoul_{race}"):
                found.append((name, node["nxt"]))
    if len(found) != 1:
        raise ValueError(f"{graph['name']}: expected one base delete + DLC grant, found {found}")
    return found[0]


def redirect(node: dict, old: str, new: str) -> dict:
    """A graph_snapshot node with its references to ``old`` moved to ``new``."""
    out = dict(node)
    for field in ("nxt", "join"):
        if out.get(field) == old:
            out[field] = new
    if "forks" in out:
        out["forks"] = [new if ref == old else ref for ref in out["forks"]]
    if "cases" in out:
        out["cases"] = {key: new if ref == old else ref for key, ref in out["cases"].items()}
    return out


def transform_for(flow_name: str):
    race, _pack_sha, flow_sha = FLOWS[flow_name]

    def transform(raw: bytes) -> tuple[bytes, list[str]]:
        if digest(raw) != flow_sha:
            raise ValueError(f"{flow_name} flow changed")
        flow = read_flow(raw)
        before = graph_snapshot(flow)
        if before["name"] != flow_name:
            raise ValueError("wrong Ballad flow")
        delete, grant = upgrade_events(before, race)
        guard_with_query(flow, delete, SWITCH, "EventSystemActor", QUERY,
                         guard_params(race), otherwise=before["events"][grant].get("nxt"))
        after = graph_snapshot(flow)
        added = set(after["events"]) - set(before["events"])
        if added != {SWITCH, SWITCH + "_Skip"} or set(before["events"]) - set(after["events"]):
            raise ValueError(f"{flow_name}: unexpected event set change {added}")
        switch = after["events"][SWITCH]
        if (switch["actor_query"] != QUERY or switch["cases"] != {1: delete, 0: SWITCH + "_Skip"}
                or after["events"][SWITCH + "_Skip"]["nxt"] != before["events"][grant].get("nxt")):
            raise ValueError(f"{flow_name}: guard not wired as expected")

        for name, node in before["events"].items():
            # Every existing event is unchanged, except that its references to
            # the delete now point to the guard.
            if redirect(node, delete, SWITCH) != after["events"][name]:
                raise ValueError(f"{flow_name}: unexpected change in {name}")
        entries_before = dict(before["entry_points"])
        for entry, first in after["entry_points"]:
            expected = SWITCH if entries_before[entry] == delete else entries_before[entry]
            if first != expected:
                raise ValueError(f"{flow_name}: entry {entry} moved")
        return write_flow(flow), [SWITCH, SWITCH + "_Skip", f"guards {delete}"]

    return transform


def build(source: Path = SOURCE, output: Path = OUTPUT, update: Path = UPDATE) -> Path:
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if (any(pack(flow) in manifest["files"] for flow in FLOWS)
            or not manifest.get("native_delivery_entries")
            or manifest.get("ballad_condition_source")):
        raise ValueError("source is not a verified native candidate without the Ballad stage")
    files = verified_files(source, manifest)
    raw_packs = {}
    for flow, (_race, pack_sha, _flow_sha) in FLOWS.items():
        raw_packs[flow] = (update / pack(flow)).read_bytes()
        if digest(raw_packs[flow]) != pack_sha:
            raise ValueError(f"mounted Ballad source changed: {pack(flow)}")
    stage = output / "_input"
    (stage / "Event").mkdir(parents=True, exist_ok=True)
    (stage / "System/Resource").mkdir(parents=True, exist_ok=True)
    for flow, raw in raw_packs.items():
        (stage / pack(flow)).write_bytes(raw)
    (stage / TABLE).write_bytes(files["content/" + TABLE])
    builder = ResourceBuilder(stage)
    for flow in FLOWS:
        builder.patch_archive(pack(flow), {member(flow): transform_for(flow)})
    outputs = builder.finish()
    if set(outputs) != {*(pack(f) for f in FLOWS), TABLE} or len(builder.changes) != len(FLOWS):
        raise ValueError("unexpected source outputs")
    for flow, raw in raw_packs.items():
        before = oead.Sarc(unpack(raw))
        after = oead.Sarc(unpack(outputs[pack(flow)]))
        names = {item.name for item in before.get_files()}
        changed = {name for name in names if bytes(before.get_file(name).data)
                   != bytes(after.get_file(name).data)}
        if names != {item.name for item in after.get_files()} or changed != {member(flow)}:
            raise ValueError(f"unexpected {pack(flow)} change: {changed}")
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
        "ballad_condition_source": {
            "parent_build": source.name,
            "parent_path": source.relative_to(ROOT).as_posix(),
            "flows": {flow: {"race": race, "pack_sha256": pack_sha, "flow_sha256": flow_sha}
                      for flow, (race, pack_sha, flow_sha) in FLOWS.items()},
            "query": "EventSystemActor HasPorchItem "
                     "{PorchItemName: Obj_HeroSoul_X, Count: 1}",
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
