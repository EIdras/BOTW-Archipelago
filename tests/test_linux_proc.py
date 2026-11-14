"""Linux discovery of the running Cemu emulator (tools/cemu/linux_proc.py).

A Cemu AppImage runs as two processes: the emulator (its command line is the
AppImage path) and the FUSE mount shim under /tmp/.mount_*. The helper keeps the
emulator, skips the shim, and prefers the AppImage match. Each fake process is a
<pid> directory holding a cmdline file: argv joined by NUL bytes, exactly as
/proc/<pid>/cmdline lays them out.
"""
import os
import tempfile
import unittest
from pathlib import Path

from tools.cemu import linux_proc


def write_cmdline(proc_dir: Path, pid: int, argv) -> None:
    """A fake /proc/<pid>: a directory with a cmdline file of argv joined by NUL."""
    pid_dir = proc_dir / str(pid)
    pid_dir.mkdir()
    raw = b"".join(entry.encode() + b"\x00" for entry in argv)
    (pid_dir / "cmdline").write_bytes(raw)


class FindCemuPidTest(unittest.TestCase):
    def test_returns_the_appimage_emulator_and_skips_the_mount_shim(self):
        with tempfile.TemporaryDirectory() as temp:
            proc_dir = Path(temp)
            write_cmdline(proc_dir, 111, ["/home/ac/Cemu/Cemu-2.6-x86_64.AppImage"])
            write_cmdline(proc_dir, 222, ["/tmp/.mount_ABCDEF12/AppRun.wrapped"])
            # A non-Cemu process is ignored as usual.
            write_cmdline(proc_dir, 333, ["/usr/bin/python", "run.py"])
            self.assertEqual(linux_proc.find_cemu_pid(environ={}, proc_dir=proc_dir), 111)

    def test_prefers_the_appimage_over_a_plain_cemu(self):
        with tempfile.TemporaryDirectory() as temp:
            proc_dir = Path(temp)
            write_cmdline(proc_dir, 444, ["/opt/cemu/Cemu"])
            write_cmdline(proc_dir, 555, ["/home/ac/Cemu/Cemu-2.6-x86_64.AppImage"])
            self.assertEqual(linux_proc.find_cemu_pid(environ={}, proc_dir=proc_dir), 555)

    def test_returns_a_non_appimage_cemu_when_none_is_running(self):
        with tempfile.TemporaryDirectory() as temp:
            proc_dir = Path(temp)
            write_cmdline(proc_dir, 666, ["/usr/local/bin/Cemu"])
            self.assertEqual(linux_proc.find_cemu_pid(environ={}, proc_dir=proc_dir), 666)

    def test_returns_none_when_no_cemu_process_is_present(self):
        with tempfile.TemporaryDirectory() as temp:
            proc_dir = Path(temp)
            write_cmdline(proc_dir, 777, ["/tmp/.mount_ZZZZ/AppRun.wrapped"])
            write_cmdline(proc_dir, 888, ["/usr/bin/whatever"])
            self.assertIsNone(linux_proc.find_cemu_pid(environ={}, proc_dir=proc_dir))

    def test_honours_an_explicit_botw_cemu_pid(self):
        with tempfile.TemporaryDirectory() as temp:
            proc_dir = Path(temp)
            write_cmdline(proc_dir, 1, ["/usr/local/bin/Cemu"])
            environ = {"BOTW_CEMU_PID": "4242"}
            self.assertEqual(linux_proc.find_cemu_pid(environ=environ, proc_dir=proc_dir), 4242)

    def test_rejects_a_non_positive_or_non_digit_explicit_pid(self):
        with tempfile.TemporaryDirectory() as temp:
            proc_dir = Path(temp)
            for bad in ("0", "-1", "abc", ""):
                with self.subTest(bad=bad):
                    with self.assertRaisesRegex(ValueError, "positive process ID"):
                        linux_proc.find_cemu_pid(environ={"BOTW_CEMU_PID": bad}, proc_dir=proc_dir)


if __name__ == "__main__":
    unittest.main()
