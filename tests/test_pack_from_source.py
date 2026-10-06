import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from botw_client.session import session_token
from tools.build_pack_from_source import ROOT, load_seed
from tools.build_resources_from_source import UPDATE_HASHES, digest, encode
from tests.full_build import full_build

CEMU = Path.home() / "AppData/Roaming/Cemu"
CONTENT = CEMU / "mlc01/usr/title/0005000e/101c9500/content"
REPORT = ROOT / ".build/play-seeds/08278964164390492688/analysis.json"


def write_seed(folder, *, corrupt_manifest=False, duplicate=False):
    slot = {"schema": 1, "game": "Breath of the Wild", "seed": "test-seed", "slot": 1,
            "slot_name": "Player", "slot_data": {"world_schema": 2, "client_schema": 3}}
    slot["content_sha256"] = digest(json.dumps(slot, ensure_ascii=False, sort_keys=True,
                                              separators=(",", ":")).encode())
    if corrupt_manifest:
        slot["slot_name"] = "altered"
    archive = folder / "seed.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("slot.apbotw.json", encode(slot))
        if duplicate:
            zipped.writestr("duplicate.apbotw.json", encode(slot))
    identity = {"seed": "test-seed", "team": 0, "slot": 1, "data_package_checksum": "checksum"}
    identity["token"] = session_token(("test-seed", 0, 1, "checksum"))
    report = {"status": "passed", "scope": "generated_solo_ap_server",
              "archive": str(archive), "archive_sha256": digest(archive.read_bytes()),
              "audit": {"seed": "test-seed", "slots": {"1": "Player"}},
              "delivery": {"sessions": {"1": identity}}}
    path = folder / "analysis.json"
    path.write_bytes(encode(report))
    return path, archive


class IdentityTests(unittest.TestCase):
    def test_relocated_archive_keeps_the_same_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report, archive = write_seed(root)
            expected = load_seed(report, 1)
            moved = root / "relocated.zip"
            archive.rename(moved)
            self.assertEqual(load_seed(report, 1, moved), expected)

    def test_rehashed_archive_does_not_hide_a_corrupt_slot_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            report, _ = write_seed(Path(temp), corrupt_manifest=True)
            with self.assertRaisesRegex(ValueError, "slot manifest checksum"):
                load_seed(report, 1)

    def test_duplicate_slot_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            report, _ = write_seed(Path(temp), duplicate=True)
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                load_seed(report, 1)

    def test_inconsistent_token_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            report, _ = write_seed(Path(temp))
            data = json.loads(report.read_text())
            data["delivery"]["sessions"]["1"]["token"] += 1
            report.write_bytes(encode(data))
            with self.assertRaisesRegex(ValueError, "identity/token"):
                load_seed(report, 1)


@unittest.skipUnless(REPORT.is_file() and (ROOT / "U-King.rpx").is_file()
                     and all((CONTENT / n).is_file() for n in UPDATE_HASHES),
                     "requires verified dumps and audited play seed")
class CompletePackTests(unittest.TestCase):
    @full_build
    def test_reproducible_isolated_pack_selection_and_integrity(self):
        script = r'''
import json, pathlib, sys
root, work, cemu = (pathlib.Path(p).resolve() for p in sys.argv[1:])
def audit(event, args):
    if event in ('open', 'os.listdir', 'os.scandir') and args and isinstance(args[0], (str, bytes)):
        path = pathlib.Path(args[0]).resolve()
        if path.is_relative_to(root / '.build') or path.is_relative_to(cemu) or path == root / 'U-King.rpx':
            raise RuntimeError('Forbidden historical/installed input: ' + str(path))
sys.addaudithook(audit)
from tools.build_pack_from_source import build, verify_pack, load_seed, RUNTIME, DIAGNOSTICS
from tools.build_resources_from_source import digest, encode
def create(output, diagnostics=True):
    return build(work/'input', work/'input.rpx', work/'analysis.json', 1, output,
                 archive=work/'seed.zip', diagnostics=diagnostics)
# The pin below proves the build reproducible: no second build.
a = create(work/'a')
def tree(path):
    return {p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()}
hashes = {n:digest(raw) for n,raw in tree(a).items() if n != 'manifest.json'}
# Every installed file (metadata excluded): the native code, the resources,
# the Archipelago key item (actor, icon, ActorInfo, texts in 7 languages), the sanctum's gate, the gifts of the Zora King and Kima,
# Goron City's armor shop.
assert len(hashes) == 40
assert digest(encode(hashes)) == '5c307970eb9e5c5a71467956bac4705d7bd3723580c4cb979af5e30b09887320', 'new pin: ' + digest(encode(hashes))
binding = load_seed(work/'analysis.json', 1, work/'seed.zip')
verify_pack(a, binding)
try:
    verify_pack(a, dict(binding, slot=2))
except ValueError:
    pass
else:
    raise AssertionError('foreign seed accepted')
(a/'unexpected.asm').write_text('unexpected')
try:
    verify_pack(a)
except ValueError:
    pass
else:
    raise AssertionError('extra native code accepted')
(a/'unexpected.asm').unlink()
original = (a/'delivery_catalog.json').read_bytes()
(a/'delivery_catalog.json').write_bytes(b'altered')
try:
    verify_pack(a)
except ValueError:
    pass
else:
    raise AssertionError('altered catalog accepted')
(a/'delivery_catalog.json').write_bytes(original)
slim = create(work/'slim', diagnostics=False)
sm = verify_pack(slim, binding)
assert set(sm['native_files']) == RUNTIME
assert not sm['diagnostics_enabled']
assert set(tree(a))-set(tree(slim)) == DIAGNOSTICS
assert all((a/n).read_bytes()==raw for n,raw in tree(slim).items() if n!='manifest.json')
print('Complete pack: exact payload, hermetic rebuild, integrity and diagnostics selection OK')
'''
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            report = json.loads(REPORT.read_text(encoding="utf-8"))
            shutil.copyfile(REPORT, work / "analysis.json")
            shutil.copyfile(Path(report["archive"]), work / "seed.zip")
            shutil.copyfile(ROOT / "U-King.rpx", work / "input.rpx")
            from botw_patch.status_item import INPUT_HASHES as STATUS_INPUTS
            for name in {**UPDATE_HASHES, **STATUS_INPUTS}:
                path = work / "input" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(CONTENT / name, path)
            result = subprocess.run([sys.executable, "-c", script, str(ROOT), str(work), str(CEMU)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=240)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            from tools import play_session
            seed = work / "seeds" / report["audit"]["seed"]
            seed.mkdir(parents=True)
            shutil.copyfile(REPORT, seed / "analysis.json")
            candidate = next((work / "a").iterdir())
            with patch.object(play_session, "PLAY_SEEDS", seed.parent), \
                    patch.object(play_session, "ROOT", work / "no-historical-candidates"):
                self.assertEqual(play_session.find_seed(seed.name, candidate)[2], candidate)


if __name__ == "__main__":
    unittest.main()
