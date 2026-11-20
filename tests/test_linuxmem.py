"""tools/cemu/linuxmem.Process over /proc/self, without Cemu running.

/proc/self is this process: readable, and writable when opened writable, so it
exercises read, write and regions end to end. A foreign pid that does not exist
must raise at open, and a read into an unmapped page must return None.
"""
import os
import unittest

from tools.cemu import linuxmem


def _writable_base(pid: int) -> int:
    """Base of a readable+writable mapped region of `pid` (its heap/stack/brk)."""
    with open(f"/proc/{pid}/maps") as stream:
        for line in stream.read().splitlines():
            perms = line.split()[1]
            base = int(line.split()[0].split("-")[0], 16)
            if len(perms) >= 2 and perms[0] == "r" and perms[1] == "w":
                return base
    raise RuntimeError("no writable region found")


class LinuxMemTest(unittest.TestCase):
    def test_read_write_round_trip_through_proc_self(self):
        # A real, mapped, writable host address in this process.
        pid = os.getpid()
        base = _writable_base(pid)
        with linuxmem.Process(pid, writable=True) as p:
            self.assertEqual(p.pid, pid)
            self.assertTrue(p.writable)
            sample = b"0123456789"
            p.write(base, sample)
            self.assertEqual(p.read(base, len(sample)), sample)

    def test_read_only_cannot_write(self):
        with linuxmem.Process(os.getpid(), writable=False) as p:
            with self.assertRaises(PermissionError):
                p.write(0, b"x")

    def test_regions_yields_readable_non_guarded_ranges(self):
        with linuxmem.Process(os.getpid()) as p:
            regions = list(p.regions())
            self.assertTrue(regions, "no readable region in /proc/self/maps")
            self.assertGreaterEqual(regions[0][1], 0x1000)

    def test_missing_process_raises_at_open(self):
        with self.assertRaises(OSError):
            linuxmem.Process(2 ** 22, writable=True)   # no such pid here

    def test_read_of_an_unmapped_address_returns_none(self):
        # The NULL page is never mapped; the read must fail wholesale (None).
        with linuxmem.Process(os.getpid()) as p:
            self.assertIsNone(p.read(0, 0x1000))


if __name__ == "__main__":
    unittest.main()
