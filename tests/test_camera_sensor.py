"""The camera's restoration no longer gives the Sheikah Sensor (botw_patch/camera_sensor.py), on the game's own flow."""
from pathlib import Path
import unittest

from botw_patch import camera_sensor as cs

UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
HAVE_UPDATE = (UPDATE / cs.PACK).is_file()


def vanilla() -> bytes:
    import oead
    from botw_patch.resources import unpack
    # The archive must outlive the read: a member's data is a view into it.
    archive = oead.Sarc(unpack((UPDATE / cs.PACK).read_bytes()))
    return bytes(archive.get_file(cs.FLOW).data)


def reachable(raw: bytes) -> dict[str, dict]:
    """The events reachable from the entries, as graph_snapshot nodes."""
    from botw_patch.events import graph_snapshot, read_flow
    graph = graph_snapshot(read_flow(raw))
    nodes = graph["events"]
    todo = [main for _name, main in graph["entry_points"]]
    seen = {}
    while todo:
        name = todo.pop()
        if name is None or name in seen:
            continue
        node = seen[name] = nodes[name]
        todo += [node.get("nxt"), node.get("join"), *node.get("forks", []),
                 *node.get("cases", {}).values()]
    return seen


@unittest.skipUnless(HAVE_UPDATE, "Wii U update absent")
class CameraSensorTests(unittest.TestCase):
    def test_no_reachable_event_gives_the_sensor(self):
        before, after = reachable(vanilla()), reachable(cs.transform(vanilla())[0])
        gives = {"Demo_DownloadShiekSensor"}
        flags = {"IsGet_Obj_SheikSensor", "IsStart_Obj_SheikSensor"}

        def grants(nodes):
            return {name for name, node in nodes.items()
                    if node.get("actor_action") in gives
                    or (node.get("actor_action") == "Demo_FlagON"
                        and node.get("params", {}).get("FlagName") in flags)}
        self.assertEqual(grants(before), {"Event249", "Event304", "Event318", "Event317"})
        self.assertEqual(grants(after), set())

    def test_the_camera_compendium_album_and_purahs_mark_stay(self):
        after = reachable(cs.transform(vanilla())[0])
        actions = {node.get("actor_action") for node in after.values()}
        self.assertTrue({"Demo_DownloadPictureBook", "Demo_DownloadAlbum"} <= actions)
        self.assertEqual(after[cs.MARK]["params"]["FlagName"], cs.MARK_FLAG)
        self.assertEqual(after[cs.DOWNLOAD[0]]["cases"], {1: "Event321", 0: cs.MARK})
        self.assertEqual(after[cs.LIST[0]]["cases"], {1: "Event254", 0: "Event254"})


if __name__ == "__main__":
    unittest.main()
