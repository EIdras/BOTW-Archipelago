"""Build a resource overlay into an isolated, content-addressed directory."""
from __future__ import annotations

import json
from pathlib import Path
import oead
from .events import suppress_terminal_rewards, suppress_reward, suppress_champion_rewards
from .resources import ResourceBuilder, digest, unpack

RECIPES = {
    "Demo003_0": suppress_terminal_rewards,
    "Demo033_0": lambda data: suppress_reward(data, "Obj_DungeonClearSeal"),
    "FindDungeon": lambda data: suppress_reward(data, "PlayerStole2"),
    "Npc_DungeonPriest001": lambda data: suppress_reward(data, "Obj_DungeonClearSeal"),
    "ClearRemains": suppress_champion_rewards,
}
# Unmodified Wii U EUR v208 resources, measured from the mounted update.
# Do not silently apply a recipe to a different revision or a merged mod.
SOURCE_HASHES = {
    "Demo003_0": "5ffd2da1e6dcf8773f2122aff4a440f0643cf0bd9f37a2faba76843115ccec9a",
    "Demo033_0": "d87df1fd49e754c4e67b798e47b50ef4ebdc762060d0f815d281a9a0305eedf0",
    "FindDungeon": "ee33828c07bafe18cd913b4188d11a8ba2c3d377a9e26c1d08bc342200f95c92",
    "Npc_DungeonPriest001": "28e5a3d85eb82852131cc55c9c2efc37ff016dc40a6b3d7c2805d149637b44fd",
    "ClearRemains": "c822f04a33335f3d01cb698f93eeade36e9f349108e701efbe766fa809ac023e",
}


def build(content: Path, output_root: Path) -> Path:
    builder = ResourceBuilder(content)
    found = set()
    # An event can be embedded in another event pack. Patch by member identity,
    # including every copy, instead of assuming the archive matches its name.
    for path in sorted((content / "Event").glob("*.sbeventpack")):
        archive = oead.Sarc(unpack(path.read_bytes()))
        transforms = {}
        for member in archive.get_files():
            name = Path(member.name).stem
            if member.name != f"EventFlow/{name}.bfevfl" or name not in RECIPES:
                continue
            def checked(data, name=name):
                if digest(data) != SOURCE_HASHES[name]:
                    raise ValueError(f"unsupported or already modified vanilla flow: {name}")
                return RECIPES[name](data)
            transforms[member.name] = checked
            found.add(name)
        if transforms:
            builder.patch_archive(path.relative_to(content).as_posix(), transforms)
    if found != set(RECIPES):
        raise ValueError(f"required vanilla flows missing: {sorted(set(RECIPES) - found)}")
    outputs = builder.finish()
    hashes = {name: digest(data) for name, data in sorted(outputs.items())}
    fingerprint = digest(json.dumps(hashes, sort_keys=True).encode())
    target = output_root.resolve() / fingerprint[:16]
    manifest = {
        "schema": 1, "target": "botw-wiiu-eur-v208", "build_sha256": fingerprint,
        "status": "requires_in_game_validation", "files": hashes,
        "capabilities": {"resource_runes": True, "resource_shrine_orbs": True,
                         "resource_paraglider": True, "resource_champions": True,
                         "save_transaction": False,
                         "event_presentation": False},
        "changes": builder.changes,
    }
    # All transformations and preconditions complete before writing anything.
    for name, data in outputs.items():
        path = target / "content" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"immutable build directory was modified: {path}")
        path.write_bytes(data)
    (target / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (target / "rules.txt").write_text(
        '[Definition]\ntitleIds = 00050000101C9500\n'
        'name = Archipelago Resources (validation)\n'
        'path = "The Legend of Zelda: Breath of the Wild/Archipelago/Resources"\n'
        'description = Experimental resource substitutions; requires matching client and seed.\n'
        'version = 7\nfsPriority = 1000\n', encoding="utf-8")
    return target
