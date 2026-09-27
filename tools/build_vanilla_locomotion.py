"""Give a play pack the game's own running and climbing speed back.

Simon asked, during the laboratory tests, to move faster: `tools/build_plateau_speed.py`
multiplied by 3 the `FrameCtrl` rates of the run, dash and wall-climb
animations of `Actor/Pack/GameROMPlayer.sbactorpack`. That candidate became an
ancestor of the whole build chain, so **every** pack since carries the aid,
including the one of the first play session (Simon, 23/09: "j'ai toujours les
cheats").

This stage restores the vanilla member, byte for byte, from the mounted update
(its sha256 is the `before` recorded by the speed builder). It is the base of
packs bound to a *play* seed; the laboratory chain keeps the aid, which shortens
the tests.

Nothing else changes: one member of Pack/TitleBG.pack, plus the resource size
table the builder keeps in step.
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

from botw_patch.resources import ResourceBuilder, digest, unpack  # noqa: E402
from tools.build_seed_bound_candidate import FLOW_MEMBER, TITLE, verified_files  # noqa: E402

SOURCE = ROOT / ".build/ballad-upgrade-delivery-candidates/a3e856f29c984bf9"
OUTPUT = ROOT / ".build/vanilla-locomotion-candidates"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
MEMBER = "Actor/Pack/GameROMPlayer.sbactorpack"
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
VANILLA_SHA = "d6518a297e3145154ccef043764929228a74dbea510e2e1a26de8423d3cfff30"
AIDED_SHA = "35aab96ef4f45bae9c9af70eb7e7514d8b82d11546b7319ae680135a699b34f7"


def vanilla_member(update: Path = UPDATE) -> bytes:
    """The player actor pack of the mounted update, unmodified."""
    archive = oead.Sarc(unpack((update / TITLE).read_bytes()))
    raw = bytes(archive.get_file(MEMBER).data)
    if digest(raw) != VANILLA_SHA:
        raise ValueError("le paquet d'acteur du joueur monté n'est pas celui attendu")
    return raw


def build(source: Path = SOURCE, output: Path = OUTPUT, update: Path = UPDATE) -> Path:
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    aid = manifest.get("validation_aids", {})
    if aid.get("locomotion_animation_rate_multiplier") != 3:
        raise ValueError("la source ne porte pas l'aide de déplacement")
    files = verified_files(source, manifest)
    vanilla = vanilla_member(update)
    builder = ResourceBuilder(source / "content")
    builder.patch_archive(TITLE, {MEMBER: lambda raw: (
        vanilla, [f"restore vanilla {MEMBER} ({digest(raw)[:16]} -> {VANILLA_SHA[:16]})"])})
    outputs = builder.finish()
    if set(outputs) != {TITLE, TABLE}:
        raise ValueError(f"sorties inattendues : {sorted(outputs)}")
    old = oead.Sarc(unpack(files["content/" + TITLE]))
    new = oead.Sarc(unpack(outputs[TITLE]))
    names = {item.name for item in old.get_files()}
    changed = {name for name in names
               if bytes(old.get_file(name).data) != bytes(new.get_file(name).data)}
    if names != {item.name for item in new.get_files()} or changed != {MEMBER}:
        raise ValueError(f"changement inattendu dans TitleBG : {changed}")
    if digest(bytes(old.get_file(MEMBER).data)) != AIDED_SHA:
        raise ValueError("le membre de la source n'est pas celui de l'aide")
    if digest(bytes(new.get_file(MEMBER).data)) != VANILLA_SHA:
        raise ValueError("le membre restauré n'est pas le vanilla")
    # The delivery flow, and everything else validated in game, is untouched.
    if bytes(old.get_file(FLOW_MEMBER).data) != bytes(new.get_file(FLOW_MEMBER).data):
        raise ValueError("le flux de livraison a changé")
    files.update({"content/" + name: raw for name, raw in outputs.items()})
    hashes = {name: digest(raw) for name, raw in sorted(files.items())}
    build_id = hashlib.sha256(json.dumps(hashes, sort_keys=True,
                              separators=(",", ":")).encode()).hexdigest()[:16]
    target = (output / build_id).resolve()
    if not target.is_relative_to(output.resolve()):
        raise ValueError("candidat hors du dossier de sortie")
    for name, raw in files.items():
        path = (target / name).resolve()
        if not path.is_relative_to(target):
            raise ValueError("membre hors du candidat")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"candidat immuable modifié : {name}")
        path.write_bytes(raw)
    result = dict(manifest)
    result.update({
        "status": "requires_in_game_validation",
        "validation_aids": {"status": "removed", "removed_by": "build_vanilla_locomotion",
                            "restored_member": MEMBER,
                            "restored_sha256": VANILLA_SHA,
                            "previous": aid},
        "vanilla_locomotion": {
            "parent_build": source.name,
            "parent_path": source.relative_to(ROOT).as_posix(),
            "reason": "packs de partie : le jeu retrouve sa vitesse d'origine",
            "source_changes": builder.changes,
        },
        "files": {name[8:]: value for name, value in hashes.items()
                  if name.startswith("content/")},
        "native_files": {name: hashes[name] for name in manifest["native_files"]},
    })
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = target / "manifest.json"
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("manifeste immuable modifié")
    path.write_bytes(encoded)
    return target


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    print(build(arguments.source, arguments.output))
