"""The ends of the Champions' Ballad, four locations: they no longer upgrade a power.

At the end of each champion's Ballad (its last trial in its Divine Beast),
the entry Demo622_N_GetUI deletes the base power from the pouch
(Demo_DeletePorchItemInEquip Obj_HeroSoul_X, DeleteNum -1) and grants the
upgraded one (GetDemo<GetItemByName> Obj_DLC_HeroSoul_X), its last event. In AP
the "+" is the second copy of the power's item, which the multiworld alone
gives; the scene's own saved flag, IsPlayed_Demo622_N, set by the scene, is the
location.

This stage turns the delete into a one-frame wait that ends the entry: neither
the delete nor the grant runs, the rest of the scene is the game's. The grant
stays in the flow, unreached: the Ballad's own flow is where it can be.
"""
from __future__ import annotations

from evfl.util import Index

from botw_patch.events import graph_snapshot, read_flow, wait_instead, write_flow
from botw_patch.resources import vanilla_digest

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
PACKS = {f"Event/{flow}.sbeventpack": pack_sha for flow, (_race, pack_sha, _flow) in FLOWS.items()}
SOURCE_FILES = ("botw_patch/ballad_ends.py",)


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


def transform_for(flow_name: str):
    race, _pack_sha, flow_sha = FLOWS[flow_name]

    def transform(raw: bytes) -> tuple[bytes, list[str]]:
        if vanilla_digest(raw) != flow_sha:
            raise ValueError(f"{flow_name} flow changed")
        flow = read_flow(raw)
        before = graph_snapshot(flow)
        if before["name"] != flow_name:
            raise ValueError("wrong Ballad flow")
        delete, grant = upgrade_events(before, race)
        if before["events"][grant].get("nxt") is not None:
            raise ValueError(f"{flow_name}: the DLC grant is not the entry's last event")
        event = next(e for e in flow.flowchart.events if e.name == delete)
        wait_instead(flow, event)
        event.data.nxt = Index()
        after = graph_snapshot(flow)
        changed = {name for name in before["events"] if before["events"][name] != after["events"][name]}
        if (changed != {delete} or set(after["events"]) != set(before["events"])
                or after["entry_points"] != before["entry_points"]
                or after["events"][delete]["nxt"] is not None
                or after["events"][delete]["actor_action"] != "Demo_WaitFrame"):
            raise ValueError(f"{flow_name}: changed beyond the upgrade: {sorted(changed)}")
        return write_flow(flow), [f"{member(flow_name)}: the Ballad's end no longer upgrades {race}'s power"]

    return transform
