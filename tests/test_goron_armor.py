"""Goron City's armor shop no longer sells the Flamebreaker set (botw_patch/goron_armor.py), on the game's own flow."""
from pathlib import Path
import unittest

from botw_patch import goron_armor as ga

UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
HAVE_UPDATE = (UPDATE / ga.PACK).is_file()


def vanilla() -> bytes:
    import oead
    from botw_patch.resources import unpack
    return bytes(oead.Sarc(unpack((UPDATE / ga.PACK).read_bytes())).get_file(ga.FLOW).data)


def walk(raw: bytes) -> dict[str, list[tuple]]:
    """Each entry's reachable events, in order: (name, action, message or sub-flow)."""
    from botw_patch.events import read_flow
    flow = read_flow(raw)

    def name(link):
        try:
            return link.v.name
        except AttributeError:
            return None

    events = {event.name: event for event in flow.flowchart.events}
    result = {}
    for entry in flow.flowchart.entry_points:
        seen, todo, order = set(), [name(entry.main_event)], []
        while todo:
            current = todo.pop(0)
            if not current or current in seen:
                continue
            seen.add(current)
            data, kind = events[current].data, type(events[current].data).__name__
            if kind == "SwitchEvent":
                todo += [name(t) for t in data.cases.values()]
                order.append((current, data.actor_query.v.v, None))
            elif kind == "SubFlowEvent":
                todo.append(name(data.nxt))
                order.append((current, "SubFlow", f"{data.res_flowchart_name}<{data.entry_point_name}>"))
            else:
                todo.append(name(data.nxt))
                order.append((current, data.actor_action.v.v, dict(data.params.data).get("MessageId")))
        result[entry.name] = order
    return result


@unittest.skipUnless(HAVE_UPDATE, "Wii U update absent")
class GoronArmorShopTests(unittest.TestCase):
    def test_buying_a_mannequin_gets_the_sold_out_line_and_no_sale(self):
        before, after = walk(vanilla()), walk(ga.transform(vanilla())[0])
        self.assertIn((ga.SALE, "SubFlow", "DisplayShop<Armor>"), before[ga.ENTRY])
        self.assertEqual(after[ga.ENTRY], [
            (ga.GREETING, "SubFlow", "InitTalk<InitTalkSell_ReturnArrivalAnchor>"),
            ("APSoldOut_Keep", "Demo_NoDeleteCurrent", None),
            ("APSoldOut_Talk", "Demo_Talk", "EventFlowMsg/Npc_goron004:talk10"),
            ("APSoldOut_Exit", "Demo_ExitEventPlayer", None),
        ])

    def test_his_talk_is_unchanged(self):
        before, after = walk(vanilla()), walk(ga.transform(vanilla())[0])
        self.assertEqual({k: v for k, v in after.items() if k != ga.ENTRY},
                         {k: v for k, v in before.items() if k != ga.ENTRY})


if __name__ == "__main__":
    unittest.main()
