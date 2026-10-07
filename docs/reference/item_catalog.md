# Item catalog

Sources: [`botw_world/data/items.json`](../../botw_world/data/items.json) defines the pool, the identifiers and the
classification; [`data/item_map.json`](../../data/item_map.json) defines what each item does in the game (its
`delivery`). The spoiler log of a seed (`AP_*_Spoiler.txt` in the generated archive) gives the placements.

## Pool size

112 items are declared, completed with drawn filler up to the number of locations: 152 locations without the shop
options (40 filler items), up to 212 with two items in every shop and all 28 stall items (100). `Defeat Calamity Ganon` is
the victory location and holds no item.

## Progression and equipment

| Archipelago item | Count | In the game |
|---|---:|---|
| Paraglider | 1 | the paraglider (`PlayerStole2`) |
| Magnesis, Remote Bomb, Stasis, Cryonis | 1 each | the rune, presented by the Sheikah Slate's download screen, and selected |
| Sheikah Sensor | 1 | the sensor's flags |
| Warm Doublet | 1 | the doublet |
| Snowquill, Flamebreaker, Desert Voe, Zora, Rubber Set | 1 each | the three pieces of the set; King Dorephan no longer gives the Zora armor, which Vah Ruta asks for, nor Kima the Flamebreaker armor, which the burning zones ask for; Goron City's armor shop says it is sold out when Link buys a piece ([`botw_patch/goron_armor.py`](../../botw_patch/goron_armor.py)) |
| Gerudo Set | 1 | the veil, top and sirwal that let Link into Gerudo Town; Vilia no longer sells them: she asks 1,000,000 rupees, and her lines say so in every language ([`botw_patch/gerudo_outfit.py`](../../botw_patch/gerudo_outfit.py)) |
| Revali's Gale, Daruk's Protection, Urbosa's Fury, Mipha's Grace | 1 each | the champion's ability, with its get window |
| Progressive Climbing Gear | 3 | body, head, legs, in that order |
| Progressive Stealth Set | 3 | body, head, legs, in that order |
| Heart Container | 17 | one heart, with the game's get window |
| Stamina Vessel | 5 | one stamina segment, with the game's get window |
| Master Sword, Hylian Shield, Champion's Tunic | 1 each | the equipment |
| Ancient Bridle, Ancient Saddle | 1 each | the horse gear |
| Master Cycle Zero | 1 | the motorcycle (DLC 2), as a rune: the Sheikah Slate's download screen (type 5, as `Demo645_0` gives it, without equipping it), then its flag; the rune in hand stays selected, and with none, the client has the game select the motorcycle as the inventory does (owned but unselected, the Slate had no module to use); its tank is full |
| Epona | 1 | registered at the stables in the first free slot, under her name in the game's language (her actor's, for Cemu's console language), with her saddle and bridle, as a stable registers her, through the game's own GameData setters ([`botw_client/horse_stable.py`](../../botw_client/horse_stable.py)); the entry then sets `Horse_Is_Registration`. Stables full: created by Link as the amiibo creates her, the first time only |
| Travel Medallion, Korok Mask | 1 each | the medallion and the mask (DLC 1), with their get window |
| Barbarian, Ancient, Radiant Set | 1 each | the three pieces of the set |
| Weapon, Bow, Shield Pouch Upgrade | 4, 3, 4 | one of Hestu's upgrades (`Npc_OldKorok`): his next upgrade flag, one more slot, then his pouch screen when Link holds an item of that pouch (in an empty pouch the screen played on another page: the slot comes quietly and the tab shows, already grown, with the first item); he offers one fewer, so the pouch never passes the game's maximum, and once he has given them all the item adds nothing |

The sets are deliberately strong: they are not filler items.

## Filler and traps

The filler is generated to fill the pool, one draw per slot left (`FILLER` in `botw_world/catalog.py`): arrows 30 %,
elixirs 25 %, weapons 25 %, gems 10 %, rupees 10 %, then one item of the family (rupees: smaller sums more often;
weapons: a group by its weight, see below). With the `trap_percentage` option, that share of the filler slots is
taken by traps instead, drawn by `trap_weights` (0 by default: no trap). What each trap does, and how: [traps.md](traps.md).

| Archipelago item | Count | In the game |
|---|---:|---|
| Spirit Orb | 20 | one Spirit Orb |
| Ancient Core | 10 | one ancient core |
| Star Fragment | 8 | one star fragment |
| Korok Seed | 0 | one Korok seed: none in the pool, the Koroks give theirs |
| Fairy | 6 | one fairy |
| 10 Arrows, 10 Fire / Ice / Shock / Bomb Arrows, 5 Ancient Arrows | drawn | the arrows, by the game's get window as Riju gives her bomb arrows (`IsInvalidOpenPouch` on: off, the window says 0 arrows); received again, quietly (`Demo_IncreasePorchItem`, one bundle) |
| Diamond, Ruby, Sapphire, Topaz, Opal, Amber | drawn | one gem |
| Hasty, Electro, Tough, Hearty, Fireproof, Chilly, Spicy, Mighty, Sneaky, Energizing, Enduring Elixir, Fairy Tonic | drawn | the elixir, cooked by the game from its ingredients (`Demo_SetCookItem`, the Champions' Ballad's recipes or two critters and a Bokoblin Horn), then the cooking pot's own window (`GetDemo<ShowGetDemoCookResult>`), every time |
| Blue Rupee (5), Red Rupee (20, `Rupee Bundle` in seeds generated before), Purple Rupee (50), Silver Rupee (100), Gold Rupee (300) | drawn | the rupees |
| 83 weapons, bows and shields (below) | drawn | the weapon, with the game's get window every time; the pouch full, it falls at Link's feet |
| Weapon Shatter, Blood Moon, Rupoor, Hearts Down, Strip Down, Cucco Swarm | none fixed | traps, see below |

A received item is delivered by the game itself: its get window when it has one, the download screen for a rune,
otherwise straight into the inventory. Given back after the reload of an older save, it returns quietly, then an
Archipelago window lists the items given back (see [messages and deliveries](ap_messages.md)).

## Weapons

Drawn by group (`WEAPONS` in `botw_world/catalog.py`), then one weapon of the group; a weapon's level orders them
through the game. The amiibo's treasures are useful items, the others filler; all are in the item group `Weapons`.

| Group | Weight | Level | Weapons |
|---|---:|---:|---|
| medium | 20 | 1 | Soldier's Broadsword, Claymore, Spear, Bow, Shield; Zora Sword, Gerudo Scimitar, Gerudo Spear, Eightfold Blade, Silver Bow |
| solid | 25 | 2 | Knight's Broadsword, Claymore, Bow, Shield; Royal Broadsword, Claymore, Halberd, Bow, Shield |
| elemental | 20 | 2 | Flameblade, Frostblade, Thunderblade and their Great ones; Flamespear, Frostspear, Thunderspear; Fire, Ice, Lightning, Meteor, Blizzard, Thunderstorm Rod |
| fragile | 10 | 3 | Royal Guard's Sword, Claymore, Spear, Bow, Shield; Dragonbone Boko Bat, Dragonbone Moblin Club |
| ancient | 10 | 3 | Ancient Short Sword, Bladesaw, Spear, Bow, Shield; Guardian Sword++, Ancient Battle Axe++, Guardian Spear++, Guardian Shield++ |
| mighty_lynel | 5 | 3 | Mighty Lynel Sword, Crusher, Spear, Bow, Shield |
| savage_lynel | 5 | 4 | Savage Lynel Sword, Crusher, Spear, Bow, Shield |
| special | 5 | 3 | Korok Leaf, Giant Boomerang, Sea-Breeze Boomerang, Duplex Bow, Phrenic Bow, Demon Carver, Windcleaver, Stone Smasher, Torch, Moonlight Scimitar |
| treasure | 4 | 5 | Biggoron's Sword, Fierce Deity Sword, Sword of the Six Sages, Goddess Sword, Sword, Twilight Bow, Hero's Shield |
| joke | 4 | — | Soup Ladle, Boat Oar, Farming Hoe, Wooden Mop, Tree Branch, Pot Lid |

Left out: the Master Sword (an item of its own) and its other forms, the Bow of Light (the final fight's), the
One-Hit Obliterator (DLC 2), the champions' weapons (the game gives them after each Divine Beast), the weak
Bokoblin, Moblin and Lizalfos weapons, the arms and the rusty ones.

`weapon_order` spreads them over the game, as Dark Souls III smooths its weapons
(`BotwWorld.stage_finalize_multiworld`): after the fill and the progression balancing, the locations holding a world's
weapons, in any world of the multiworld, are taken by sphere, and its weapons dealt again over them by level, the
weaker first. `smoothed` (the default) follows the levels; `loosely_smoothed` moves each level by up to 1.5 at
random, so a weapon may come a level earlier or later, never a treasure among the first; `anywhere` keeps the fill's
placement. The jokes stay where the fill put them. No rule names a weapon, so the spheres do not change; a location's
own rules still decide what it takes. In a solo game the first sphere after the Great Plateau holds most of Hyrule:
there the weapons are mixed, the weakest on the Plateau, the strongest behind the last items.
