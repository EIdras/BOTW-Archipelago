"""The client's setup inside Archipelago (botw_world/client): the pinned
wheels, checked and unpacked as pip would; the project's code unpacked once per
version; one window at a time, later launches handing it their file."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.package_native import PAYLOAD, client_payload, package  # noqa: E402


def _load():
    """botw_world/client without the world's __init__ (which needs Archipelago)."""
    folder = ROOT / "botw_world/client"
    spec = importlib.util.spec_from_file_location("botw_client_setup", folder / "__init__.py",
                                                  submodule_search_locations=[str(folder)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


client = _load()


def wheel(name: str = "pkg") -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(f"{name}/__init__.py", "VALUE = 1\n")
        archive.writestr(f"{name}-1.0.data/platlib/runtime.dll", b"dll")
    return stream.getvalue()


def pinned(data: bytes, name: str = "pkg") -> dict:
    return {"name": name, "file": f"{name}-1.0-py3-none-any.whl", "url": f"https://example.invalid/{name}",
            "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class PinTests(unittest.TestCase):
    def test_every_library_is_pinned_for_archipelagos_python_from_pypi(self):
        pins = json.loads((ROOT / "botw_world/client/wheels.json").read_bytes())
        self.assertEqual(set(pins["libraries"]), {"oead", "numpy", "evfl", "rstb"})
        for name, entry in pins["libraries"].items():
            self.assertIn("cp313", entry["wheels"], name)       # Archipelago 0.6.7
            for wheel_pin in entry["wheels"].values():
                self.assertTrue(wheel_pin["url"].startswith("https://files.pythonhosted.org/"), wheel_pin)
                self.assertTrue(wheel_pin["url"].endswith("/" + wheel_pin["file"]), wheel_pin)
                self.assertTrue(wheel_pin["file"].startswith(f"{name}-{entry['version']}-"), wheel_pin)
                self.assertRegex(wheel_pin["sha256"], re.compile("^[0-9a-f]{64}$"))
                self.assertGreater(wheel_pin["size"], 0)

    def test_a_python_without_pins_asks_for_a_newer_apworld(self):
        if sys.platform != "win32":
            self.skipTest("Windows only")
        with self.assertRaisesRegex(client.SetupError, "newest botw.apworld"):
            client._pins({"libraries": {"oead": {"version": "1", "wheels": {"cp30": {}}}}})


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.base = Path(self.folder.name)
        self.fetched: list[str] = []

    def tearDown(self):
        self.folder.cleanup()

    def fetch(self, data: bytes):
        def fetch(url, size, progress):
            self.fetched.append(url)
            progress(len(data))
            return data
        return fetch

    def test_a_wheel_is_unpacked_as_pip_would_once(self):
        data = wheel()
        stale = self.base / "libraries/0123456789abcdef"
        stale.mkdir(parents=True)
        installed = client.install_libraries(self.base, [pinned(data)], fetch=self.fetch(data))
        self.assertTrue((installed / "pkg/__init__.py").is_file())
        self.assertTrue((installed / "runtime.dll").is_file())      # platlib at the root
        self.assertFalse(stale.exists())                            # an older set is removed
        again = client.install_libraries(self.base, [pinned(data)], fetch=self.fetch(data))
        self.assertEqual((again, len(self.fetched)), (installed, 1))

    def test_a_wheel_that_is_not_the_pinned_one_installs_nothing(self):
        data = wheel()
        with self.assertRaisesRegex(client.SetupError, "not the file this version expects"):
            client.install_libraries(self.base, [pinned(data)], fetch=self.fetch(data + b"x"))
        self.assertFalse(client.libraries_folder(self.base, [pinned(data)]).exists())

    def test_an_archive_cannot_write_outside_its_folder(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("../outside.py", "")
        data = stream.getvalue()
        with self.assertRaisesRegex(client.SetupError, "unexpected file"):
            client.install_libraries(self.base, [pinned(data)], fetch=self.fetch(data))
        self.assertFalse((self.base / "libraries/outside.py").exists())

    def test_a_download_failure_says_what_to_check(self):
        def offline(url, size, progress):
            raise OSError("no network")
        data = wheel()
        with self.assertRaisesRegex(client.SetupError, "internet connection"):
            client.install_libraries(self.base, [pinned(data)], fetch=offline)


class ProjectTests(unittest.TestCase):
    def test_the_code_is_unpacked_once_per_version(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            first = client.install_project(base, client_payload({"release.json": b"{}", "a/b.py": b"1"}))
            self.assertTrue((first / "a/b.py").is_file())
            second = client.install_project(base, client_payload({"release.json": b"{}", "a/b.py": b"2"}))
            self.assertNotEqual(first, second)
            self.assertFalse(first.exists())
            self.assertEqual((second / "a/b.py").read_bytes(), b"2")

    def test_the_payload_is_reproducible_and_carried_by_the_apworld(self):
        files = {"release.json": b"{}", "botw_client/x.py": b"pass\n"}
        self.assertEqual(client_payload(files), client_payload(dict(reversed(files.items()))))
        with tempfile.TemporaryDirectory() as folder:
            archive = package(Path(folder) / "botw.apworld", client_payload(files))
            with zipfile.ZipFile(archive) as zipped:
                names = set(zipped.namelist())
        self.assertTrue({f"botw/{PAYLOAD}", "botw/client/__init__.py", "botw/client/wheels.json",
                         "botw/client/icon.png"} <= names)


class InstanceTests(unittest.TestCase):
    def test_one_window_and_later_launches_hand_it_their_file(self):
        with tempfile.TemporaryDirectory() as folder:
            first, later = client.Instance(Path(folder)), client.Instance(Path(folder))
            self.assertTrue(first.claim())
            try:
                self.assertFalse(later.claim())
                later.forward(["C:/seeds/AP_1_P1_Link.apbotw"])
                later.forward([])
                self.assertEqual(first.requests(), [["C:/seeds/AP_1_P1_Link.apbotw"], []])
                self.assertEqual(first.requests(), [])
            finally:
                first._handle.close()


if __name__ == "__main__":
    unittest.main()
