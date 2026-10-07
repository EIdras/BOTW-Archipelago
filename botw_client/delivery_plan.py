"""Compile AP item definitions into resumable native delivery steps."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .items import load_item_map, progressive_index


class MutationKind(str, Enum):
    GRANT_ACTOR = "grant_actor"
    GET_DEMO_ACTOR = "get_demo_actor"
    # Demo_IncreaseRupee, as quest rewards give rupees without a window
    # (Npc_Goron018, Demo035_0): the silent twin of a rupee bundle.
    INCREASE_RUPEE = "increase_rupee"
    # Demo_IncreasePlayerMaxHeart / _Stamina (the action, as target), as the
    # Horned Statue trades vessels (Demo035_0): the silent twin of a vessel.
    INCREASE_MAX = "increase_max"
    CHAMPION_ACTOR = "champion_actor"
    # The rune terminal's own presentation (Demo003_0 Item01..04): the Sheikah
    # Slate download screen, "the module is activated" in the Slate's voice,
    # the menu closed, then the rune's flag. Its silent twin sets the flag.
    RUNE_DOWNLOAD = "rune_download"
    # A trap: the entry of botw_patch/traps.py called as a sub-flow, its text
    # (what the journal says once it has happened) as the value. Its silent twin,
    # for a trap given back after a reload, spends it without effect.
    TRAP = "trap"
    TRAP_SPENT = "trap_spent"
    # A trap the client plays itself once the delivery is committed (the
    # game has no action for it): its effect's name, its text as the value.
    NATIVE_TRAP = "native_trap"
    # The pouch was full: the client created the item at Link's feet
    # (botw_client/item_drop.py); the entry only commits.
    DROPPED = "dropped"
    # A bundle of arrows by the game's get window with IsInvalidOpenPouch on,
    # as Riju gives her bomb arrows (Electric_Relic): off, the window says
    # "0 arrows" and gives none (measured). Its silent twin: INCREASE_PORCH.
    GET_DEMO_BUNDLE = "get_demo_bundle"
    # Demo_IncreasePorchItem, Value 1: one bundle, all its arrows (measured).
    INCREASE_PORCH = "increase_porch"
    # A dish cooked by the game from its ingredients (the value), as the
    # Champions' Ballad gives its elixirs (Demo_SetCookItem), then the cooking's
    # own get window (GetDemo<ShowGetDemoCookResult>); its silent twin cooks only.
    COOK = "cook"
    # One of Hestu's pouch upgrades (Npc_OldKorok): his next upgrade flag
    # (target: the pouch, POUCHES), one more slot, then his pouch screen
    # (Demo_OpenPouchAddStockNum); its silent twin, without the screen.
    POUCH_SLOT = "pouch_slot"
    SET_BOOL = "set_bool"
    SET_S32 = "set_s32"
    INCREMENT = "increment"
    AT_LEAST = "at_least"
    MANUAL = "manual"


@dataclass(frozen=True)
class DeliveryMutation:
    kind: MutationKind
    target: str
    value: object = None
    maximum: object = None
    value_type: str | None = None


@dataclass(frozen=True)
class DeliveryStep:
    mutations: tuple[DeliveryMutation, ...]
    capacity_actor: str | None = None
    # The flowchart the step's entry must live in, when its kind does not
    # decide it (a trap that calls a cutscene: botw_patch/delivery_flow.host_of).
    host: str | None = None


@dataclass(frozen=True)
class ItemDeliveryPlan:
    item_name: str
    steps: tuple[DeliveryStep, ...]
    automatic: bool = True


# Pouch items are delivered as the game hands them over: its own get window
# (GetDemo<GetItemByName>), one per piece; the AP journal names the sender
# just before. Horse tack is not a pouch item: granted silently, its AP
# window stays.
SILENT_ACTOR_PREFIXES = ("GameRomHorse",)


# The items that fall at Link's feet when the pouch is full: the kinds
# measured on the ground (botw_client/item_drop.py). The others wait for room.
DROPPABLE_PREFIXES = ("Weapon_Lsword_", "Weapon_Bow_", "Weapon_Shield_", "Obj_ArrowBundle_", "Item_Ore_")


# What a cooked dish is to the pouch: the game's elixir (its effect comes from
# the cooking, Demo_SetCookItem; given by its name, it is an empty "Elixir").
COOKED = "Item_Cook_C_17"
# Ingredients of a dish: Demo_SetCookItem takes up to five.
COOK_SLOTS = 5


@dataclass(frozen=True)
class Pouch:
    counter: str            # its slots, an s32 of the save
    screen: int             # Demo_OpenPouchAddStockNum's Type (Hestu's: 0, 1, 2)
    category: int           # HasPouchItemByPouchCategory's (0, 1, 3: 2 is the arrows)
    flags: tuple[str, ...]  # Hestu's upgrades, in the order his flow checks them


# Hestu's upgrades (Npc_OldKorok): an AP upgrade is one of his, so he offers one
# fewer and the pouch never passes the game's maximum (20, 13 of 14, 20).
POUCHES = {
    "weapon": Pouch("WeaponPorchStockNum", 0, 0, tuple(f"Npc_OldKorok_Weapon{n:02d}" for n in range(1, 12))),
    "bow": Pouch("BowPorchStockNum", 1, 1, tuple(f"Npc_OldKorok_Bow{n:02d}" for n in range(1, 9))),
    "shield": Pouch("ShieldPorchStockNum", 2, 3, tuple(f"Npc_OldKorok_Shield{n:02d}" for n in range(1, 17))),
}


def droppable(actor: str | None) -> bool:
    return bool(actor) and actor.startswith(DROPPABLE_PREFIXES)


def pouch_kind(actor: str) -> MutationKind:
    return (MutationKind.GRANT_ACTOR if actor.startswith(SILENT_ACTOR_PREFIXES)
            else MutationKind.GET_DEMO_ACTOR)


def compile_delivery_plan(item_name: str, received_before: int = 0,
                          mapping=None) -> ItemDeliveryPlan:
    mapping = load_item_map() if mapping is None else mapping
    entry = mapping.get(item_name)
    if entry is None:
        raise KeyError(f"AP item missing from the item map: {item_name}")
    delivery = entry["delivery"]
    kind = delivery["kind"]

    if kind == "actors":
        # Each actor gets its own committed sub-step. This lets a three-piece
        # set resume at piece 2 without granting piece 1 again, and lets every
        # component run its own capacity preflight.
        return ItemDeliveryPlan(item_name, tuple(
            DeliveryStep((DeliveryMutation(pouch_kind(actor), actor, 1),), actor)
            for actor in delivery["actors"]))
    if kind == "arrows":
        return ItemDeliveryPlan(item_name, (DeliveryStep((DeliveryMutation(
            MutationKind.GET_DEMO_BUNDLE, delivery["actor"], 1),)),))
    if kind == "cook":
        return ItemDeliveryPlan(item_name, (DeliveryStep((DeliveryMutation(
            MutationKind.COOK, COOKED, tuple(delivery["ingredients"])),)),))
    if kind == "pouch_slot":
        return ItemDeliveryPlan(item_name, (DeliveryStep((DeliveryMutation(
            MutationKind.POUCH_SLOT, delivery["pouch"], 1),)),))
    if kind == "getdemo_actor":
        return ItemDeliveryPlan(item_name, (
            DeliveryStep((DeliveryMutation(
                MutationKind.GET_DEMO_ACTOR, delivery["actor"], 1),)),))
    if kind == "champion_actor":
        # Pouch, equipment creation and actor ownership belong to one native
        # transaction. The AP dialog has already finished; omit GetDemo's dialog.
        return ItemDeliveryPlan(item_name, (DeliveryStep((DeliveryMutation(
            MutationKind.CHAMPION_ACTOR, delivery["actor"], 1),)),))
    if kind == "progressive_actors":
        actors = delivery["actors"]
        actor = actors[progressive_index(
            item_name, received_before, len(actors))]
        return ItemDeliveryPlan(item_name, (
            DeliveryStep((DeliveryMutation(pouch_kind(actor), actor, 1),), actor),))
    if kind == "flags":
        # Boolean setters are idempotent and have no pouch capacity. Keep the
        # related flags in one guarded commit so the AP item advances once.
        mutations = tuple(DeliveryMutation(
            MutationKind.SET_BOOL, flag, bool(value), value_type="bool")
            for flag, value in delivery["writes"])
        return ItemDeliveryPlan(item_name, (DeliveryStep(mutations),))
    if kind == "rune":
        # Vanilla rune downloads both unlock and select the new app. Keeping
        # PlayerEquipItemType in the same guarded step makes the first received
        # rune usable without forcing the player through the inventory menu.
        # The flag is set by the terminal's presentation (RUNE_DOWNLOAD).
        return ItemDeliveryPlan(item_name, (DeliveryStep((
            DeliveryMutation(
                MutationKind.RUNE_DOWNLOAD, delivery["flag"],
                int(delivery["download_type"])),
            DeliveryMutation(
                MutationKind.SET_S32, "PlayerEquipItemType",
                int(delivery["equip_type"]), value_type="s32"),
        )),))
    if kind == "counter":
        mutation = DeliveryMutation(
            MutationKind.INCREMENT, delivery["flag"], delivery["delta"],
            delivery["maximum"], delivery["type"])
        return ItemDeliveryPlan(item_name, (DeliveryStep((mutation,)),))
    if kind == "counter_at_least":
        mutation = DeliveryMutation(
            MutationKind.AT_LEAST, delivery["flag"], delivery["value"],
            value_type=delivery["type"])
        return ItemDeliveryPlan(item_name, (DeliveryStep((mutation,)),))
    if kind == "trap":
        mutation = DeliveryMutation(MutationKind.TRAP, delivery["entry"], delivery["text"])
        return ItemDeliveryPlan(item_name, (DeliveryStep((mutation,), host=delivery.get("host")),))
    if kind == "native_trap":
        mutation = DeliveryMutation(MutationKind.NATIVE_TRAP, delivery["effect"], delivery["text"])
        return ItemDeliveryPlan(item_name, (DeliveryStep((mutation,)),))
    if kind == "manual_prompt":
        mutation = DeliveryMutation(
            MutationKind.MANUAL, item_name, delivery["text"])
        return ItemDeliveryPlan(
            item_name, (DeliveryStep((mutation,)),), automatic=False)
    raise ValueError(f"unknown delivery kind: {item_name}/{kind}")


def compile_all_delivery_plans(mapping=None) -> dict[str, ItemDeliveryPlan]:
    mapping = load_item_map() if mapping is None else mapping
    return {name: compile_delivery_plan(name, mapping=mapping)
            for name in mapping}
