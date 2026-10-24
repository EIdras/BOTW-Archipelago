import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.build_native_from_source import ROOT, build, generate


class NativeSourceTests(unittest.TestCase):
    def test_resource_gate_changes_only_owner_extension(self):
        from tools.build_owned_presentation import owner_source
        old, new = generate(), generate(resource_gate=True)
        name = 'runtime/patch_apInject.asm'
        for key in old:
            if key != name:
                self.assertEqual(old[key], new[key])
        self.assertEqual(new[name], old[name].replace(
            owner_source(2, retired_guard=True, resource_gate=False).encode(),
            owner_source(2, retired_guard=True, resource_gate=True).encode()))

    def test_foreign_rpx_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'wrong.rpx').write_bytes(b'wrong revision')
            with self.assertRaisesRegex(ValueError, 'incompatible RPX'):
                build(root / 'wrong.rpx', root / 'out')
            self.assertFalse((root / 'out').exists())

    def test_optional_probes_have_no_runtime_dependents_or_hook_overlap(self):
        from tools.build_runtime_cleanup import strip_probes
        files = generate()
        flattened = {Path(name).name: data for name, data in files.items()}
        retained, sites = strip_probes(flattened)
        self.assertEqual(set(retained), {'patch_apInject.asm', 'patch_event_request.asm'})
        self.assertEqual(len(sites), 15)

    @unittest.skipUnless((ROOT / 'U-King.rpx').is_file(), 'requires verified RPX dump')
    def test_the_per_frame_hook_replays_the_instruction_it_replaces(self):
        from tools.cemu.rpx import Rpx
        text = generate()['runtime/patch_apInject.asm'].decode()
        self.assertEqual(text.count('\n0x031FA9B4 = bla apProbe\n'), 1)
        # lwz r12, 0x0(r30), then the load it feeds: the probe replays it last.
        self.assertEqual(Rpx().read(0x031FA9B4, 8), bytes.fromhex('819e0000800c0104'))
        self.assertIn('\napDone:\n    lwz   r12, 0x0(r30)', text)

    @unittest.skipUnless((ROOT / 'U-King.rpx').is_file(), 'requires verified RPX dump')
    def test_build_is_hermetic_reproducible_and_immutable(self):
        # Separate interpreter refuses reads/listings under .build and also
        # refuses the default RPX; only the explicitly copied input is allowed.
        script = r'''
import json, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve()
work = pathlib.Path(sys.argv[2]).resolve()
def audit(event, args):
    if event in ('open', 'os.listdir', 'os.scandir') and args and isinstance(args[0], (str, bytes)):
        p = pathlib.Path(args[0]).resolve()
        if p.is_relative_to(root / '.build') or p == root / 'U-King.rpx':
            raise RuntimeError('Forbidden historical/default input: ' + str(p))
sys.addaudithook(audit)
from tools.build_native_from_source import build
a = build(work / 'input.rpx', work / 'a')
b = build(work / 'input.rpx', work / 'b')
assert a.name == b.name
assert {p.relative_to(a).as_posix():p.read_bytes() for p in a.rglob('*') if p.is_file()} == {
    p.relative_to(b).as_posix():p.read_bytes() for p in b.rglob('*') if p.is_file()}
assert build(work / 'input.rpx', work / 'a') == a
(a / 'runtime/patch_apInject.asm').write_bytes(b'altered')
try:
    build(work / 'input.rpx', work / 'a')
except ValueError:
    pass
else:
    raise AssertionError('immutable artifact was overwritten')
print(a.name)
'''
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            (work / 'input.rpx').write_bytes((ROOT / 'U-King.rpx').read_bytes())
            result = subprocess.run([sys.executable, '-c', script, str(ROOT), str(work)],
                                    cwd=ROOT, text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_all_five_files_match_the_validated_play_pack(self):
        reference = ROOT / '.build/seed-bound-candidates/5e94d0a1880f1b2b'
        if not reference.is_dir(): self.skipTest('optional historical comparison pack absent')
        manifest = json.loads((reference / 'manifest.json').read_text(encoding='utf-8'))
        from tools.build_native_from_source import digest
        files = generate()
        self.assertEqual({Path(n).name for n in files}, set(manifest['native_files']))
        from unittest.mock import patch
        from tools import build_tip_channel as tip

        def code(text):
            # Instructions and labels only: the comments have been rewritten since.
            lines = (line.split(';', 1)[0].rstrip() for line in text.replace('\r\n', '\n').split('\n'))
            return '\n'.join(line for line in lines if line.strip()) + '\n'
        for name, raw in files.items():
            with self.subTest(name=name):
                validated = (reference / Path(name).name).read_bytes()
                if name == 'runtime/patch_apInject.asm':
                    # Every pack carries the AP journal (the tip channel): the
                    # validated file plus that composition, nothing else.
                    with patch.object(tip, 'FRAME_HOOK', code(tip.FRAME_HOOK)), \
                            patch.object(tip, 'TEXT_HOOK', code(tip.TEXT_HOOK)):
                        composed = tip.compose(code(validated.decode('utf-8')))
                    # Since then, the rune selection also takes the Master Cycle
                    # Zero (type 6): its type limit, 5 in the validated file.
                    from tools.build_rune_selection_sync import _TYPE_LIMIT
                    old_limit = '    cmpwi r12, 5\n    bge   apSelFinish'
                    self.assertEqual(composed.count(old_limit), 1)
                    composed = composed.replace(
                        old_limit, f'    cmpwi r12, {_TYPE_LIMIT}\n    bge   apSelFinish')
                    # And the map opening's fallback of the tower maps, in every pack.
                    from tools.build_tower_maps_native import patch_injection as tower_maps
                    composed = tower_maps(composed, icons=False)
                    # And the Downpour trap's weather hold, in every pack.
                    from tools.build_weather_native import patch_injection as weather
                    composed = weather(composed)
                    # And the pointers it follows end with the game's main memory
                    # (tools/cemu/guest.py), no longer at 0x60000000.
                    from tools.cemu.guest import MEM2_END, below
                    old_bind = 'lis r10, 0x6000\ncmplw r12, r10\nbge apOwnedBindDone'
                    old_join = 'lis r0, 0x5fff\nori r0, r0, 0xffc0'
                    self.assertEqual((composed.count(old_bind), composed.count(old_join)), (1, 2))
                    composed = composed.replace(old_bind, '\n'.join(
                        below(MEM2_END, 'r12', 'r10', 'apOwnedBindDone', margin=0x40)))
                    composed = composed.replace(old_join, '\n'.join(
                        below(MEM2_END, 'r12', 'r0', 'x', margin=0x40)[:2]))
                    # And the per-frame hook, moved off FPS++'s instruction (0x031FA97C):
                    # the one it replaces now is replayed last.
                    hook = ('apProbe:\n    stw   r0, 0x78(r30)\n', 'apDone:\n    blr\n',
                            '0x031FA97C = bla apProbe\n')
                    self.assertEqual([composed.count(old) for old in hook], [1, 1, 1])
                    composed = (composed.replace(hook[0], 'apProbe:\n')
                                .replace(hook[1], 'apDone:\n    lwz   r12, 0x0(r30)\n    blr\n')
                                .replace(hook[2], '0x031FA9B4 = bla apProbe\n'))
                    self.assertEqual(code(raw.decode('utf-8')), code(composed))
                else:
                    self.assertEqual(digest(raw), manifest['native_files'][Path(name).name])
                    self.assertEqual(raw, validated)


if __name__ == '__main__':
    unittest.main()
