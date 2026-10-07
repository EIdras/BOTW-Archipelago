import unittest

from botw_client.backend import DeliveryCommand
from botw_client.delivery_plan import (
    MutationKind, compile_all_delivery_plans, compile_delivery_plan)
from botw_client.items import load_item_map


class DeliveryPlanTests(unittest.TestCase):
    def test_every_mapped_item_compiles(self):
        mapping = load_item_map()
        plans = compile_all_delivery_plans(mapping)
        self.assertEqual(set(plans), set(mapping))
        self.assertTrue(all(plan.steps for plan in plans.values()))

    def test_three_piece_set_commits_one_capacity_checked_piece_per_step(self):
        plan = compile_delivery_plan("Snowquill Set")
        self.assertEqual(len(plan.steps), 3)
        self.assertEqual([step.capacity_actor for step in plan.steps], [
            "Armor_009_Head", "Armor_009_Upper", "Armor_009_Lower"])
        # Each piece through the game's own get window.
        self.assertTrue(all(step.mutations[0].kind is
                            MutationKind.GET_DEMO_ACTOR for step in plan.steps))

    def test_horse_tack_is_not_a_pouch_item_and_stays_silent(self):
        plan = compile_delivery_plan("Ancient Bridle")
        self.assertIs(plan.steps[0].mutations[0].kind, MutationKind.GRANT_ACTOR)

    def test_progressive_actor_depends_on_prior_received_count(self):
        expected = ["Armor_014_Upper", "Armor_014_Head", "Armor_014_Lower",
                    "Armor_014_Lower"]
        actual = [compile_delivery_plan(
            "Progressive Climbing Gear", count).steps[0].capacity_actor
                  for count in range(4)]
        self.assertEqual(actual, expected)

    def test_related_flags_share_one_idempotent_step(self):
        plan = compile_delivery_plan("Sheikah Sensor")
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(len(plan.steps[0].mutations), 3)
        self.assertIsNone(plan.steps[0].capacity_actor)
        self.assertTrue(all(mutation.kind is MutationKind.SET_BOOL
                            for mutation in plan.steps[0].mutations))

    def test_rune_unlock_and_selection_share_one_guarded_step(self):
        plan = compile_delivery_plan("Stasis")
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual([
            (mutation.kind, mutation.target, mutation.value)
            for mutation in plan.steps[0].mutations], [
                # The terminal's presentation sets the flag (Demo003_0 Item03).
                (MutationKind.RUNE_DOWNLOAD, "IsGet_Obj_StopTimer", 2),
                (MutationKind.SET_S32, "PlayerEquipItemType", 3),
            ])

    def test_the_master_cycle_downloads_as_a_rune_without_taking_the_hand(self):
        # Demo645_0 (Event63, Event73): the download screen, type 5, then its flag;
        # the rune the player holds stays selected.
        (step,) = compile_delivery_plan("Master Cycle Zero").steps
        self.assertEqual([(m.kind, m.target, m.value) for m in step.mutations],
                         [(MutationKind.RUNE_DOWNLOAD, "IsGet_Obj_Motorcycle", 5)])

    def test_heart_uses_vanilla_getdemo_actor(self):
        mutation = compile_delivery_plan(
            "Heart Container").steps[0].mutations[0]
        self.assertEqual((mutation.kind, mutation.target, mutation.value),
                         (MutationKind.GET_DEMO_ACTOR,
                          "Obj_HeartUtuwa_A_01", 1))

    def test_a_trap_calls_its_entry_and_carries_its_text(self):
        plan = compile_delivery_plan("Weapon Shatter")
        self.assertTrue(plan.automatic)
        (step,) = plan.steps
        (mutation,) = step.mutations
        self.assertEqual((mutation.kind, mutation.target, mutation.value),
                         (MutationKind.TRAP, "APTrapWeaponShatter", "Your weapon shatters!"))
        self.assertIsNone(step.capacity_actor)

    def test_a_manual_prompt_is_never_automatic(self):
        mapping = {"Prompt": {"delivery": {"kind": "manual_prompt", "text": "Do it."}}}
        plan = compile_delivery_plan("Prompt", mapping=mapping)
        self.assertFalse(plan.automatic)
        self.assertIs(plan.steps[0].mutations[0].kind, MutationKind.MANUAL)

    def test_packed_cursor_advances_substeps_then_next_item(self):
        first = DeliveryCommand("seed", 1, 7, "Snowquill Set", 0, 3)
        middle = DeliveryCommand("seed", 1, 7, "Snowquill Set", 1, 3)
        final = DeliveryCommand("seed", 1, 7, "Snowquill Set", 2, 3)
        self.assertEqual((first.cursor, first.next_cursor),
                         ((7 << 8), (7 << 8) | 1))
        self.assertEqual((middle.cursor, middle.next_cursor),
                         ((7 << 8) | 1, (7 << 8) | 2))
        self.assertEqual((final.cursor, final.next_cursor),
                         ((7 << 8) | 2, 8 << 8))


if __name__ == "__main__":
    unittest.main()
