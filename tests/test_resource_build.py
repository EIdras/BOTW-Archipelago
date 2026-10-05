"""Resource integration tests; optional local vanilla dump, never redistributed."""
import json
import os
from pathlib import Path
import tempfile
import unittest

import oead
import rstb
from botw_patch.build import build, RECIPES
from botw_patch.events import graph_snapshot, read_flow, suppress_reward
from botw_patch.resources import ResourceBuilder, digest, unpack

CONTENT = Path(os.environ.get("BOTW_TEST_CONTENT", str(Path.home() /
    "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content")))


@unittest.skipUnless((CONTENT / "Event/Demo003_0.sbeventpack").is_file(),
                     "set BOTW_TEST_CONTENT to the vanilla Wii U v208 update")
class ResourceBuildTests(unittest.TestCase):
    def member(self, path, name):
        # SARC file views borrow the archive's storage. Keep its owner alive.
        archive = oead.Sarc(unpack(path.read_bytes()))
        return bytes(archive.get_file(name).data)

    def test_only_declared_events_change_and_all_edges_survive(self):
        for name, transform in RECIPES.items():
            raw = self.member(CONTENT / f"Event/{name}.sbeventpack", f"EventFlow/{name}.bfevfl")
            before = graph_snapshot(read_flow(raw))
            patched, changed = transform(raw)
            after = graph_snapshot(read_flow(patched))
            self.assertEqual(before["entry_points"], after["entry_points"])
            self.assertEqual(set(before["events"]), set(after["events"]))
            self.assertTrue(changed)
            for event_name, event in before["events"].items():
                if event_name not in changed:
                    self.assertEqual(event, after["events"][event_name], (name, event_name))
                elif event["type"] == "SwitchEvent":
                    # An NPC's gift (suppress_gift): its pouch test always finds room.
                    replacement = after["events"][event_name]
                    self.assertEqual(replacement["actor_query"], "CheckAddPorchItem")
                    self.assertEqual(replacement["cases"], {0: event["cases"][1], 1: event["cases"][1]})
                else:
                    replacement = after["events"][event_name]
                    self.assertEqual(event["nxt"], replacement["nxt"])
                    self.assertEqual(replacement["actor_action"], "Demo_WaitFrame")
                    self.assertEqual(replacement["params"], {"Frame": 1, "IsWaitFinish": True})

    def test_terminal_patch_removes_all_four_rune_ownership_setters(self):
        raw = self.member(
            CONTENT / "Event/Demo003_0.sbeventpack",
            "EventFlow/Demo003_0.bfevfl")
        before = graph_snapshot(read_flow(raw))["events"]
        patched, changed = RECIPES["Demo003_0"](raw)
        after = graph_snapshot(read_flow(patched))["events"]
        rune_setters = {
            name for name, node in before.items()
            if node.get("actor_action") == "Demo_FlagON"
            and node.get("params", {}).get("FlagName") in {
                "IsGet_Obj_Magnetglove", "IsGet_Obj_RemoteBomb",
                "IsGet_Obj_StopTimer", "IsGet_Obj_IceMaker"}
        }
        self.assertEqual(len(rune_setters), 4)
        self.assertTrue(rune_setters.issubset(changed))
        for name in rune_setters:
            self.assertEqual(after[name]["actor_action"], "Demo_WaitFrame")
            self.assertEqual(after[name]["nxt"], before[name]["nxt"])
        self.assertEqual(after["Event219"], before["Event219"])

    def test_build_is_reproducible_and_does_not_modify_source_or_unrelated_members(self):
        originals = {name: (CONTENT / f"Event/{name}.sbeventpack").read_bytes() for name in RECIPES}
        with tempfile.TemporaryDirectory() as temp:
            first = build(CONTENT, Path(temp) / "first")
            second = build(CONTENT, Path(temp) / "second")
            manifest = json.loads((first / "manifest.json").read_text())
            self.assertEqual(first.name, second.name)
            for name, expected in manifest["files"].items():
                data = (first / "content" / name).read_bytes()
                self.assertEqual(digest(data), expected)
                self.assertEqual(data, (second / "content" / name).read_bytes())
            for name, original in originals.items():
                self.assertEqual(original, (CONTENT / f"Event/{name}.sbeventpack").read_bytes())
                before = oead.Sarc(unpack(original))
                after = oead.Sarc(unpack((first / f"content/Event/{name}.sbeventpack").read_bytes()))
                for member in before.get_files():
                    if member.name != f"EventFlow/{name}.bfevfl":
                        self.assertEqual(bytes(member.data), bytes(after.get_file(member.name).data))
            old = ResourceBuilder(CONTENT).table
            new = rstb.ResourceSizeTable(unpack((first / "content/System/Resource/ResourceSizeTable.product.srsizetable").read_bytes()), True)
            for key, value in old.crc32_map.items():
                self.assertGreaterEqual(new.crc32_map[key], value)

    def test_incompatible_source_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            table = root / "source/System/Resource/ResourceSizeTable.product.srsizetable"
            table.parent.mkdir(parents=True)
            table.write_bytes((CONTENT / "System/Resource/ResourceSizeTable.product.srsizetable").read_bytes())
            for name in RECIPES:
                target = root / f"source/Event/{name}.sbeventpack"
                target.parent.mkdir(parents=True, exist_ok=True)
                data = (CONTENT / f"Event/{name}.sbeventpack").read_bytes()
                if name == "ClearRemains":
                    sarc = oead.Sarc(unpack(data))
                    writer = oead.SarcWriter.from_sarc(sarc)
                    writer.files[f"EventFlow/{name}.bfevfl"] = b"wrong revision"
                    data = bytes(oead.yaz0.compress(writer.write()[1]))
                target.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "unsupported"):
                build(root / "source", root / "output")
            self.assertFalse((root / "output").exists())

    def test_mismatched_recipe_and_path_escape_are_rejected(self):
        raw = self.member(CONTENT / "Event/FindDungeon.sbeventpack", "EventFlow/FindDungeon.bfevfl")
        with self.assertRaisesRegex(ValueError, "expected 1"):
            suppress_reward(raw, "ActorThatDoesNotExist")
        with self.assertRaisesRegex(ValueError, "escapes"):
            ResourceBuilder(CONTENT).read("../outside.pack")
        with self.assertRaisesRegex(ValueError, "platform mismatch"):
            # The RSTB parser itself may reject mismatched endian first.
            b = ResourceBuilder(CONTENT)
            b.big_endian = False
            b.patch_archive("Event/FindDungeon.sbeventpack", {})
