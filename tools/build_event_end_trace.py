"""Bounded executor-end diagnostic; never acknowledges completion or changes ownership."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_ui_lifecycle import trace_source as lifecycle_source
from tools.build_owned_presentation import Rpx
from tools.cemu.guest import MEM2_END, below

SOURCE = ROOT / '.build/ledger-validation/314914ec4d35a853'
OWNER = 25187360  # Verified immutable 6aa layout; checked again on startup.
MAGIC, CAPACITY, STRIDE = 0x41504546, 512, 256
SITES = (
    (0x031C9498, 0x907D0000, 'executor_created', 30, 0x118, 0x120),
    (0x031D8A9C, 0x7F43D378, 'executor_terminal_return', 30, 0x18c, 0x1cc),
    (0x031C9B1C, 0x815B00FC, 'manager_terminal', 30, 0x18c, 0x1cc),
    (0x031C9BD8, 0x3BBD0001, 'manager_slot_released', 30, 0, 4),
)


def trace_source():
    source = lifecycle_source(SITES).replace('BOTW_AP_UILifecycle_V208', 'BOTW_AP_EventEnd_V208')
    source = source.replace('apLife', 'apEnd').replace('0x41504c46', f'0x{MAGIC:08x}')
    # 4096*32 and 512*256 are the same bounded allocation.
    source = source.replace('.int 4096\n.int 32', '.int 512\n.int 256')
    source = source.replace('cmplwi r9, 4096', 'cmplwi r9, 512').replace('slwi r10, r9, 5', 'slwi r10, r9, 8')
    for index, (_, _, _, reg, first, second) in enumerate(SITES, 1):
        label = f'apEnd{index}'
        begin, end = source.index(label+':'), source.index(label+'Done:')
        part = source[begin:end]
        # Only our active generation; ignore ordinary per-frame return0.
        prefix = [f'lis r12, 0x{(OWNER+0x8000)>>16:04x}', f'addi r12, r12, {OWNER&0xffff if OWNER&0xffff<32768 else (OWNER&0xffff)-65536}',
                  'lwz r0, 12(r12)', 'cmpwi r0, 0', f'beq {label}Done']
        if index == 2:
            prefix += ['cmpwi r26, 0', f'beq {label}Done']
        part = part.replace('lis r11, apEndData@ha', '\n'.join(prefix)+'\nlis r11, apEndData@ha')
        # The released instance is already destroyed: preserve pointer value only.
        if index == 4:
            part = part.replace(f'lwz r0, {first}(r{reg})', 'lwz r12, 20(r1)\nlwz r0, 0(r12)')
            part = part.replace(f'lwz r0, {second}(r{reg})', 'li r0, 0')
        anchor = 'stw r0, 28(r10)'
        extra = [anchor, f'lis r12, 0x{(OWNER+0x8000)>>16:04x}',
                 f'addi r12, r12, {OWNER&0xffff if OWNER&0xffff<32768 else (OWNER&0xffff)-65536}']
        for offset, dest in ((12,32),(8,36),(32,40),(28,44),(52,48),(48,52),(16,192)):
            extra += [f'lwz r0, {offset}(r12)', f'stw r0, {dest}(r10)']
        extra += [f'stw r{3 if index == 1 else 30}, 56(r10)',
                  'stw r26, 60(r10)' if index == 2 else 'li r0, 0\nstw r0, 60(r10)']
        if index != 4:
            # Source strings are used by vanilla code at these same object offsets.
            for field, dest in ((0x24 if index == 1 else 0x34,64), (0x70 if index == 1 else 0x80,128)):
                done = f'{label}String{dest}Done'
                extra += [f'lwz r12, {field}(r30)', 'lis r0, 0x0100', 'cmplw r12, r0', f'blt {done}',
                          *below(MEM2_END, 'r12', 'r0', done, margin=0x40)]
                for byte in range(63):
                    extra += [f'lbz r0, {byte}(r12)', f'stb r0, {dest+byte}(r10)', 'cmpwi r0, 0', f'beq {done}']
                extra += [done+':']
        part = part.replace(anchor, '\n'.join(extra))
        source = source[:begin]+part+source[end:]
    return source


def build():
    rpx = Rpx()
    for address, word, *_ in SITES:
        if rpx.read(address,4) != word.to_bytes(4,'big'):
            raise ValueError(f'Unexpected RPX anchor {address:#x}')
    manifest = json.loads((SOURCE/'manifest.json').read_text())
    files = {}
    for prefix,key in (('content/','files'),('','native_files')):
        for name,expected in manifest[key].items():
            path = (SOURCE/(prefix+name)).resolve()
            if not path.is_relative_to(SOURCE.resolve()):
                raise ValueError('Source path escape')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('Immutable source changed')
            files[prefix+name] = raw
    files['patch_event_end.asm'] = trace_source().encode()
    hashes = {n:hashlib.sha256(raw).hexdigest() for n,raw in sorted(files.items())}
    target = SOURCE.parent/hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()[:16]
    manifest.update(source_build=SOURCE.name,event_end_trace=1,
        native_files={n:h for n,h in hashes.items() if not n.startswith('content/')})
    files['manifest.json'] = (json.dumps(manifest,indent=2)+'\n').encode()
    files['rules.txt'] = (SOURCE/'rules.txt').read_bytes()
    for name,raw in files.items():
        path = target/name
        if path.exists() and path.read_bytes()!=raw:
            raise ValueError('Immutable target changed')
    for name,raw in files.items():
        path = target/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(raw)
    print(target)
    return target


if __name__ == '__main__':
    build()
