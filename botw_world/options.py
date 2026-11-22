"""Player options of the Breath of the Wild world."""
from dataclasses import dataclass

from Options import (Choice, DeathLink, OptionCounter, OptionGroup, PerGameCommonOptions, Range,
                     StartInventoryPool, Toggle)

from .catalog import TRAPS


class Goal(Choice):
    """What finishes your game.
    ganon: defeat Calamity Ganon, in Hyrule Castle's sanctum (see the Sanctum options).
    divine_beasts: free the four Divine Beasts.
    shrines: clear the number of shrines of Goal Shrines."""
    display_name = "Goal"
    option_ganon = 0
    option_divine_beasts = 1
    option_shrines = 2
    default = 0


class GoalShrines(Range):
    """The shrines to clear, with the shrines goal."""
    display_name = "Goal Shrines"
    range_start = 1
    range_end = 120
    default = 60


class SanctumDivineBeasts(Range):
    """Hyrule Castle's sanctum, where Ganon waits, stays sealed until this many
    Divine Beasts are freed (entering it sends Link back; the Archipelago journal
    says what is missing). 0: not asked."""
    display_name = "Sanctum: Divine Beasts"
    range_start = 0
    range_end = 4
    default = 2


class SanctumShrines(Range):
    """The sanctum stays sealed until this many shrines are cleared. 0: not asked."""
    display_name = "Sanctum: Shrines"
    range_start = 0
    range_end = 120
    default = 0


class SanctumMasterSword(Toggle):
    """The sanctum stays sealed until the Master Sword is received."""
    display_name = "Sanctum: Master Sword"
    default = 1


class SanctumRunes(Toggle):
    """The sanctum stays sealed until the four runes (Magnesis, Remote Bomb, Stasis,
    Cryonis) are received."""
    display_name = "Sanctum: Runes"
    default = 1


class BeedleShopItems(Range):
    """Items of Beedle's stock that become Archipelago locations, at each of his
    16 shops (the 15 stables and Kara Kara Bazaar). They are listed first,
    priced by the seed; seeing them in his list hints them. 0: no shop."""
    display_name = "Beedle Shop Items"
    range_start = 0
    range_end = 2
    default = 0


class StallItems(Range):
    """Items on the 3D stalls of the villages (Kakariko, Hateno, Rito, Goron,
    Zora's Domain, Gerudo Town, Kara Kara, Korok Forest, Lurelin, Tarrey Town)
    that become Archipelago locations, spread at random over their 14 stalls,
    2 at most on one stall: some stalls have none, others one or two. The
    Archipelago medallion replaces one copy of an item the stall sells in
    several, priced by the seed; once bought it never comes back. 0: none."""
    display_name = "Stall Items"
    range_start = 0
    range_end = 28
    default = 0


class WeaponOrder(Choice):
    """How the weapons of the filler are spread over the game, wherever they land
    in the multiworld (the jokes, a Soup Ladle or a Pot Lid, always come anywhere).
    smoothed: the weaker first, the stronger as the game goes on, the amiibo's
    treasures last.
    loosely_smoothed: the same order, with some chance: a weapon may come a level
    earlier or later, never a treasure among the first.
    anywhere: wherever the fill put them, a treasure on the Great Plateau too."""
    display_name = "Weapon Order"
    option_anywhere = 0
    option_loosely_smoothed = 1
    option_smoothed = 2
    default = 2


class TowerMaps(Choice):
    """The map of each region, revealed in the game by its tower.
    vanilla: as in the game, a tower reveals its region's map.
    items: the 14 maps (all but the Great Plateau's) are items: a map received
    reveals its region with the game's own animation, and a tower no longer
    reveals it (climbing a tower still counts as its location, and opens its
    travel point). The logic does not change.
    region_keys: the maps are items, and a region's locations are in the logic once
    its map is received, as are the locations whose quest goes through another
    region with that region's map too. Nothing is locked in the game: a location
    done without its map counts all the same. The Great Plateau and Calamity Ganon
    need no map, nor do the towers unless Towers Need Maps or Region Lock is on."""
    display_name = "Tower Maps"
    option_vanilla = 0
    option_items = 1
    option_region_keys = 2
    default = 2


class EarlyMap(Choice):
    """With Tower Maps on items or region_keys, a map placed early: at one of the
    Great Plateau's first locations, those reachable from the start (its rune
    terminals and its tower), so that a region opens besides the towers once Link
    leaves the Plateau.
    none: no map placed early; until one comes, the towers are all the logic
    outside the Great Plateau (none of it with Towers Need Maps).
    gentle: one of the regions the game leads to first: Dueling Peaks, Hateno,
    Lake or Faron.
    any: any of the 14 maps.
    With Region Lock, only the maps of the regions bordering the Great Plateau are
    drawn."""
    display_name = "Early Map"
    option_none = 0
    option_gentle = 1
    option_any = 2
    default = 1


class TowersNeedMaps(Toggle):
    """With Tower Maps on region_keys, a tower is in the logic once its region's map
    is received, like the rest of its region. Off, the towers need no map, so that
    the early game has room before the maps come in; with Early Map on none, only
    the Great Plateau is then in the logic until a map comes. Region Lock always
    has the towers need their map."""
    display_name = "Towers Need Maps"


class RegionLock(Toggle):
    """With Tower Maps on region_keys, the regions open from the Great Plateau
    outward, as the game's map cuts them: a region is in the logic once its map is
    received and it borders a region already in the logic (with Map Travel Points,
    bordering one or not). Its tower then needs its map too, Hyrule Castle needs
    Central, and a quest that goes through another region needs that region in the
    logic. The game holds Link to it: he cannot enter a region not yet in the logic,
    and is sent back out of it."""
    display_name = "Region Lock"


class MapTravelPoints(Toggle):
    """With Tower Maps on items or region_keys, a map received also opens the travel
    point of a shrine near where its region begins, once Link has the Paraglider:
    he can warp there at once, and the game shows the shrine's name as it opens.
    The shrine stays a location, cleared as ever. With Region Lock, a region no
    longer needs to border one in the logic: its map and the Paraglider are enough,
    and the Early Map is drawn as without Region Lock."""
    display_name = "Map Travel Points"


class BikeAnywhere(Toggle):
    """The Master Cycle Zero (the Champions' Ballad DLC) can be summoned and ridden in
    the Gerudo Desert and on Death Mountain, which refuse it in the game, and goes
    through the invisible walls that stop horses, at the desert's entrances among
    others. Indoors still refuse it. Flying onto the desert or Death Mountain from a
    cliff outside still throws Link off just before the landing. The logic does not
    change."""
    display_name = "Master Cycle Zero Anywhere"


class CutsceneSkip(Choice):
    """How cutscenes play.
    off: as in the game.
    fast: cutscenes are skipped with + alone, without X first, and from the first game
    on: the opening on the Great Plateau too. The + prompt shows as soon as a cutscene
    can be skipped. A new game also starts without its black-screen intro. The cutscenes
    the game never lets be skipped can be too (the Shrine of Resurrection's pedestal and
    exit, the Great Plateau's first view). A page of text shows at once, without its
    pauses.
    removed (experimental): the same, and every cutscene fast skips is skipped at once,
    without +: what it gives or opens is kept.
    With fast or removed, the mode can be changed after the game pack is built, in Cemu's
    graphic packs (the Archipelago pack's Cutscenes preset), before the game starts; the
    launcher keeps the choice for the seed. Other scripted scenes (the animations
    and waits of dialogues, terminals, towers) do not change yet. The logic does not
    change."""
    display_name = "Skip Cutscenes"
    option_off = 0
    option_fast = 1
    option_removed = 2
    alias_false = 0
    alias_true = 1
    default = 0


class TrapPercentage(Range):
    """Share of the filler (arrows, elixirs, weapons, gems and rupees) that becomes traps,
    chosen among the traps of Trap Weights. 0: no trap. A trap strikes when it is
    received: Weapon Shatter breaks the weapon in Link's hand, Blood Moon calls a
    Blood Moon at once, Rupoor takes up to 100 rupees, Hearts Down takes up
    to two hearts (never the last quarter), Strip Down puts Link's weapon, shield,
    bow and armor back in the pouch, Cucco Swarm sends the angry cuccos' swarm, Yiga
    Ambush two Yiga Footsoldiers and a Yiga archer, Paranoia a Guardian that takes
    aim at Link and vanishes before it fires, and Downpour rain for 2 minutes or a
    thunderstorm for 90 s. The cuccos, the Yiga and the lightning can kill."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 0


class TrapWeights(OptionCounter):
    """How likely each trap is compared with the others: a trap of weight 2 comes up
    twice as often as one of weight 1. A trap left out of the list, or of weight 0,
    never comes up."""
    display_name = "Trap Weights"
    valid_keys = frozenset(TRAPS)
    min = 0
    default = {name: 1 for name in TRAPS}


class SpiritOrbs(Choice):
    """How hearts and stamina are won. The Goddess Statues trade four Spirit Orbs
    for a heart container or a stamina vessel, as in the game, whichever you choose.
    containers: 17 heart containers, 5 stamina vessels and 20 Spirit Orbs are items;
    the logic counts the heart containers.
    vanilla_statues: 108 Spirit Orbs are items, and no heart container nor stamina
    vessel: the statues give them all. The Master Sword asks for 40 Spirit Orbs, ten
    heart containers. This adds 66 items, which need room: chest_sanity, or
    korok_sanity with fewer Koroks holding your own filler (korok_local_filler).
    statue_checks: each trade at a statue is a location, up to statue_offerings of them,
    and gives nothing more; heart containers and stamina vessels are items, as with
    containers, and four Spirit Orbs per offering. Offering k asks for 4k orbs, and the
    Temple of Time's statue for a shrine cleared first, as in the game."""
    display_name = "Spirit Orbs"
    option_containers = 0
    option_vanilla_statues = 1
    option_statue_checks = 2
    default = 0


class StatueOfferings(Range):
    """With spirit_orbs on statue_checks, how many trades at the Goddess Statues are
    locations. Four Spirit Orbs per offering are items: five take the 20 of containers,
    and each one more adds four orbs and a location. Every orb is progression, which
    the Koroks, the chests and the quests hold only with korok_progression,
    chest_progression or quest_progression: above some ten offerings, turn one of
    them on."""
    display_name = "Statue Offerings"
    range_start = 1
    range_end = 30
    default = 5


class ChestSanity(Choice):
    """Whether the chests of Hyrule's surface (1,180), of its shrines (174) and of
    the Divine Beasts (35) are locations.
    off: they are not.
    check_only: opening a chest sends its location's item; the chest keeps its own
    contents, and a window says what was found and for whom.
    ap_items: each chest of the surface and of the Divine Beasts holds the item it
    sends, under its name, in place of its contents; a shrine's chest keeps its
    own, as with check_only, unless shrine_chest_items says otherwise.
    A Divine Beast cannot be entered again once freed: the chests left inside are
    sent then.
    Either way, the chests hold nothing needed to finish a game, unless
    chest_progression says otherwise."""
    display_name = "Chest Sanity"
    option_off = 0
    option_check_only = 1
    option_ap_items = 2
    alias_false = 0
    default = 0


class ChestProgression(Toggle):
    """With chest_sanity, whether chests may hold items needed to finish a game.
    The logic asks what the map says opening each one takes: runes, bombs, Death
    Mountain's heat, a Divine Beast freed, the Gerudo Set in Gerudo Town, and for
    a chest inside a shrine or a Divine Beast, every rune. A chest frozen in ice,
    under a boulder, after a Lynel's fight or created by a side quest still holds
    nothing needed. A buried chest holds nothing needed in the first half of the
    game: what it holds comes later."""
    display_name = "Chest Progression"


class ShrineChestItems(Toggle):
    """With chest_sanity on ap_items, whether a shrine's chest holds the item it
    sends too, in place of its contents.
    Warning: a shrine's chest only changes with its whole shrine, so this takes
    about 1 GB more disk space. These shrines are built once from your own copy of
    the game (its base game must be installed as a folder, not as a .wua or .wud
    file), then shared by every seed. Without such a folder, the shrines' chests
    keep their contents."""
    display_name = "Shrine Chest Items"


class KorokSanity(Toggle):
    """Whether Koroks are locations: finding one sends its location's item, and a
    window says what was found and for whom. The Korok still gives its seed, so
    Hestu is unchanged. The Koroks hold nothing needed to finish a game, unless
    korok_progression says otherwise."""
    display_name = "Korok Sanity"


class KorokCount(Range):
    """With korok_sanity, how many of the 900 Koroks are locations, drawn by the
    seed (900: every one). Each adds an item to the multiworld, mostly filler."""
    display_name = "Korok Count"
    range_start = 1
    range_end = 900
    default = 100


class KorokLocalFiller(Range):
    """With korok_sanity, the share in percent of those Koroks that hold filler of
    your own world, placed there before the multiworld is filled: they send nothing
    to the other players. The other Koroks hold any item no progression needs (any
    item with korok_progression), from any world, and add their filler to the
    multiworld."""
    display_name = "Korok Local Filler"
    range_start = 0
    range_end = 100
    default = 95


class KorokProgression(Toggle):
    """With korok_sanity, whether Koroks may hold items needed to finish a game.
    The logic asks what each Korok's puzzle takes: bombs for cracked rocks,
    Magnesis for iron, Death Mountain's heat, the Gerudo Set in Gerudo Town. A
    Korok behind an ice wall or ivy to burn still holds nothing needed."""
    display_name = "Korok Progression"


class SideQuestSanity(Toggle):
    """Whether the side quests are locations: finishing one sends its location's
    item, and a window says what was found and for whom. The quest still gives its
    reward, but Thunder Magnet's Rubber Helm and Lynel Safari's Zora Greaves,
    whose sets are items. 73 quests; left out: Slated for Upgrades (Purah's upgrades are
    locations already), A Gift from the Monks, The Statue's Bargain, and the EX
    quests of The Master Trials. They hold nothing needed to finish a game, unless
    quest_progression says otherwise. My Hero asks for the Master Sword, which then
    becomes a progression item."""
    display_name = "Side Quest Sanity"


class ShrineQuestSanity(Toggle):
    """Whether the 42 shrine quests are locations: finishing one, which raises its
    shrine, sends its location's item. Each asks what its shrine asks. They hold
    nothing needed to finish a game, unless quest_progression says otherwise."""
    display_name = "Shrine Quest Sanity"


class QuestProgression(Toggle):
    """With side_quest_sanity or shrine_quest_sanity, whether quests may hold items
    needed to finish a game. The logic asks what each quest takes: a shrine quest
    what its shrine asks; a side quest a rune, an armor set, a Divine Beast freed,
    the Camera or the maps of the regions it goes through. Hylian Homeowner and A
    Gift for the Great Fairy (rupees), The Weapon Connoisseur (weapons), From the
    Ground Up and the two Tarrey Town quests that follow it (long), Hunt for the
    Giant Horse and The Royal White Stallion (two stamina wheels to tame the horse)
    still hold nothing needed."""
    display_name = "Quest Progression"


class BossSanity(Toggle):
    """Whether the field bosses are locations: the first defeat of each of the 86
    Hinoxes, Stalnoxes, Stone Taluses and Moldugas whose defeat the game saves sends
    its location's item. A Blood Moon brings the
    boss back; its location stays sent. They hold nothing needed to finish a game,
    unless boss_progression says otherwise."""
    display_name = "Boss Sanity"


class BossProgression(Toggle):
    """With boss_sanity, whether bosses may hold items needed to finish a game. The
    logic asks for the boss's region and, on Death Mountain's burning slopes, the
    heat's protection; never a weapon: the fight is the player's."""
    display_name = "Boss Progression"


class ProgressiveHorse(Toggle):
    """Epona and the Master Cycle Zero are replaced by four Progressive Horses, given
    in this order: the Giant Horse, the Royal White Stallion (with the royal saddle and
    bridle), Epona, then the Master Cycle Zero. Each horse waits at the stables, as
    Epona does; with every stable full, it appears by Link."""
    display_name = "Progressive Horse"


class BonusItems(Range):
    """Share of the filler (arrows, elixirs, weapons, gems and rupees) that becomes
    bonus items: armor (boots, circlets, earrings, monster masks, the Hylian and Soldier's
    sets, the amiibo's and the DLC's sets), saddles and bridles. 38 at most, none needed
    to finish a game; traps keep their count. The armor is useful: it never goes where
    nothing useful may (a chest, Korok, quest or boss whose progression option is off).
    The saddles and bridles, for looks only, are filler. 0: none."""
    display_name = "Bonus Items"
    range_start = 0
    range_end = 100
    default = 0


class ExtraFiller(Toggle):
    """Adds to the filler what upgrades armor at the Great Fairies (the dragons' scales,
    claws, fangs and horns, the Lynels' horns, hooves and guts, the Guardians' parts and
    Luminous Stones), hearty and mighty food, raw or cooked, and 20 Bomb Arrows. The
    arrows, elixirs, weapons, gems and rupees come a little less often."""
    display_name = "Extra Filler"


@dataclass
class BotwOptions(PerGameCommonOptions):
    start_inventory_from_pool: StartInventoryPool
    goal: Goal
    goal_shrines: GoalShrines
    sanctum_divine_beasts: SanctumDivineBeasts
    sanctum_shrines: SanctumShrines
    sanctum_master_sword: SanctumMasterSword
    sanctum_runes: SanctumRunes
    beedle_shop_items: BeedleShopItems
    stall_items: StallItems
    death_link: DeathLink
    weapon_order: WeaponOrder
    tower_maps: TowerMaps
    early_map: EarlyMap
    towers_need_maps: TowersNeedMaps
    region_lock: RegionLock
    map_travel_points: MapTravelPoints
    bike_anywhere: BikeAnywhere
    cutscene_skip: CutsceneSkip
    spirit_orbs: SpiritOrbs
    statue_offerings: StatueOfferings
    chest_sanity: ChestSanity
    chest_progression: ChestProgression
    shrine_chest_items: ShrineChestItems
    korok_sanity: KorokSanity
    korok_count: KorokCount
    korok_local_filler: KorokLocalFiller
    korok_progression: KorokProgression
    side_quest_sanity: SideQuestSanity
    shrine_quest_sanity: ShrineQuestSanity
    quest_progression: QuestProgression
    boss_sanity: BossSanity
    boss_progression: BossProgression
    progressive_horse: ProgressiveHorse
    bonus_items: BonusItems
    extra_filler: ExtraFiller
    trap_percentage: TrapPercentage
    trap_weights: TrapWeights


OPTION_GROUPS = [
    OptionGroup("Goal", [Goal, GoalShrines]),
    OptionGroup("Hyrule Castle's Sanctum",
                [SanctumDivineBeasts, SanctumShrines, SanctumMasterSword, SanctumRunes]),
    OptionGroup("Shops", [BeedleShopItems, StallItems]),
    OptionGroup("Weapons", [WeaponOrder]),
    OptionGroup("Maps", [TowerMaps, EarlyMap, TowersNeedMaps, RegionLock, MapTravelPoints]),
    OptionGroup("Horses", [ProgressiveHorse]),
    OptionGroup("Master Cycle Zero", [BikeAnywhere]),
    OptionGroup("Cutscenes", [CutsceneSkip]),
    OptionGroup("Spirit Orbs", [SpiritOrbs, StatueOfferings]),
    OptionGroup("Chests", [ChestSanity, ChestProgression, ShrineChestItems]),
    OptionGroup("Koroks", [KorokSanity, KorokCount, KorokLocalFiller, KorokProgression]),
    OptionGroup("Quests", [SideQuestSanity, ShrineQuestSanity, QuestProgression]),
    OptionGroup("Bosses", [BossSanity, BossProgression]),
    OptionGroup("Bonus Items", [BonusItems]),
    OptionGroup("Filler", [ExtraFiller]),
    OptionGroup("Traps", [TrapPercentage, TrapWeights]),
]

# What the sanctum asks before Ganon, ready made (the options page's presets; a
# YAML sets the same options by hand). The defaults are Medium.
PRESETS = {
    "Easy": {"sanctum_divine_beasts": 4, "sanctum_shrines": 0,
             "sanctum_master_sword": True, "sanctum_runes": True},
    "Medium": {"sanctum_divine_beasts": 2, "sanctum_shrines": 0,
               "sanctum_master_sword": True, "sanctum_runes": True},
    "Hard": {"sanctum_divine_beasts": 0, "sanctum_shrines": 0,
             "sanctum_master_sword": False, "sanctum_runes": False},
}
