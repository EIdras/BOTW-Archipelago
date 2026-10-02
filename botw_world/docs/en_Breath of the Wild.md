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
medallion on the village stalls, spread at random over 14 stalls (2 at most on one); buying one checks its location.

## Which items can be received?

- The Paraglider, and the four runes: Magnesis, Remote Bomb, Stasis and Cryonis
- The Sheikah Sensor
- Climate armor: Warm Doublet, Snowquill Set, Flamebreaker Set, Desert Voe Set, Zora Set, Rubber Set
- The four champions' abilities: Revali's Gale, Daruk's Protection, Urbosa's Fury, Mipha's Grace
- Progressive Climbing Gear and Progressive Stealth Set (three pieces each)
- 17 Heart Containers and 5 Stamina Vessels
- The Master Sword, the Hylian Shield, the Champion's Tunic, the Ancient Bridle and Saddle, the Barbarian, Ancient
  and Radiant sets
- Spirit Orbs, Ancient Cores, Star Fragments, Fairies and rupees (the Koroks still give their seeds, as in the game)
- Traps, with the `trap_percentage` option: Weapon Shatter, Blood Moon, Rupoor, Hearts Down, Strip Down and Cucco
  Swarm

## What is the goal?

Defeat Calamity Ganon. Two options can add a requirement before the final fight counts: a number of freed Divine
Beasts, or a number of cleared shrines.

## How does the logic work?

The Great Plateau is the only region reachable at first: its terminals need nothing, each of its four shrines needs
its rune, and leaving it needs the Paraglider. Outside the Plateau, every shrine and Divine Beast, and Ganon,
conservatively require the Paraglider and all four runes. Some shrine quests need their Divine Beast freed, and the
Master Sword needs ten Heart Containers. Food and equipment of the normal game are assumed available.

## What does DeathLink do?

With the `death_link` option, Link's death kills the other DeathLink players of the room, with what killed him
("Player was slain by a Bokoblin", "Player froze to death"...), and their deaths kill Link.
A received death is first announced in the Archipelago journal, then Link dies as he would of a lethal blow: the
death animation, the Game Over screen and the reload of the last save. Mipha's Grace and fairies still save him, as
they would from any lethal blow; the received death is then spent. It waits for a safe moment: not during a
cutscene, a menu or a loading screen.

## What do traps do?

With the `trap_percentage` option, that share of the filler, the items that would be rupees, becomes traps, drawn
by the `trap_weights` option (a trap of weight 0 or left out never comes up). A trap strikes when it is received,
at a safe moment, and the Archipelago journal says what it did. Only the cuccos can kill Link.

| Trap | What it does |
|---|---|
| Weapon Shatter | The melee weapon in Link's hand is deleted. Empty hands, or the Master Sword, which never breaks: nothing. |
| Blood Moon | The Blood Moon rises at once: its cutscene plays and the defeated monsters come back. In a shrine or a place where the game allows none, the next midnight is the Blood Moon instead. |
| Rupoor | Takes up to 100 rupees: the largest of 100, 50, 20, 10, 5 or 1 the purse holds. |
| Hearts Down | Takes up to two hearts, never the last quarter. |
| Strip Down | Link's weapon, shield, bow and armor go back in the pouch, to equip again. |
| Cucco Swarm | The angry cuccos' swarm rushes at Link from every side for 10 s. It can kill; such a death is not sent as a DeathLink. |

A trap given back after loading an older save is spent without effect: the save forgot the trap's effect with the
rest, and a trap is not suffered twice.

## What does another world's item look like in Breath of the Wild?

Your own items appear as the game shows them. An item for another player is announced in the Archipelago journal, a
line of text in the game's tip frame (top right of the screen). In shops and on stalls, it is shown as an Archipelago
medallion, with the item's name and its recipient.

## Current limitations

- Only the European Wii U version, update v208, in Cemu on Windows, is supported.
- Each player's launcher builds a game pack for their seed, from their slot file (`.apbotw`, on the room's page
  or in the seed's zip). The seed is generated with Archipelago on a computer, then hosted anywhere, archipelago.gg
  included.
