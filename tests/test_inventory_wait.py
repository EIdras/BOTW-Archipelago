import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from tools.cemu import menu_diagnostic as menu


class InventoryWaitTests(unittest.TestCase):
    def test_map_blocks_and_observed_post_map_variant_releases(self):
        catalog = self.catalog()
        catalog["screens"][44] = dict(index=44, pointer=0x42000000, activity=1, state_94=0x01000200)
        self.assertFalse(menu.menu_state(catalog, "map")["idle"])
        catalog["screens"][44].update(activity=255, state_94=0x01000000)
        for i in (46, 68):
            catalog["screens"][i]["state_94"] = 0x01fc0000
        self.assertTrue(menu.menu_state(catalog, "map")["idle"])

    def catalog(self, opened=False):
        rows = [{} for _ in range(99)]
        for i in (46, 68):
            rows[i] = dict(index=i, pointer=0x40000000 + i * 1024,
                           activity=1 if opened else 255, state_94=0x01000200 if opened else 0x01000000)
        rows[47] = dict(index=47, pointer=0x41000000 if opened else 0,
                        activity=1 if opened else 255, state_94=0x01000200 if opened else None)
        return dict(screens=rows)

    def test_unknown_transition_does_not_release(self):
        state = self.catalog()
        state["screens"][46]["state_94"] = 0x01000100
        self.assertFalse(menu.inventory_state(state)["idle"])

    def test_waiter_reads_only_and_requires_stable_close(self):
        process = Mock()
        with tempfile.TemporaryDirectory() as folder, patch.object(menu, "screens", side_effect=[
                self.catalog(True), self.catalog(), self.catalog(), self.catalog()]), \
                patch.object(menu.time, "sleep"):
            result = menu.wait_for_inventory(process, 0, Path(folder) / "trace.json")
        self.assertEqual(result["status"], "released")
        process.write.assert_not_called()

    def test_already_closed_does_not_pretend_to_test_deferral(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(menu, "screens", return_value=self.catalog()):
            with self.assertRaisesRegex(RuntimeError, "deja ferme"):
                menu.wait_for_inventory(Mock(), 0, Path(folder) / "trace.json")
