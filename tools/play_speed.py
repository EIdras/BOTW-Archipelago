"""Immutable, opt-in locomotion variant of a verified play pack."""
import argparse
import io
import math
from pathlib import Path

import oead
import rstb

from botw_patch.resources import ResourceBuilder, unpack, vanilla_digest
from tools.build_pack_from_source import verify_pack
from tools.build_resources_from_source import digest, encode, pack_path, TITLE, TABLE
from tools.build_plateau_speed import faster_animation
from tools.build_vanilla_locomotion import MEMBER, VANILLA_SHA


def speed_argument(value):
    try:
        speed = float(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError('speed: a number between 0.1 and 10') from None
    if not math.isfinite(speed) or not 0.1 <= speed <= 10:
        raise argparse.ArgumentTypeError('speed: a finite number between 0.1 and 10')
    return speed


def variant(source: Path, speed: float, output: Path) -> Path:
    speed = speed_argument(speed)
    manifest = verify_pack(source)
    if manifest.get('locomotion_speed_multiplier', 1) != 1:
        raise ValueError('choose a base pack without a speed multiplier')
    if speed == 1:
        return source
    builder = ResourceBuilder(source / 'content')

    def player(raw):
        if vanilla_digest(raw) != VANILLA_SHA:
            raise ValueError('base player actor is not vanilla; multiplier refused')
        archive = oead.Sarc(unpack(raw))
        writer = oead.SarcWriter.from_sarc(archive)
        edits = {}
        for member in ('Actor/AS/Player_Move.bas', 'Actor/AS/Player_ClimbMove.bas'):
            previous = bytes(archive.get_file(member).data)
            data, edits[member] = faster_animation(previous, member, speed, preserve_size=False)
            # Only existing float values change; AAMP node/parameter counts
            # stay fixed. Float pooling can change the serialized byte count.
            # Retain the verified vanilla allocation and add aligned growth.
            if not builder.table.is_in_table(member):
                raise ValueError(f'reference allocation missing: {member}')
            growth = max(0, len(data) - len(previous))
            builder.table.set_size(member, builder.table.get_size(member)
                                   + ((growth + 31) & ~31))
            writer.files[member] = data
        return bytes(oead.yaz0.compress(bytes(writer.write()[1]))), edits

    builder.patch_archive(TITLE, {MEMBER: player})
    replacements = builder.finish()
    table = rstb.ResourceSizeTable(unpack(replacements[TABLE]), True)
    original = rstb.ResourceSizeTable(unpack((source / 'content' / TABLE).read_bytes()), True)
    for name in (TITLE, MEMBER):
        if original.get_size(name) is not None:
            table.set_size(name, max(table.get_size(name) or 0, original.get_size(name)))
    stream = io.BytesIO()
    table.write(stream, True)
    replacements[TABLE] = bytes(oead.yaz0.compress(stream.getvalue()))
    files = {p.relative_to(source).as_posix(): p.read_bytes()
             for p in source.rglob('*') if p.is_file() and p.name != 'manifest.json'}
    files.update({pack_path(name): raw for name, raw in replacements.items()})
    manifest.pop('build_id')
    manifest.update(locomotion_speed_multiplier=speed, gameplay_aids=True,
                    locomotion_base_pack=source.name, status='requires_in_game_validation')
    # DLC files (stalls) sit at the pack's root, the rest in content/.
    manifest['files'] = {name: digest(files[pack_path(name)]) for name in manifest['files']}
    for name in ('tools/play_speed.py', 'tools/build_plateau_speed.py'):
        manifest['source_hashes'][name] = digest((Path(__file__).resolve().parents[1] / name).read_bytes())
    identity = digest(encode(manifest))[:16]
    manifest['build_id'] = identity
    files['manifest.json'] = encode(manifest)
    target = output.resolve() / identity
    if target.exists():
        verify_pack(target)
        if any((target / name).read_bytes() != raw for name, raw in files.items()):
            raise ValueError('immutable speed variant changed')
        return target
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    verify_pack(target, manifest['seed_binding'])
    return target
