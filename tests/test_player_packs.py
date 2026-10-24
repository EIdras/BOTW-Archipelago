"""The graphic packs of the player's own Cemu (tools/player_packs.py)."""
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tools import player_packs as pp

TITLE = "101c9400"
TITLES = "00050000101C9300,00050000101C9400,00050000101C9500"


class Cemu:
    """A Cemu user folder with graphic packs and their settings.xml entries."""

    def __init__(self, root: Path):
        self.user = root / "Cemu"
        (self.user / "graphicPacks").mkdir(parents=True)
        self.entries = ET.Element("GraphicPack")

    def pack(self, path: str, *, titles: str = TITLES, version: str = "7", extra: str = "",
             files: dict[str, bytes] | None = None) -> Path:
        folder = self.user / "graphicPacks" / path
        folder.mkdir(parents=True)
        (folder / "rules.txt").write_text(
            f'[Definition]\ntitleIds = {titles}\nname = {Path(path).name}\npath = "BOTW/{path}"\n'
            f"version = {version}\n{extra}\n[Default]\n$x = 1\n", encoding="utf-8")
        for name, data in (files or {}).items():
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(data)
        return folder

    def entry(self, path: str, *, disabled: bool = False, presets=()) -> None:
        element = ET.SubElement(self.entries, "Entry", filename=f"graphicPacks/{path}/rules.txt")
        if disabled:
            element.set("disabled", "true")
        for category, preset in presets:
            node = ET.SubElement(element, "Preset")
            ET.SubElement(node, "category").text = category
            ET.SubElement(node, "preset").text = preset

    def enabled(self) -> list[pp.PlayerPack]:
        settings = ET.Element("content")
        settings.append(self.entries)
        ET.ElementTree(settings).write(self.user / "settings.xml")
        return pp.enabled(self.user, TITLE)


class PlayerPacksTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cemu = Cemu(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_enabled_as_cemu_decides(self):
        self.cemu.pack("listed")
        self.cemu.entry("listed")
        self.cemu.pack("unlisted")                                  # not default: off
        self.cemu.pack("by_default", extra="default = true")        # default: on without an entry
        self.cemu.pack("turned_off", extra="default = true")
        self.cemu.entry("turned_off", disabled=True)
        self.cemu.pack("other_game", titles="0005000010101C00")
        self.cemu.entry("other_game")
        self.cemu.pack("outdated", version="2")
        self.cemu.entry("outdated")
        self.assertEqual([pack.folder.name for pack in self.cemu.enabled()], ["by_default", "listed"])

    def test_walk_order_and_nested_packs(self):
        self.cemu.pack("b_pack")
        self.cemu.pack("a_folder/inner")
        self.cemu.pack("a_folder/inner/deeper")     # inside a pack: never loaded
        for path in ("b_pack", "a_folder/inner", "a_folder/inner/deeper"):
            self.cemu.entry(path)
        self.assertEqual([pack.entry for pack in self.cemu.enabled()],
                         ["graphicPacks/a_folder/inner/rules.txt", "graphicPacks/b_pack/rules.txt"])

    def test_priority_presets_and_files(self):
        self.cemu.pack("mods", extra='fsPriority = 9999 # wins\ndescription = "a # in quotes"',
                       files={"content/Pack/Bootup.pack": b"x", "aoc/0010/Map/A.smubin": b"y"})
        self.cemu.entry("mods", presets=[("Resolution", "2K")])
        self.cemu.pack("plain")
        self.cemu.entry("plain")
        mods, plain = self.cemu.enabled()
        self.assertEqual((mods.priority, plain.priority), (9999, pp.DEFAULT_PRIORITY))
        self.assertEqual(mods.presets, (("Resolution", "2K"),))
        self.assertEqual((mods.content, mods.aoc), (("Pack/Bootup.pack",), ("0010/Map/A.smubin",)))
        self.assertEqual(mods.virtual_path, "BOTW/mods")

    def test_patched_addresses_of_our_executable_only(self):
        folder = self.cemu.pack("fps", files={"patch_speed.asm": (
            b"[Speed_V208]\nmoduleMatches = 0x6267BFD0, 0x12345678\n.origin = codecave\n"
            b"_calc:\nblr\n0x031FA97C = bla _calc ; our hook\n0x1031E2C0 = .float 2\n"
            b"[Speed_V150]\nmoduleMatches = 0x0F748D9C\n0x02000000 = nop\n")})
        self.assertEqual(pp.patched_addresses(folder), {0x031FA97C, 0x1031E2C0})

    def test_report_names_what_is_shared(self):
        self.cemu.pack("mods", extra="fsPriority = 9999",
                       files={"content/Pack/Bootup.pack": b"x", "content/Model/Other.sbfres": b"y"})
        self.cemu.pack("fps", files={"patch_speed.asm": b"[S]\nmoduleMatches = 0x6267BFD0\n0x031FA97C = nop\n"})
        for path in ("mods", "fps"):
            self.cemu.entry(path)
        lines = pp.report(self.cemu.enabled(), {"files": {"content/Pack/Bootup.pack"},
                                                "patched": frozenset({0x031FA97C})})
        text = "\n".join(lines)
        self.assertIn("2 graphic pack(s)", text)
        self.assertIn("replaces 1 file(s) the Archipelago pack changes: content/Pack/Bootup.pack", text)
        self.assertIn("patches the same code as the Archipelago pack: 0x031FA97C", text)
        self.assertEqual(pp.report([]), ["Your Cemu runs no graphic pack for Breath of the Wild."])

    def test_missing_settings(self):
        self.cemu.pack("by_default", extra="default = true")
        self.assertEqual([pack.folder.name for pack in pp.enabled(self.cemu.user, TITLE)], ["by_default"])


if __name__ == "__main__":
    unittest.main()
