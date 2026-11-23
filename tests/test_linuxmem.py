"""Cemu's memory on Linux (tools/cemu/linuxmem.py) and the backend each platform gets."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

from tools.cemu import linuxmem, mailbox

MAPS = b"""\
00400000-00452000 r-xp 00000000 08:02 173521      /usr/bin/Cemu
00651000-00652000 rw-p 00051000 08:02 173521      /usr/bin/Cemu
7f0000000000-7f0100000000 ---p 00000000 00:00 0
7f0100000000-7f0100001000 rw-p 00000000 00:00 0
7f2000000000-7f2000400000 r--p 00000000 08:02 9   /home/player/a path (with spaces)
7ffd8c000000-7ffd8c021000 rw-p 00000000 00:00 0   [stack]
not a mapping
ffffffffff600000-ffffffffff601000 --xp 00000000 00:00 0   [vsyscall]
ffffffffff700000-ffffffffff701000 r--p 00000000 00:00 0   [above user space]
"""

# Holds a known buffer, prints its address, then prints it again once told to.
CHILD = r"""
import ctypes, sys
buffer = ctypes.create_string_buffer(b"APLINUXMEM-READ!", 16)
print(ctypes.addressof(buffer), flush=True)
sys.stdin.readline()
print(buffer.raw.hex(), flush=True)
sys.stdin.readline()
"""


class ParseMapsTest(unittest.TestCase):
    def test_readable_mappings_in_user_space(self):
        self.assertEqual(list(linuxmem.parse_maps(MAPS)), [
            (0x00400000, 0x52000), (0x00651000, 0x1000), (0x7f0100000000, 0x1000),
            (0x7f2000000000, 0x400000), (0x7ffd8c000000, 0x21000)])

    def test_minimum_size(self):
        self.assertEqual(list(linuxmem.parse_maps(MAPS, min_size=0x100000)),
                         [(0x7f2000000000, 0x400000)])


class BackendTest(unittest.TestCase):
    def test_the_client_opens_cemu_with_the_platform_backend(self):
        backend = Path(sys.modules[mailbox.Process.__module__].__file__)
        self.assertEqual(backend.parent, Path(mailbox.__file__).parent)
        self.assertEqual(backend.name, "winmem.py" if sys.platform == "win32" else "linuxmem.py")


@unittest.skipUnless(sys.platform.startswith("linux"), "/proc/<pid>/mem is Linux only")
class LinuxProcessTest(unittest.TestCase):
    def setUp(self):
        self.child = subprocess.Popen([sys.executable, "-c", CHILD], text=True,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.addCleanup(self._stop_child)
        self.address = int(self.child.stdout.readline())

    def _stop_child(self):
        self.child.kill()
        self.child.communicate()

    def _child_buffer(self):
        self.child.stdin.write("\n")
        self.child.stdin.flush()
        return bytes.fromhex(self.child.stdout.readline().strip())

    def test_read_write_and_regions(self):
        with linuxmem.Process(self.child.pid, writable=True) as process:
            self.assertEqual(process.read(self.address, 16), b"APLINUXMEM-READ!")
            self.assertTrue(any(base <= self.address < base + size
                                for base, size in process.regions(min_size=1 << 12)))
            self.assertTrue(process.write(self.address, b"APLINUXMEM-WROTE"))
            self.assertEqual(process.read(self.address, 16), b"APLINUXMEM-WROTE")
            self.assertEqual(self._child_buffer(), b"APLINUXMEM-WROTE")

    def test_unreadable_memory_fails_like_winmem(self):
        with linuxmem.Process(self.child.pid, writable=True) as process:
            self.assertIsNone(process.read(0, 16))
            self.assertFalse(process.write(0, b"x"))
            self.assertIsNone(process.read(self.address, 0))
        self.assertIsNone(process.h)
        self.assertIsNone(process.read(self.address, 16))

    def test_read_only_process_refuses_writes(self):
        with linuxmem.Process(self.child.pid) as process:
            self.assertEqual(process.read(self.address, 4), b"APLI")
            with self.assertRaises(PermissionError):
                process.write(self.address, b"x")

    def test_missing_process(self):
        gone = subprocess.Popen([sys.executable, "-c", ""])
        gone.wait()
        with self.assertRaises(FileNotFoundError):
            linuxmem.Process(gone.pid)

    @unittest.skipIf(sys.platform.startswith("linux") and os.geteuid() == 0, "root reads anything")
    def test_a_process_this_one_did_not_start_names_ptrace_scope(self):
        with self.assertRaises(PermissionError) as raised:
            linuxmem.Process(1)
        self.assertIn("ptrace_scope", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
