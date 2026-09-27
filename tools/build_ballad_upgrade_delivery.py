"""Deliver the upgraded champion power when its Ballad has already been played.

A stage of the native build chain (Simon, 21/09, question 2: "oui").

The Ballad guard (tools/build_ballad_condition_candidate.py) withholds the DLC
upgrade at the end of a Champions' Ballad dungeon when the base power is not in
the pouch: in AP the base powers are pool items and may arrive later. Without
this stage, a base power arriving after that scene would stay the base one for
good, since the scene is not replayed (its second visit, BalladOfHeroX_Finish,
never reaches GetUI).

Which flag says "the Ballad scene has been played": measured in 9q
(20260920T173920.595198Z-native-ballad-context), across the scene,
IsPlayed_Demo622_2 goes 0 -> 1 and BalladOfHeroZora_Finish stays 0, so Finish
is not the signal. The scene carries the guard, so IsPlayed_Demo622_N = 1 when
the base power arrives means the upgrade was withheld: had the base been owned
then, the upgrade was given and the pool item cannot arrive a second time.

The stage edits only the four champion entries of the AP delivery flow
(Demo007_1, APD_<hash>_00). In front of the base grant it inserts the vanilla
query EventSystemActor CheckFlag {FlagName: IsPlayed_Demo622_N}:
  0 -> the base grant, unchanged (validated 9u);
  1 -> the same three vanilla actions on Obj_DLC_HeroSoul_X (pouch,
       create-equip, get flag), then the get flag of the base power, as the
       vanilla upgrade leaves both flags at 1 (9q), and the same cursor commit.
No GetDemo subflow is used: a GetDemo grant of the DLC power outside its Ballad
crashes (9l), even on a branch not taken. The DLC actor through
Demo_SetItemDataToPouch outside the Ballad has not been measured yet.
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

from botw_patch.events import SubFlowStep, branch_with_query, graph_snapshot, read_flow, write_flow  # noqa: E402
from botw_patch.resources import ResourceBuilder, digest, unpack  # noqa: E402
from tools.build_ballad_condition_candidate import FLOWS  # noqa: E402
from tools.build_seed_bound_candidate import FLOW_MEMBER, TITLE, verified_files  # noqa: E402

# 4f8e651898d3423b: the champion power restore stage, validated 9t/9u.
SOURCE = ROOT / ".build/hero-soul-restore-candidates/4f8e651898d3423b"
OUTPUT = ROOT / ".build/ballad-upgrade-delivery-candidates"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
QUERY = "CheckFlag"
SCENES = {race: flow for flow, (race, _pack, _flow) in FLOWS.items()}


def scene_flag(race: str) -> str:
    return f"IsPlayed_{SCENES[race]}"


def champion_entries(catalog: dict) -> dict[str, tuple[str, str]]:
    """AP item -> (delivery entry, race) for the four champion powers."""
    out = {}
    for item, spec in catalog["items"].items():
        steps = spec["variants"].get("default", [])
        kinds = [m["kind"] for step in steps for m in step["mutations"]]
        if "champion_actor" not in kinds:
            continue
        if len(steps) != 1 or kinds != ["champion_actor"]:
            raise ValueError(f"{item}: unexpected champion delivery shape")
        target = steps[0]["mutations"][0]["target"]
        race = target.removeprefix("Obj_HeroSoul_")
        if race not in SCENES or target != f"Obj_HeroSoul_{race}":
            raise ValueError(f"{item}: unknown champion actor {target}")
        out[item] = (steps[0]["entry"], race)
        # The silent twin (items given back after a reload) branches the same.
        if steps[0].get("quiet_entry"):
            out[f"{item} (quiet)"] = (steps[0]["quiet_entry"], race)
    base = [race for item, (_entry, race) in out.items() if not item.endswith(" (quiet)")]
    if sorted(base) != sorted(SCENES):
        raise ValueError(f"champion entries do not cover the four races: {out}")
    return out


def upgrade_chain(stem: str, race: str) -> list[tuple[str, str, dict]]:
    dlc, base = f"Obj_DLC_HeroSoul_{race}", f"Obj_HeroSoul_{race}"
    return [
        (stem + "_Dlc", "Demo_SetItemDataToPouch",
         {"TargetActorName": dlc, "IsWaitFinish": False}),
        (stem + "_Dlc_Equip", "Demo_CheckAndCreateEquip",
         {"TargetActorName": dlc, "IsWaitFinish": True}),
        # No get window for the DLC power: a GetDemo grant of it outside its
        # Ballad crashed in 9l; this chain is the one validated in 9w.
        (stem + "_Dlc_GetFlag", "Demo_SetGetFlagByActorName",
         {"ActorName": dlc, "IsWaitFinish": True}),
        (stem + "_Dlc_BaseFlag", "Demo_SetGetFlagByActorName",
         {"ActorName": base, "IsWaitFinish": True}),
    ]


def redirect(node: dict, old: str, new: str) -> dict:
    out = dict(node)
    for field in ("nxt", "join"):
        if out.get(field) == old:
            out[field] = new
    if "forks" in out:
        out["forks"] = [new if ref == old else ref for ref in out["forks"]]
    if "cases" in out:
        out["cases"] = {key: new if ref == old else ref for key, ref in out["cases"].items()}
    return out


def transform_for(entries: dict[str, tuple[str, str]], host: str = "Demo007_1"):
    """`host`: Demo007_1 for the entries with a window, the silent twins'
    flowchart (botw_patch/delivery_flow.QUIET_FLOW) for theirs."""
    def transform(raw: bytes) -> tuple[bytes, list[str]]:
        flow = read_flow(raw)
        before = graph_snapshot(flow)
        if before["name"] != host:
            raise ValueError("wrong delivery host flow")
        changes, moved = [], {}
        for item, (stem, race) in sorted(entries.items()):
            base = f"Obj_HeroSoul_{race}"
            grant, equip, flag = stem + "_Mut0", stem + "_Mut0_Equip", stem + "_Mut0_GetFlag"
            show = stem + "_Mut0_Show"
            events = before["events"]
            # Since 25/09 the base entry shows the game's get window between
            # equipment and flag, as vanilla GetItemByName; the laboratory
            # chain's entries predate it.
            shown = (events[equip].get("nxt") == show
                     and events[show].get("entry_point_name") == "ShowGetDemoDialogByName"
                     and events[show]["params"].get("CheckTargetActorName") == base
                     and events[show].get("nxt") == flag)
            if (events[grant].get("actor_action") != "Demo_SetItemDataToPouch"
                    or events[grant]["params"].get("TargetActorName") != base
                    or events[grant].get("nxt") != equip
                    or not (shown or events[equip].get("nxt") == flag)
                    or events[flag]["params"].get("ActorName") != base
                    or events[flag].get("nxt") != stem + "_Commit"
                    or events[stem + "_GuardON"].get("nxt") != grant):
                raise ValueError(f"{item}: champion entry is not the validated shape")
            switch = stem + "_Ballad"
            branch_with_query(flow, grant, switch, "EventSystemActor", QUERY,
                              {"FlagName": scene_flag(race)},
                              upgrade_chain(stem, race), rejoin=stem + "_Commit")
            moved[grant] = switch
            changes.append(f"{item}: {scene_flag(race)} -> Obj_DLC_HeroSoul_{race}")
        after = graph_snapshot(flow)
        added = set(after["events"]) - set(before["events"])
        expected = {name for stem, race in entries.values()
                    for name in [stem + "_Ballad", *(n for n, _a, _p in upgrade_chain(stem, race))]}
        if added != expected or set(before["events"]) - set(after["events"]):
            raise ValueError(f"unexpected event set change: {sorted(added ^ expected)}")
        for name, node in before["events"].items():
            expected_node = node
            for old, new in moved.items():
                expected_node = redirect(expected_node, old, new)
            if after["events"][name] != expected_node:
                raise ValueError(f"unexpected change in {name}")
        if after["entry_points"] != before["entry_points"]:
            raise ValueError("delivery entry points changed")
        for stem, race in entries.values():
            switch = after["events"][stem + "_Ballad"]
            chain = upgrade_chain(stem, race)
            if (switch["actor_query"] != QUERY
                    or switch["params"] != {"FlagName": scene_flag(race)}
                    or switch["cases"] != {1: chain[0][0], 0: stem + "_Mut0"}
                    or after["events"][chain[-1][0]]["nxt"] != stem + "_Commit"):
                raise ValueError(f"{stem}: branch not wired as expected")
            for (name, action, params), nxt in zip(chain, [n for n, _a, _p in chain[1:]]
                                                   + [stem + "_Commit"]):
                node = after["events"][name]
                kind = ((node.get("res_flowchart_name"), node.get("entry_point_name"))
                        if isinstance(action, SubFlowStep) else node.get("actor_action"))
                wanted = ((action.flowchart, action.entry)
                          if isinstance(action, SubFlowStep) else action)
                if kind != wanted or node["params"] != params or node["nxt"] != nxt:
                    raise ValueError(f"{name}: not the planned action")
        return write_flow(flow), changes

    return transform


def build(source: Path = SOURCE, output: Path = OUTPUT) -> Path:
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if (not manifest.get("native_delivery_entries")
            or not manifest.get("hero_soul_restore_withhold")
            or not manifest.get("ballad_condition_source")
            or manifest.get("ballad_upgrade_delivery")):
        raise ValueError("source is not a verified native candidate without the stage")
    files = verified_files(source, manifest)
    catalog = json.loads(files["delivery_catalog.json"])
    entries = champion_entries(catalog)
    builder = ResourceBuilder(source / "content")
    builder.patch_archive(TITLE, {FLOW_MEMBER: transform_for(entries)})
    outputs = builder.finish()
    if set(outputs) != {TITLE, TABLE}:
        raise ValueError(f"unexpected outputs: {sorted(outputs)}")
    old = oead.Sarc(unpack(files["content/" + TITLE]))
    new = oead.Sarc(unpack(outputs[TITLE]))
    names = {item.name for item in old.get_files()}
    changed = {name for name in names
               if bytes(old.get_file(name).data) != bytes(new.get_file(name).data)}
    if names != {item.name for item in new.get_files()} or changed != {FLOW_MEMBER}:
        raise ValueError(f"unexpected TitleBG change: {changed}")
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
        "ballad_upgrade_delivery": {
            "parent_build": source.name,
            "parent_path": source.relative_to(ROOT).as_posix(),
            "query": "EventSystemActor CheckFlag {FlagName: IsPlayed_Demo622_N}",
            "entries": {item: {"entry": stem, "race": race, "flag": scene_flag(race),
                               "upgrade": f"Obj_DLC_HeroSoul_{race}"}
                        for item, (stem, race) in sorted(entries.items())},
            "evidence": ["20260920T173920.595198Z-native-ballad-context",
                         "20260921T004056.552332Z-native-hero-soul-delivery"],
            "catalog_unchanged": True,
            "source_changes": builder.changes,
        },
        "files": {name[8:]: value for name, value in hashes.items()
                  if name.startswith("content/")},
        "native_files": {name: hashes[name] for name in manifest["native_files"]},
    })
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = target / "manifest.json"
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("immutable candidate manifest changed")
    path.write_bytes(encoded)
    return target


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    print(build(arguments.source, arguments.output))
