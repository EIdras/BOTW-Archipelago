"""Immutable, read-only v208 request-stage probe; no grant or retry change."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.build/champion-delivery/56ec5e32a5197030'
SITES = (0x031c82e0, 0x031c82fc, 0x031ca02c)
CALLER = 0x02ddf80c
PATCH = 'patch_request_reject_trace.asm'


def trace_source():
    lines = ['[BOTW_AP_RequestReject_V208]', 'moduleMatches = 0x6267BFD0',
             '; Read-only observations of wrapper calls. Only stack/trace writes.',
             '.origin = codecave', 'apRejectData:', '.int 0x4150524a',
             '.int 1', '.int 0', '.int 0'] + ['.int 0'] * 24
    for i, site in enumerate(SITES):
        # 031c80b4 frame 0x418 + outer 031ca008 LR at +0x14.
        caller_offset = 0x45c if i < 2 else 68  # includes our 48-byte frame
        manager = 'r27' if i < 2 else 'r31'
        lines += [f'apRejectStage{i}:', '.int 0x9421ffd0 ; stwu r1,-48(r1)',
                  'stw r0, 8(r1)', 'stw r9, 12(r1)', 'stw r10, 16(r1)',
                  'stw r11, 20(r1)', 'stw r12, 24(r1)',
                  '.int 0x7c000026 ; mfcr r0', 'stw r0, 28(r1)',
                  f'lwz r9, {caller_offset}(r1)', 'lis r10, 0x02dd',
                  'ori r10, r10, 0xf80c', 'cmpw r9, r10',
                  f'bne apRejectRestore{i}',
                  'lis r11, apRejectData@ha', 'addi r11, r11, apRejectData@l',
                  'li r9, 1', 'stw r9, 12(r11)', '.int 0x7c0004ac ; sync',
                  'lwz r12, 8(r11)', 'addi r12, r12, 1',
                  f'addi r10, r11, {16+i*32}',
                  f'lwz r9, {caller_offset}(r1)',
                  'stw r3, 4(r10)', 'stw r9, 8(r10)', f'stw {manager}, 12(r10)']
        lines += ['lwz r9, 56(r1)' if i == 2 else 'li r9, 0',
                  'stw r9, 16(r10)', '.int 0x7c0004ac ; sync', 'stw r12, 0(r10)',
                  '.int 0x7c0004ac ; sync', 'stw r12, 8(r11)',
                  '.int 0x7c0004ac ; sync', 'li r9, 0', 'stw r9, 12(r11)',
                  f'apRejectRestore{i}:',
                  'lwz r0, 28(r1)', '.int 0x7c0ff120 ; mtcrf 255,r0',
                  'lwz r0, 8(r1)', 'lwz r9, 12(r1)', 'lwz r10, 16(r1)',
                  'lwz r11, 20(r1)', 'lwz r12, 24(r1)', 'addi r1, r1, 48',
                  '.int 0x2c030000 ; replay cmpwi r3,0', f'b 0x{site+4:08x}',
                  f'0x{site:08x} = b apRejectStage{i}']
    return '\n'.join(lines) + '\n'


def verify_rpx(rpx):
    for address in SITES:
        if rpx.read(address, 4) != bytes.fromhex('2c030000'):
            raise ValueError(f'request probe anchor changed: {address:#x}')
    for address, expected in ((0x031c80b4, '9421fbe8'),
                              (0x031ca00c, '9421fff0'),
                              (0x031ca014, '90010014'),
                              (0x031c80c8, '9001041c'),
                              (0x02ddf808, '483ea801')):
        if rpx.read(address, 4) != bytes.fromhex(expected):
            raise ValueError(f'request probe call/frame changed: {address:#x}')


def build():
    sys.path.insert(0, str(ROOT / 'tools/cemu'))
    from rpx import Rpx
    verify_rpx(Rpx())
    manifest = json.loads((SOURCE / 'manifest.json').read_text(encoding='utf-8'))
    files = {}
    for prefix, section in (('content/', 'files'), ('', 'native_files')):
        for name, digest in manifest[section].items():
            path = (SOURCE / prefix / name).resolve()
            if not path.is_relative_to(SOURCE.resolve()):
                raise ValueError('source path escapes build')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('source build changed')
            if not prefix and any(f'0x{site:08x} =' in raw.decode().lower() for site in SITES):
                raise ValueError('probe hook collision')
            files[prefix+name] = raw
    for name in ('rules.txt', 'delivery_catalog.json'):
        files[name] = (SOURCE / name).read_bytes()
    if hashlib.sha256(files['delivery_catalog.json']).hexdigest() != manifest['native_delivery_catalog_sha256']:
        raise ValueError('source catalogue changed')
    files[PATCH] = trace_source().encode('ascii')
    hashes = {n: hashlib.sha256(v).hexdigest() for n,v in sorted(files.items())}
    identity = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:16]
    target = ROOT / '.build/request-reject-trace' / identity
    manifest['native_files'][PATCH] = hashes[PATCH]
    manifest['request_reject_trace'] = {'version': 1, 'parent_build': SOURCE.name,
        'sites': list(SITES), 'caller_return': CALLER, 'scope': 'wrapper_calls_only',
        'limitations': ['No owner-generation correlation; compare before/after stage sequences.',
                        'Cemu assembly/runtime validation pending.']}
    files['manifest.json'] = (json.dumps(manifest, indent=2)+'\n').encode('utf-8')
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError('immutable trace build changed')
        path.write_bytes(raw)
    return target


if __name__ == '__main__':
    print(build())
