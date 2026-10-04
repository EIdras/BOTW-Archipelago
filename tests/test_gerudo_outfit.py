"""Vilia no longer sells the Gerudo outfit (botw_patch/gerudo_outfit.py), on the game's own flows."""
from pathlib import Path
import unittest

from botw_patch import gerudo_outfit as go

UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
HAVE_UPDATE = all((UPDATE / pack).is_file() for pack in go.PACKS)
OUTFIT = ("Armor_053_Head", "Armor_053_Upper", "Armor_053_Lower")


def vanilla(pack: str, member: str) -> bytes:
    import oead
    from botw_patch.resources import unpack
    return bytes(oead.Sarc(unpack((UPDATE / pack).read_bytes())).get_file(member).data)


def grants_without_paying(raw: bytes) -> set[str]:
    """The outfit's grants reachable from the entries when no CheckRupee says yes."""
    from botw_patch.events import read_flow
    flow = read_flow(raw)

    def name(link):
        try:
            return link.v.name
        except AttributeError:
            return None

    def params(data):
        return {k: (v.v if hasattr(v, "v") else v) for k, v in dict(data.params.data).items()} \
            if getattr(data, "params", None) else {}

    graph, grants = {}, set()
    for event in flow.flowchart.events:
        data, kind = event.data, type(event.data).__name__
        if kind == "SwitchEvent":
            rupees = data.actor_query.v.v == "CheckRupee"
            graph[event.name] = [name(t) for case, t in data.cases.items() if not (rupees and case == 1)]
        elif kind == "ForkEvent":
            graph[event.name] = [name(f) for f in data.forks] + [name(data.join)]
        else:
            graph[event.name] = [name(data.nxt)] if hasattr(data, "nxt") else []
        given = str(params(data).get("PorchItemName", params(data).get("CheckTargetActorName", "")))
        granting = (kind == "ActionEvent" and data.actor_action.v.v == "Demo_IncreasePorchItem"
                    or kind == "SubFlowEvent" and data.res_flowchart_name == "GetDemo")
        if granting and given in OUTFIT:
            grants.add(event.name)
    seen, todo = set(), [name(entry.main_event) for entry in flow.flowchart.entry_points]
    while todo:
        current = todo.pop()
        if current and current not in seen:
            seen.add(current)
            todo.extend(graph.get(current, []))
    return grants & seen


@unittest.skipUnless(HAVE_UPDATE, "Wii U update absent")
class ViliaTests(unittest.TestCase):
    def test_every_sale_of_the_outfit_passes_a_rupee_check(self):
        # What the stage relies on: price the checks out and nothing is given.
        for pack, members in go.STAGES.items():
            for member in members:
                with self.subTest(pack=pack, member=member):
                    self.assertEqual(grants_without_paying(vanilla(pack, member)), set())

    def test_every_price_is_above_any_purse_and_nothing_else_changes(self):
        from botw_patch.events import graph_snapshot, read_flow
        for pack, members in go.STAGES.items():
            for member in members:
                with self.subTest(pack=pack, member=member):
                    raw = vanilla(pack, member)
                    patched, edits = go.transform_for(member)(raw)
                    before, after = graph_snapshot(read_flow(raw)), graph_snapshot(read_flow(patched))
                    changed = {name for name in before["events"]
                               if before["events"][name] != after["events"][name]}
                    self.assertEqual(len(changed), len(go.FLOWS[member][1]))
                    for name in changed:
                        self.assertEqual(after["events"][name]["params"]["Value"], go.UNPAYABLE)
                    self.assertEqual(len(edits), len(changed))

    def test_her_lines_quote_the_price_she_asks_in_every_language(self):
        # 04/10: she refused with 600 rupees in hand while her line said 600.
        import oead
        from botw_patch.resources import unpack
        from botw_patch.shop_items import read_labels
        for language, shown in go.SHOWN_PRICE.items():
            boot = oead.Sarc(unpack((UPDATE / f"Pack/Bootup_{language}.pack").read_bytes()))
            messages = oead.Sarc(unpack(bytes(boot.get_file(
                f"Message/Msg_{language}.product.ssarc").data)))
            for member, prices in go.PRICE_LINES.items():
                with self.subTest(language=language, member=member):
                    raw = bytes(messages.get_file(member).data)
                    patched, detail = go.set_price(raw, prices, shown)
                    before, after = read_labels(raw), read_labels(patched)
                    self.assertEqual(set(before), set(after))
                    self.assertEqual({k for k in before if before[k] != after[k]}, set(prices))
                    for label, price in prices.items():
                        self.assertEqual(after[label], before[label].replace(price, shown, 1))
                        self.assertNotIn(price, after[label].replace(shown, ""))
                    self.assertEqual(len(detail), len(prices))


if __name__ == "__main__":
    unittest.main()
