import unittest
from tools.build_runtime_cleanup import REMOVED, strip_probes


class CleanupTests(unittest.TestCase):
    def files(self):
        result = {name: (f"[{group}]\nmoduleMatches = 0x6267BFD0\n"
                        f"probe{i}:\n0x{0x2000000 + i*4:x} = b probe{i}\n").encode()
                  for i, (name, group) in enumerate(REMOVED.items())}
        result.update({"patch_runtime.asm": b"[Runtime]\n0x03000000 = nop\n",
                       "content/Pack/TitleBG.pack": b"unchanged resource"})
        return result

    def test_removes_only_probes_preserving_resources_and_runtime(self):
        files = self.files()
        cleaned, sites = strip_probes(files)
        self.assertEqual(cleaned, {n: b for n, b in files.items() if n not in REMOVED})
        self.assertEqual(sites, [0x2000000, 0x2000004, 0x2000008])
        self.assertTrue(REMOVED.keys() <= files.keys())

    def test_refuses_runtime_symbol_dependency(self):
        files = self.files()
        files["patch_runtime.asm"] += b"b probe0\n"
        with self.assertRaisesRegex(ValueError, "references diagnostic"):
            strip_probes(files)

    def test_refuses_overlapping_hook(self):
        files = self.files()
        files["patch_runtime.asm"] += b"0x02000004 = nop\n"
        with self.assertRaisesRegex(ValueError, "overlapping hook"):
            strip_probes(files)

    def test_refuses_unexpected_patch_group(self):
        files = self.files()
        files[next(iter(REMOVED))] += b"[UnknownRuntime]\n"
        with self.assertRaisesRegex(ValueError, "unexpected patch group"):
            strip_probes(files)
