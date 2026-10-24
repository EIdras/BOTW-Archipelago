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

    def test_what_the_play_profile_runs(self):
        self.cemu.pack("graphics", files={"patch_res.asm": b"[R]\nmoduleMatches = 0x6267BFD0\n0x02000000 = nop\n"})
        self.cemu.pack("mods", files={"content/Pack/Bootup.pack": b"x"})
        self.cemu.pack("fps", files={"patch_speed.asm": b"[S]\nmoduleMatches = 0x6267BFD0\n0x031FA97C = nop\n"})
        self.cemu.pack("exe", files={"code/U-King.rpx": b"rpx"})
        for path in ("graphics", "mods", "fps", "exe"):
            self.cemu.entry(path)
        packs = self.cemu.enabled()
        kept, left = pp.carried(packs, {"files": {"content/Pack/Bootup.pack"},
                                        "patched": frozenset({0x031FA97C})})
        self.assertEqual([pack.path for pack in kept], ["graphics"])
        self.assertEqual(left, {"graphicPacks/exe/rules.txt": "it replaces the game's executable",
                                "graphicPacks/fps/rules.txt": "it patches code the Archipelago pack needs",
                                "graphicPacks/mods/rules.txt":
                                    "it replaces files the Archipelago pack changes (not supported yet)"})
        self.assertIn("The Archipelago game runs 1 of them.", pp.report(packs, None, left))

    def test_mirror_copies_keeps_and_cleans(self):
        source = self.cemu.pack("community/Graphics", files={"content/a.bin": b"1"})
        self.cemu.entry("community/Graphics", presets=[("Resolution", "2K")])
        (pack,) = self.cemu.enabled()
        profile = Path(self.temp.name) / "profile"
        target = profile / "graphicPacks" / pp.MIRROR / "community/Graphics"
        entries = pp.mirror([pack], profile / "graphicPacks")
        self.assertEqual(entries, [{"entry": "graphicPacks/AP_Player/community/Graphics/rules.txt",
                                    "source": "graphicPacks/community/Graphics/rules.txt",
                                    "name": "BOTW/community/Graphics", "priority": pp.DEFAULT_PRIORITY,
                                    "presets": [["Resolution", "2K"]]}])
        self.assertEqual((target / "content/a.bin").read_bytes(), b"1")
        marker = target / "kept"                    # an unchanged source keeps its copy
        marker.write_bytes(b"")
        pp.mirror([pack], profile / "graphicPacks")
        self.assertTrue(marker.exists())
        (source / "content/a.bin").write_bytes(b"22")     # a changed one is copied again
        pp.mirror([pack], profile / "graphicPacks")
        self.assertFalse(marker.exists())
        self.assertEqual((target / "content/a.bin").read_bytes(), b"22")
        stray = profile / "graphicPacks" / pp.MIRROR / "old"
        stray.mkdir()
        (stray / "rules.txt").write_bytes(b"[Definition]")
        pp.mirror([], profile / "graphicPacks")           # a pack turned off loses its copy
        self.assertFalse(target.exists())
        self.assertFalse(stray.exists())

    def test_enable_keeps_the_presets(self):
        portable = Path(self.temp.name) / "portable"
        portable.mkdir()
        (portable / "settings.xml").write_text(
            '<?xml version="1.0"?><content><GraphicPack><Entry filename="graphicPacks/AP_Ledger_x/rules.txt"/>'
            "</GraphicPack></content>", encoding="utf-8")
        pp.enable(portable, [{"entry": "graphicPacks/AP_Player/g/rules.txt", "presets": [["Resolution", "2K"]]}])
        entries = pp.settings_entries(portable / "settings.xml")
        self.assertEqual(list(entries), ["graphicPacks/AP_Ledger_x/rules.txt", "graphicPacks/AP_Player/g/rules.txt"])
        self.assertEqual(entries["graphicPacks/AP_Player/g/rules.txt"], (False, (("Resolution", "2K"),)))


if __name__ == "__main__":
    unittest.main()
