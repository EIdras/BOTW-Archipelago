"""Cemu's process on Linux (tools/cemu/linuxmem.py) and the backend each platform gets."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

from tools import cemu_profile
from tools.cemu import linuxmem, mailbox

LINUX = sys.platform.startswith("linux")

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


def stat_line(name: bytes, state: bytes, start: int) -> bytes:
    """A /proc/<pid>/stat line: fields 4 to 21 numbered, field 22 the start time."""
    middle = b" ".join(str(n).encode() for n in range(4, 22))
    return b"4242 (" + name + b") " + state + b" " + middle + b" %d 0 0\n" % start


class ParseStatTest(unittest.TestCase):
    def test_state_and_start_time(self):
        self.assertEqual(linuxmem.parse_stat(stat_line(b"Cemu", b"S", 987654)), ("S", 987654))

    def test_a_name_with_spaces_and_parentheses(self):
        self.assertEqual(linuxmem.parse_stat(stat_line(b"a) (b) Z c", b"R", 5)), ("R", 5))


class CemuPidsTest(unittest.TestCase):
    def setUp(self):
        self.proc = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, self.proc, True)

    def process(self, pid, comm=None, cmdline=b""):
        folder = self.proc / str(pid)
        folder.mkdir()
        if comm is not None:
            (folder / "comm").write_bytes(comm + b"\n")
        (folder / "cmdline").write_bytes(cmdline)
        return folder

    def test_the_process_name_not_the_command_line(self):
        self.process(300, b"cemu")
        self.process(100, b"Cemu")
        self.process(200, b"python3", b"python3\0launcher.py\0--cemu\0/home/player/Cemu.AppImage\0")
        self.process(250, b"tail", b"tail\0/home/player/.local/share/Cemu/log.txt\0")
        self.process(50, b"Cemu-2.6-x86_64")
        self.process(400)                       # gone while listed
        (self.proc / "self").mkdir()
        self.assertEqual(linuxmem.cemu_pids(str(self.proc)), [100, 300])

    def test_no_proc(self):
        self.assertEqual(linuxmem.cemu_pids(str(self.proc / "missing")), [])

    @unittest.skipUnless(LINUX, "symbolic links of /proc/<pid>/exe")
    def test_an_appimage_by_the_binary_it_runs(self):
        os.symlink("/tmp/.mount_CemuAb/usr/bin/Cemu", self.process(500, b"AppRun") / "exe")
        os.symlink("/home/player/Cemu-2.6-x86_64.AppImage", self.process(600, b"Cemu-2.6-x86_6") / "exe")
        self.assertEqual(linuxmem.cemu_pids(str(self.proc)), [500])


class PlatformBranchTest(unittest.TestCase):
    """The Linux branches, chosen on any system by the platform name."""

    def test_cemu_running(self):
        with mock.patch.object(cemu_profile.sys, "platform", "linux"):
            with mock.patch.object(linuxmem, "cemu_pids", return_value=[42]):
                self.assertTrue(cemu_profile.cemu_running())
            with mock.patch.object(linuxmem, "cemu_pids", return_value=[]):
                self.assertFalse(cemu_profile.cemu_running())

    def test_cemu_pid(self):
        environ = {k: v for k, v in os.environ.items() if k != "BOTW_CEMU_PID"}
        with mock.patch.object(mailbox.sys, "platform", "linux"), mock.patch.dict(os.environ, environ, clear=True):
            for found, pid in (([7, 9], 7), ([], None)):
                flat = types.SimpleNamespace(cemu_pids=lambda found=found: found)
                with mock.patch.dict(sys.modules, {"linuxmem": flat}):
                    self.assertEqual(mailbox.cemu_pid(), pid)


@unittest.skipUnless(LINUX, "/proc/<pid>/stat and flock are Linux only")
class LinuxIdentityAndLockTest(unittest.TestCase):
    def test_a_process_that_exited_has_no_incarnation(self):
        child = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE)
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        first = linuxmem.incarnation(child.pid)
        self.assertEqual(first, linuxmem.incarnation(child.pid))
        self.assertTrue(first.startswith(f"{child.pid}:"))
        child.stdin.close()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:          # exited, not reaped yet: a zombie
            state, _ = linuxmem.parse_stat(Path(f"/proc/{child.pid}/stat").read_bytes())
            if state == "Z":
                break
            time.sleep(0.01)
        self.assertEqual(state, "Z")
        with self.assertRaises(RuntimeError):
            linuxmem.incarnation(child.pid)
        child.wait()
        with self.assertRaises(RuntimeError):
            linuxmem.incarnation(child.pid)

    def test_one_publisher_per_emulator(self):
        from tools.cemu.owned_presentation import publisher_lock
        folder = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, folder, True)
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": folder}):
            with publisher_lock(4242):
                with self.assertRaises(RuntimeError):
                    with publisher_lock(4242):
                        pass
                with publisher_lock(4243):
                    pass
            with publisher_lock(4242):
                pass


if __name__ == "__main__":
    unittest.main()
