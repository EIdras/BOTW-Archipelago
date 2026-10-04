from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools.build_resources_from_source import ROOT, UPDATE_HASHES, build
from tests.full_build import full_build


CEMU = Path.home() / "AppData/Roaming/Cemu"
CONTENT = CEMU / "mlc01/usr/title/0005000e/101c9500/content"


class ResourcesFromSourceTests(unittest.TestCase):
    def test_invalid_binding_is_rejected_before_reading_dump(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for token in (True, 0, -1, 0x80000000, "417391497"):
                with self.subTest(token=token), self.assertRaisesRegex(ValueError, "binding token"):
                    build(root / "absent", root / "out", binding_token=token)
            self.assertFalse((root / "out").exists())

    def test_foreign_dump_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "input/Pack").mkdir(parents=True)
            (root / "input/Pack/Bootup.pack").write_bytes(b"another dump")
            with self.assertRaisesRegex(ValueError, "unexpected Wii U update resource"):
                build(root / "input", root / "out", binding_token=417391497)
            self.assertFalse((root / "out").exists())

    @full_build
    @unittest.skipUnless(all((CONTENT / name).is_file() for name in UPDATE_HASHES),
                         "requires verified Wii U EUR v208 update")
    def test_clean_build_matches_play_pack_without_historical_or_installed_inputs(self):
        script = r'''
import json, pathlib, sys
root, work, cemu = (pathlib.Path(p).resolve() for p in sys.argv[1:])
def audit(event, args):
    if event in ('open', 'os.listdir', 'os.scandir') and args and isinstance(args[0], (str, bytes)):
        path = pathlib.Path(args[0]).resolve()
        if path.is_relative_to(root / '.build') or path.is_relative_to(cemu) or path == root / 'U-King.rpx':
            raise RuntimeError('Forbidden historical/installed input: ' + str(path))
sys.addaudithook(audit)
from tools.build_resources_from_source import build, digest, encode
# The pin below proves the build reproducible: no second build.
a = build(work / 'input', work / 'a', binding_token=417391497)
manifest = json.loads((a / 'manifest.json').read_text())
hashes = dict(manifest['files'])
hashes['delivery_catalog.json'] = digest((a / 'delivery_catalog.json').read_bytes())
# All 26 resources (7 message archives: Vilia's price; the sanctum's gate) + the delivery catalog.
assert len(manifest['files']) == 26
assert digest(encode(hashes)) == 'b1663f3953ed227a05dee5a4bb2ea1d9ba9e2e27894a176f5a70401ae66faeb3', 'new pin: ' + digest(encode(hashes))
assert manifest['gameplay_aids'] is False
assert manifest['status'] == 'not_installable'
(a / 'content/Pack/Bootup.pack').write_bytes(b'altered')
try:
    build(work / 'input', work / 'a', binding_token=417391497)
except ValueError as exc:
    assert 'immutable resource component modified' in str(exc), str(exc)
else:
    raise AssertionError('modified artifact was overwritten')
assert (a / 'content/Pack/Bootup.pack').read_bytes() == b'altered'
print('Exact resource/catalog match; isolated, reproducible and immutable.')
'''
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            for name in UPDATE_HASHES:
                path = work / "input" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(CONTENT / name, path)
            result = subprocess.run(
                [sys.executable, "-c", script, str(ROOT), str(work), str(CEMU)],
                cwd=ROOT, text=True, capture_output=True, timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
