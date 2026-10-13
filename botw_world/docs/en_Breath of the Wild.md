# The Legend of Zelda: Breath of the Wild

## Where is the options page?

The [player options page for this game](../player-options) contains all the options you need to configure and export
a config file.

## What does randomization do to this game?

The rewards of the game's main milestones become Archipelago locations: clearing a shrine, activating a tower, the
Great Fairies, freeing a Divine Beast, and so on. What those milestones gave in the normal game (the paraglider, the
runes, the champions' abilities, key armor, heart containers and stamina vessels) is shuffled into the multiworld
instead, and arrives in your game from wherever it was found.

The game runs on the Wii U version in the Cemu emulator. A game pack built for your seed replaces those rewards in the
game's own resources, and the Archipelago client delivers items while you play, through the game's own presentation:
the game's item window, or the Sheikah Slate's download screen for a rune. Items lost by reloading an older save are
given back quietly, then listed in a single Archipelago window.

## Which locations are there?

| Locations                                  | Count      |
|--------------------------------------------|------------|
| Shrines (4 on the Great Plateau)           | 120        |
| Sheikah Towers                             | 15         |
| Rune terminals of the Great Plateau        | 4          |
| Great Fairy fountains                      | 4          |
| Divine Beasts, and their heart containers  | 4 + 4      |
| Master Sword                               | 1          |
| Beedle's shops (option)                    | 0 to 32    |
| Village stalls (option)                    | 0 to 28    |

With the shop options, Archipelago items are sold by Beedle at his 16 shops (listed first in his stock) and placed as a
jewel on the village stalls, spread at random over 14 stalls (2 at most on one); buying one checks its location.
Opening Beedle's list, or looking at a stall's jewel, hints the items for sale there.

## Which items can be received?

- The Paraglider, and the four runes: Magnesis, Remote Bomb, Stasis and Cryonis
- The Sheikah Sensor
- Armor: Warm Doublet, Snowquill Set, Flamebreaker Set (Goron City's armor shop no longer sells it), Desert Voe Set,
  Zora Set, Rubber Set
- The Gerudo Set, the outfit Gerudo Town's guards let Link in with: Vilia no longer sells it
- The four champions' abilities: Revali's Gale, Daruk's Protection, Urbosa's Fury, Mipha's Grace
- Progressive Climbing Gear and Progressive Stealth Set (three pieces each)
- 17 Heart Containers and 5 Stamina Vessels
- The Master Sword, the Hylian Shield, the Champion's Tunic, the Ancient Bridle and Saddle, the Barbarian, Ancient
  and Radiant sets
- Pouch upgrades: 4 for weapons, 3 for bows, 4 for shields (each one of Hestu's, who offers one fewer)
- The Master Cycle Zero (The Champions' Ballad), the Travel Medallion and the Korok Mask (The Master Trials)
- Epona, registered at the stables: take her out at any of them
- The maps of the 14 regions (all but the Great Plateau's), with the `tower_maps` option: see below
- Spirit Orbs, Ancient Cores, Star Fragments, Fairies (the Koroks still give their seeds, as in the game)
- Filler: arrows (normal, fire, ice, shock, bomb, ancient), elixirs, weapons, gems and rupees
- Weapons, bows and shields: 83 of the game's, from the soldiers' to the Lynels', elemental and ancient ones, a few
  jokes (a Soup Ladle, a Pot Lid) and, rarely, the amiibo's treasures (Biggoron's Sword, the Twilight Bow...)
- Traps, with the `trap_percentage` option: Weapon Shatter, Blood Moon, Rupoor, Hearts Down, Strip Down and Cucco
  Swarm

## What is the goal?

The `goal` option says what finishes your game:

- `ganon` (the default): defeat Calamity Ganon;
- `divine_beasts`: free the four Divine Beasts;
- `shrines`: clear the number of shrines of `goal_shrines`.

## When can Link face Ganon?

Hyrule Castle's sanctum, where Ganon waits, stays sealed until what the `sanctum_` options ask is met, whatever the
goal: entering it sends Link back to its doors, a monk's line says the seal holds, and the Archipelago journal says
what is missing ("Sanctum sealed: 1/2 Divine Beasts freed, 3/4 runes"). Each option asks for one thing, and 0 or
`false` asks for nothing:

- `sanctum_divine_beasts`: Divine Beasts freed (0 to 4);
- `sanctum_shrines`: shrines cleared (0 to 120);
- `sanctum_master_sword`: the Master Sword received;
- `sanctum_runes`: the four runes received.

Three presets set them on the options page: **Easy** (the 4 Divine Beasts, the Master Sword and the runes),
**Medium** (2 Divine Beasts, the Master Sword and the runes: the defaults) and **Hard** (nothing: Ganon whenever Link
likes, as in the game).

## How does the logic work?

The Great Plateau is the only region reachable at first: its terminals need nothing, each of its four shrines needs
its rune, and leaving it needs the Paraglider. Beyond, the logic asks only for what the game itself blocks
(`data/logic.csv` in the world):

- **The runes on the way to a shrine's monk** (its chests left out). Where the game offers two ways, either rune
  is enough (Maka Rah: Magnesis or Stasis), unless one way is clearly the game's own. An entrance blocked by cracked
  rocks asks for Remote Bomb, bomb arrows not being sure to be at hand.
  The Divine Beasts keep all four runes.
- **The Flamebreaker Set** where Link catches fire, the game's burning zones: Death Mountain, Goron City and the
  canyon around it (Vah Rudania, Shae Mo'sah, Shora Hah...), and Tarrey Town's arrow stall, whose merchant comes in
  a quest that goes through the Southern Mine. The foothills around Foothill Stable do not burn. Cold and desert
  heat are crossed with food and elixirs, as in the game: no armor is required for them.
- **The Zora Set** where the way goes up a waterfall: Vah Ruta.
- **The Gerudo Set** for Gerudo Town, whose guards let Link in only wearing it, for Vah Naboris, whose quest goes
  through the town, and for the shrine quests given in the town.
- The freed Divine Beast for its heart container and for the shrines whose quest opens after it; ten Heart
  Containers for the Master Sword.

Only what these rules name is progression; the champions' abilities, the other armor, the climbing gear and the
stamina vessels help without being required, and come wherever the seed puts them.

## What do the region maps do?

A tower reveals one area of the game's map; each location belongs to the region of the tower whose map shows it. The
`tower_maps` option makes these maps items:

- `region_keys` (the default): the 14 maps, all but the Great Plateau's, are items. A region's locations are in the
  logic once its map is received; so are the locations whose quest goes through another region, with that region's
  map too: Tarrey Town's arrow stall (its quest recruits in Eldin, the Wasteland and Tabantha) and Shoqa Tatone
  (its quest wants pictures of Guardians, taken with the camera Purah gives in Hateno, of the kinds that roam
  Central Hyrule). The towers, the Great Plateau and Calamity Ganon need no map. Nothing is locked in the game: a
  location done without its map counts all the same, it was just out of the logic. The trackers show such a
  location as possible but out of logic: "glitched" in Universal Tracker, a sequence break (yellow) in PopTracker.
- `items`: the maps are items, but the logic does not ask for them.
- `vanilla`: as in the game, each tower reveals its own map; no map is an item.

With the maps as items, climbing a tower still counts as its location and opens its travel point, but no longer
reveals the map: a map received does, with the game's own animation of a map opening.

The `early_map` option places one map among the Great Plateau's first locations, those reachable from the start (its
rune terminals and its tower), so that a region opens besides the towers once Link leaves the Plateau: `gentle` (the
default) draws one of the regions the game leads to first (Dueling Peaks, Hateno, Lake or Faron), `any` one of the 14,
`none` places none early.

## How are the weapons spread?

The `weapon_order` option orders the weapons wherever they land in the multiworld, by the logic's spheres:

- `smoothed` (the default): the weaker first, the stronger as the game goes on, the amiibo's treasures last;
- `loosely_smoothed`: the same order, with some chance: a weapon may come a level earlier or later, never a treasure
  among the first;
- `anywhere`: wherever the fill put them, a treasure on the Great Plateau too.

The jokes come anywhere. Alone in a game, without the region maps as keys, the first sphere past the Great Plateau
holds most of Hyrule: the Plateau gets the weakest weapons, the strongest wait behind the last items, and the rest is
mixed. With them, each map opens a sphere of its own, and the weapons grow region after region.

## What does DeathLink do?

With the `death_link` option, Link's death kills the other DeathLink players of the room, with what killed him
("Player was slain by a Bokoblin", "Player froze to death"...), and their deaths kill Link.
A received death is first announced in the Archipelago journal, then Link dies as he would of a lethal blow: the
death animation, the Game Over screen and the reload of the last save. Mipha's Grace and fairies still save him, as
they would from any lethal blow; the received death is then spent. It waits for a safe moment: not during a
cutscene, a menu or a loading screen.

## What do traps do?

With the `trap_percentage` option, that share of the filler (arrows, elixirs, weapons, gems and rupees) becomes traps, drawn
by the `trap_weights` option (a trap of weight 0 or left out never comes up). A trap strikes when it is received,
at a safe moment, and the Archipelago journal says what it did. The cuccos, the Yiga and the storm's lightning can
kill Link.

| Trap | What it does |
|---|---|
| Weapon Shatter | The melee weapon in Link's hand is deleted. Empty hands, or the Master Sword, which never breaks: nothing. |
| Blood Moon | The Blood Moon rises at once: its cutscene plays and the defeated monsters come back. In a shrine or a place where the game allows none, the next midnight is the Blood Moon instead. |
| Rupoor | Takes up to 100 rupees: the largest of 100, 50, 20, 10, 5 or 1 the purse holds. |
| Hearts Down | Takes up to two hearts, never the last quarter. |
| Strip Down | Link's weapon, shield, bow and armor go back in the pouch, to equip again. |
| Cucco Swarm | The angry cuccos' swarm rushes at Link from every side for 10 s. It can kill. |
| Yiga Ambush | Two Yiga Footsoldiers and a Yiga archer appear around Link and attack. |
| Paranoia | A Guardian takes aim at Link from behind, beeping, and vanishes just before it fires. |
| Downpour | Rain for 2 minutes (the walls get slippery), or a thunderstorm for 90 s (its lightning strikes metal). Nothing shows in a shrine; a death or a reload ends it. |

A trap given back after loading an older save is spent without effect: the save forgot the trap's effect with the
rest, and a trap is not suffered twice.

## What does another world's item look like in Breath of the Wild?

Your own items appear as the game shows them. An item for another player is announced in the Archipelago journal, a
line of text in the game's tip frame (top right of the screen). In shops and on stalls, it is shown as an Archipelago
jewel, with the item's name and its recipient.

## Current limitations

- Only the European Wii U version, update v208, in Cemu on Windows, is supported.
- Each player's launcher builds a game pack for their seed, from their slot file (`.apbotw`, on the room's page
  or in the seed's zip). The seed is generated with Archipelago on a computer, then hosted anywhere, archipelago.gg
  included.
