import argparse
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from tests.full_build import full_build

import oead
from botw_patch.resources import unpack, digest
from tools.play_speed import variant, speed_argument, TITLE, MEMBER
from tools.build_vanilla_locomotion import AIDED_SHA

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.build/packs-from-source/1c912b3869c94a1a'
STALLS = ROOT / '.build/packs-from-source/024441ae80c0c7bb'      # a seed with stall locations


class PlaySpeedTests(unittest.TestCase):
    @unittest.skipUnless(SOURCE.is_dir(), 'requires local source pack')
    @full_build
    def test_x6_handles_float_pool_size_change_and_preserves_allocation(self):
        import rstb
        from tools.play_speed import TABLE
        with tempfile.TemporaryDirectory() as directory:
            target = variant(SOURCE, 6, Path(directory))
            actors = []
            tables = []
            for pack in (SOURCE, target):
                title = oead.Sarc(unpack((pack / 'content' / TITLE).read_bytes()))
                actors.append(oead.Sarc(unpack(bytes(title.get_file(MEMBER).data))))
                tables.append(rstb.ResourceSizeTable(unpack((pack / 'content' / TABLE).read_bytes()), True))
            for member in ('Actor/AS/Player_Move.bas', 'Actor/AS/Player_ClimbMove.bas'):
                old, new = [bytes(a.get_file(member).data) for a in actors]
                growth = max(0, len(new) - len(old))
                self.assertGreaterEqual(tables[1].get_size(member),
                                        tables[0].get_size(member) + ((growth + 31) & ~31))
                from tools.build_plateau_speed import faster_animation
                expected, edits = faster_animation(old, member, 6, preserve_size=False)
                self.assertEqual(new, expected)
                self.assertTrue(edits)
                for edit in edits:
                    self.assertAlmostEqual(edit['after'], edit['before'] * 6, places=5)

    @unittest.skipUnless(STALLS.is_dir(), 'requires a local pack with stalls')
    @full_build
    def test_a_pack_with_dlc_files_keeps_them_at_its_root(self):
        # Seen in play: the variant of a seed with stalls failed on its aoc/ files.
        from tools.build_pack_from_source import verify_pack
        with tempfile.TemporaryDirectory() as directory:
            target = variant(STALLS, 3, Path(directory))
            manifest = verify_pack(target)
            dlc = [name for name in manifest['files'] if name.startswith('aoc/')]
            self.assertTrue(dlc)
            for name in dlc:
                self.assertEqual((target / name).read_bytes(), (STALLS / name).read_bytes())

    def test_direct_script_import_path_does_not_shadow_rstb_package(self):
        script = '''
import pathlib, runpy, sys
root = pathlib.Path.cwd()
sys.path.insert(0, str(root / "tools"))
runpy.run_path(str(root / "tools/play_session.py"), run_name="launcher_import_test")
from tools.play_speed import rstb
assert hasattr(rstb, "ResourceSizeTable"), rstb.__file__
assert pathlib.Path(rstb.__file__).resolve() != root / "tools/rstb.py"
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_multipliers_are_rejected(self):
        for value in ('nan', 'inf', '0', '-1', '100', 'abc'):
            with self.assertRaises(argparse.ArgumentTypeError):
                speed_argument(value)
        self.assertEqual(speed_argument('1.5'), 1.5)

    @unittest.skipUnless(SOURCE.is_dir(), 'requires local source pack')
    @full_build
    def test_x3_matches_historical_actor_without_altering_base_or_other_members(self):
        before = {p.relative_to(SOURCE): digest(p.read_bytes()) for p in SOURCE.rglob('*') if p.is_file()}
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(variant(SOURCE, 1, Path(directory)), SOURCE)
            target = variant(SOURCE, 3, Path(directory))
            old = oead.Sarc(unpack((SOURCE / 'content' / TITLE).read_bytes()))
            new = oead.Sarc(unpack((target / 'content' / TITLE).read_bytes()))
            self.assertEqual(digest(bytes(new.get_file(MEMBER).data)), AIDED_SHA)
            for item in old.get_files():
                if item.name != MEMBER:
                    self.assertEqual(bytes(item.data), bytes(new.get_file(item.name).data))
            for path in SOURCE.glob('*.asm'):
                self.assertEqual(path.read_bytes(), (target / path.name).read_bytes())
            self.assertEqual(variant(SOURCE, 3, Path(directory)), target)
            with self.assertRaises(ValueError):
                variant(target, 2, Path(directory))
        self.assertEqual(before, {p.relative_to(SOURCE): digest(p.read_bytes())
                                 for p in SOURCE.rglob('*') if p.is_file()})
