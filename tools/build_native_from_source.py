"""Rebuild the native component from maintained sources and an explicit RPX.

This is NOT an installable mod: resources/EventFlow and seed binding are a
separate next stage. No historical .build candidate is an input. Optional
standalone probes are emitted separately from runtime files. Embedded legacy
instrumentation is deliberately preserved pending a dedicated ABI audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path
                            if Path(p).resolve() != ROOT / 'tools']

from tools.cemu.guest import MEM2_END  # noqa: E402

RPX_SHA256 = 'ba58da5b95ce929e005d058ceb08b9b2788d1ab2bbc8a6c189bbadca0bb34d30'
SOURCE_FILES = (
    'native/cemu/legacy/patch_apInject.asm', 'native/cemu/ui_close_trace.asm',
    'tools/build_native_from_source.py', 'tools/build_scoped_text.py',
    'tools/build_owned_presentation.py', 'tools/native_presentation_join.py',
    'tools/build_event_end_trace.py', 'tools/build_rune_selection_sync.py',
    'tools/build_world_heart_withhold.py', 'tools/build_hero_soul_restore_withhold.py',
    'tools/build_event_request_trace.py', 'tools/build_ui_lifecycle.py',
    'tools/build_request_reject_trace.py', 'tools/build_tip_channel.py',
    'botw_client/tip_protocol.py', 'tools/build_tower_maps_native.py',
    'tools/build_weather_native.py', 'tools/cemu/guest.py',
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def generate(*, resource_gate=False, event_gate=False, tower_maps=False, bike_anywhere=False,
             mem2_end=MEM2_END):
    """Pure native assembly generation; no dump, candidate or Cemu access.
    tower_maps: the seed's maps are items, the towers' icons read APTower_NN
    (tools/build_tower_maps_native.py; the map opening's fallback is in every pack).
    bike_anywhere: the Master Cycle Zero anywhere outdoors (botw_patch/bike_anywhere.py).
    The weather hold of the Downpour trap is in every pack (tools/build_weather_native.py).
    mem2_end: where the game's main memory ends (tools/cemu/guest.py): the code follows
    no pointer beyond (Extended Memory moves it, tools/player_packs.py mem2_end())."""
    from tools.build_scoped_text import scoped_source
    from tools.build_owned_presentation import patch_native, owner_source
    from tools.build_rune_selection_sync import patch_injection as rune
    from tools.build_world_heart_withhold import patch_injection as heart
    from tools.build_hero_soul_restore_withhold import patch_injection as restore
    from tools.build_event_request_trace import trace_source as event
    from tools.build_ui_lifecycle import trace_source as lifecycle
    from tools.build_request_reject_trace import trace_source as reject

    legacy = (ROOT / 'native/cemu/legacy/patch_apInject.asm').read_bytes()
    injection = patch_native(scoped_source(legacy)).decode('utf-8').replace('\r\n', '\n')
    current_owner = owner_source()
    if injection.count(current_owner) != 1:
        raise ValueError('owner source is not unique')
    # The owner of the played packs (retired guard, optional gates).
    injection = injection.replace(current_owner,
        owner_source(2, retired_guard=True, resource_gate=resource_gate, event_gate=event_gate,
                     mem2_end=mem2_end))
    injection = restore(heart(rune(injection)))
    # The AP journal in the game's tip frame.
    from tools.build_tip_channel import compose as tip_channel
    injection = tip_channel(injection, mem2_end)
    from tools.build_tower_maps_native import patch_injection as tower_maps_stage
    injection = tower_maps_stage(injection, icons=tower_maps)
    # The Downpour trap's weather, held frame after frame (in every pack).
    from tools.build_weather_native import patch_injection as weather_stage
    injection = weather_stage(injection)
    if bike_anywhere:
        from botw_patch.bike_anywhere import patch_injection as bike_stage
        injection = bike_stage(injection)
    from tools.patch_lint import lint
    problems = lint(injection)
    if problems:
        raise ValueError('injection refused before Cemu: ' + '; '.join(problems[:5]))
    return {
        'runtime/patch_apInject.asm': injection.encode('utf-8'),
        'runtime/patch_event_request.asm': event().encode('utf-8'),
        'diagnostics/patch_ui_close_trace.asm': (ROOT / 'native/cemu/ui_close_trace.asm').read_bytes(),
        'diagnostics/patch_ui_lifecycle.asm': lifecycle(version=2).encode('utf-8'),
        'diagnostics/patch_request_reject_trace.asm': reject().encode('utf-8'),
    }


def build(rpx: Path, output: Path, *, resource_gate=False, event_gate=False, tower_maps=False,
          bike_anywhere=False, mem2_end=MEM2_END) -> Path:
    raw = rpx.read_bytes()
    if digest(raw) != RPX_SHA256:
        raise ValueError('incompatible RPX: provide the verified Wii U EUR v208 dump')
    files = generate(resource_gate=resource_gate, event_gate=event_gate, tower_maps=tower_maps,
                     bike_anywhere=bike_anywhere, mem2_end=mem2_end)
    source_hashes = {name: digest((ROOT / name).read_bytes()) for name in SOURCE_FILES}
    hashes = {name: digest(data) for name, data in sorted(files.items())}
    manifest = {
        'schema': 1, 'component': 'native_only',
        'status': 'not_installable_without_resources', 'installed': False,
        'platform': 'wiiu', 'revision': 'EUR v208', 'rpx_sha256': RPX_SHA256,
        'source_hashes': source_hashes, 'files': hashes,
        'options': {'owned_presentation': 2, 'retired_executor_guard': True,
                    'tip_channel': True,
                    'resource_gate': resource_gate, 'event_gate': event_gate, 'gameplay_aids': False,
                    'tower_map_icons': tower_maps, 'mem2_end': mem2_end},
        'runtime_files': sorted(n for n in files if n.startswith('runtime/')),
        'optional_diagnostics': sorted(n for n in files if n.startswith('diagnostics/')),
        'limits': ['resources_and_seed_binding_not_built',
                   'embedded_legacy_instrumentation_retained',
                   'standalone_probe_removal_not_validated_in_game'],
    }
    if bike_anywhere:   # only then, so that the other packs keep their identity
        from botw_patch import bike_anywhere as bike_stage
        manifest['options']['bike_anywhere'] = True
        manifest['source_hashes'].update({name: digest((ROOT / name).read_bytes())
                                          for name in bike_stage.SOURCE_FILES})
    identity = digest(encode(manifest))[:16]
    manifest['build_id'] = identity
    files['manifest.json'] = encode(manifest)
    target = output.resolve() / identity
    if target.exists():
        existing = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
        if existing != set(files):
            raise ValueError('native component is incomplete or contains unexpected files')
        for name, data in files.items():
            if (target / name).read_bytes() != data:
                raise ValueError(f'immutable native component changed: {name}')
        return target
    for name, data in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rpx', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / '.build/native-from-source')
    parser.add_argument('--resource-gate', action='store_true')
    parser.add_argument('--event-gate', action='store_true')
    args = parser.parse_args()
    print(build(args.rpx, args.output, resource_gate=args.resource_gate, event_gate=args.event_gate))
