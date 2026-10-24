"""The player's mods in the Archipelago game (tools/play_mods.py)."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from botw_patch.game_files import ModConflict
from tools import play_mods, player_packs
from tools.build_pack_from_source import PRIORITY, rules
from tools.play_pack import outdated


def pack(entry: str, priority: int = 100) -> player_packs.PlayerPack:
    return player_packs.PlayerPack(folder=Path("x"), entry=f"graphicPacks/{entry}/rules.txt", name=entry,
                                   virtual_path=f"BOTW/{entry}", priority=priority, default=True, presets=(),
                                   content=("Pack/TitleBG.pack",), aoc=(), patches=(), code=False,
                                   patched=frozenset())


class FreshPackTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.portable = Path(temp.name) / "portable"
        patcher = mock.patch.object(play_mods.cemu_profile, "PORTABLE", self.portable)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ukmm, self.other = pack("BreathOfTheWild_UKMM", 9999), pack("Other")
        self.mods = play_mods.Mods([self.ukmm, self.other], {})
        self.copied = []

        def mirror(kept, graphic_packs):
            self.copied.append([p.entry for p in kept])
            return [{"entry": f"graphicPacks/AP_Player/{p.path}/rules.txt", "source": p.entry,
                     "priority": p.priority, "fingerprint": p.path, "game_files": True} for p in kept]
        patcher = mock.patch.object(play_mods.player_packs, "mirror", side_effect=mirror)
        patcher.start()
        self.addCleanup(patcher.stop)
        play_mods._copy(self.mods)

    def test_a_pack_built_over_the_same_mods_is_kept(self):
        with mock.patch("tools.play_pack.selected_pack", return_value=Path("pack")), \
                mock.patch("tools.play_pack.outdated", return_value=[]) as stale, \
                mock.patch("tools.play_seed.refresh") as refresh:
            self.assertEqual(play_mods.fresh_pack(Path("seed"), self.mods, say=lambda text: None), Path("pack"))
        stale.assert_called_once_with(Path("pack"), self.mods.layers, 0x50000000)
        refresh.assert_not_called()
        self.assertEqual([layer["pack"] for layer in self.mods.layers],
                         ["AP_Player/BreathOfTheWild_UKMM", "AP_Player/Other"])

    def test_a_conflicting_mod_is_left_out_by_name_and_the_pack_built_again(self):
        conflict = ModConflict("conflict", self.portable / "graphicPacks/AP_Player/BreathOfTheWild_UKMM",
                               "EventFlow/Demo007_1.bfevfl")
        said = []
        with mock.patch("tools.play_pack.selected_pack", side_effect=RuntimeError("no pack")), \
                mock.patch("tools.play_seed.refresh", side_effect=[conflict, Path("pack")]) as refresh:
            self.assertEqual(play_mods.fresh_pack(Path("seed"), self.mods, say=said.append), Path("pack"))
        self.assertEqual(refresh.call_args_list[-1], mock.call(Path("seed"), self.mods.layers, 0x50000000))
        self.assertEqual([layer["pack"] for layer in self.mods.layers], ["AP_Player/Other"])
        self.assertEqual(self.copied[-1], [self.other.entry])
        self.assertIn("EventFlow/Demo007_1.bfevfl", self.mods.left[self.ukmm.entry])
        self.assertIn("It holds every mod UKMM manages.", said[-1])

    def test_a_conflict_no_copy_explains_is_raised(self):
        with mock.patch("tools.play_pack.selected_pack", side_effect=RuntimeError("no pack")), \
                mock.patch("tools.play_seed.refresh", side_effect=ModConflict("elsewhere", Path("nowhere"))):
            with self.assertRaisesRegex(ModConflict, "elsewhere"):
                play_mods.fresh_pack(Path("seed"), self.mods, say=lambda text: None)


def any_pack(name, *, order, enabled=True, content=(), ram=(), patched=frozenset()):
    return player_packs.PlayerPack(folder=Path(name), entry=f"graphicPacks/{name}/rules.txt", name=name,
                                   virtual_path=f"BOTW/{name}", priority=100, default=False, presets=(),
                                   content=content, aoc=(), patches=(), code=False, patched=patched,
                                   ram=ram, enabled=enabled, order=order)


class MemoryTest(unittest.TestCase):
    """With mods holding game files, the Archipelago game runs Extended Memory."""

    def prepare(self, *installed):
        said = []
        with mock.patch.object(play_mods.cemu_profile, "check_isolated"), \
                mock.patch.object(play_mods.cemu_profile, "source_user_data"), \
                mock.patch.object(play_mods.cemu_profile, "region"), \
                mock.patch.object(play_mods.player_packs, "installed", return_value=list(installed)), \
                mock.patch.object(play_mods.player_packs, "our_addresses", return_value=frozenset({0x031FA97C})), \
                mock.patch.object(play_mods, "_copy"):
            return play_mods.prepare(say=said.append), said

    def setUp(self):
        self.linkle = any_pack("BreathOfTheWild_UKMM", order=0, content=("Pack/TitleBG.pack",))
        self.graphics = any_pack("Graphics", order=3)
        self.memory = any_pack("ExtendedMemory", order=2, enabled=False,
                               ram=((0x10000000, 0xA0000000), (0xA0000000, 0xE0000000)))

    def test_mods_get_the_memory_they_need(self):
        mods, said = self.prepare(self.linkle, self.memory, self.graphics)
        self.assertEqual([pack.name for pack in mods.added], ["ExtendedMemory"])
        self.assertEqual([pack.name for pack in mods.kept], ["BreathOfTheWild_UKMM", "ExtendedMemory", "Graphics"])
        self.assertEqual(mods.mem2_end, 0xA0000000)
        self.assertEqual(said, [play_mods.MEMORY_ADDED.format(name="BOTW/ExtendedMemory")])

    def test_without_extended_memory_installed_the_player_is_told_how(self):
        mods, said = self.prepare(self.linkle, self.graphics)
        self.assertEqual((mods.added, mods.mem2_end, said), ([], 0x50000000, [play_mods.MEMORY_MISSING]))

    def test_nothing_changes_without_game_files_nor_when_it_runs(self):
        mods, said = self.prepare(self.memory, self.graphics)
        self.assertEqual((mods.added, mods.mem2_end, said), ([], 0x50000000, []))
        running = any_pack("ExtendedMemory", order=2, ram=self.memory.ram)
        mods, said = self.prepare(self.linkle, running)
        self.assertEqual((mods.added, mods.mem2_end, said), ([], 0xA0000000, []))

    def test_a_memory_pack_patching_our_code_is_not_added(self):
        clash = any_pack("ExtendedMemory", order=2, enabled=False, ram=self.memory.ram,
                         patched=frozenset({0x031FA97C}))
        mods, said = self.prepare(self.linkle, clash)
        self.assertEqual((mods.added, said), ([], [play_mods.MEMORY_MISSING]))


class IdentityTest(unittest.TestCase):
    def test_a_pack_records_the_mods_it_is_built_on(self):
        layer = {"pack": "AP_Player/BreathOfTheWild_UKMM", "priority": 9999, "fingerprint": "f"}
        with tempfile.TemporaryDirectory() as folder:
            pack_dir = Path(folder)
            (pack_dir / "manifest.json").write_text('{"revision": "USA v208", "source_hashes": {}, '
                                                    '"game_packs": [' + str(layer).replace("'", '"') + "]}")
            with mock.patch("tools.cemu_profile.region", return_value=mock.Mock(key="USA")):
                self.assertEqual(outdated(pack_dir, [{**layer, "folder": Path("x")}]), [])
                self.assertEqual(outdated(pack_dir, [{**layer, "fingerprint": "g"}]), ["the mods it is built on"])
                self.assertEqual(outdated(pack_dir, []), ["the mods it is built on"])
                self.assertEqual(outdated(pack_dir), [])        # mods not asked about
                self.assertEqual(outdated(pack_dir, mem2_end=0x50000000), [])
                self.assertEqual(outdated(pack_dir, mem2_end=0xA0000000), ["the game's memory"])

    def test_its_priority_is_above_theirs(self):
        self.assertIn(f"fsPriority = {PRIORITY}\n".encode(), rules())
        self.assertIn(b"fsPriority = 10000\n", rules(priority=10000))


if __name__ == "__main__":
    unittest.main()
