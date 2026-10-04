# Item catalog

Sources: [`botw_world/data/items.json`](../../botw_world/data/items.json) defines the pool, the identifiers and the
classification; [`data/item_map.json`](../../data/item_map.json) defines what each item does in the game (its
`delivery`). The spoiler log of a seed (`AP_*_Spoiler.txt` in the generated archive) gives the placements.

## Pool size

97 items are declared, completed with `Rupee Bundle` up to the number of locations: 152 locations without the shop
options (55 rupee bundles), up to 212 with two items in every shop and all 28 stall items (115 bundles). `Defeat Calamity Ganon` is
the victory location and holds no item.

## Progression and equipment

| Archipelago item | Count | In the game |
|---|---:|---|
| Paraglider | 1 | the paraglider (`PlayerStole2`) |
| Magnesis, Remote Bomb, Stasis, Cryonis | 1 each | the rune, presented by the Sheikah Slate's download screen, and selected |
| Sheikah Sensor | 1 | the sensor's flags |
| Warm Doublet | 1 | the doublet |
| Snowquill, Flamebreaker, Desert Voe, Zora, Rubber Set | 1 each | the three pieces of the set |
| Gerudo Set | 1 | the veil, top and sirwal that let Link into Gerudo Town; Vilia no longer sells them: she asks 1,000,000 rupees, and her lines say so in every language ([`botw_patch/gerudo_outfit.py`](../../botw_patch/gerudo_outfit.py)) |
| Revali's Gale, Daruk's Protection, Urbosa's Fury, Mipha's Grace | 1 each | the champion's ability, with its get window |
| Progressive Climbing Gear | 3 | body, head, legs, in that order |
| Progressive Stealth Set | 3 | body, head, legs, in that order |
| Heart Container | 17 | one heart, with the game's get window |
| Stamina Vessel | 5 | one stamina segment, with the game's get window |
| Master Sword, Hylian Shield, Champion's Tunic | 1 each | the equipment |
| Ancient Bridle, Ancient Saddle | 1 each | the horse gear |
| Barbarian, Ancient, Radiant Set | 1 each | the three pieces of the set |

The sets are deliberately strong: they are not filler items.

## Filler and traps

The filler is generated to fill the pool. With the `trap_percentage` option, that share of the `Rupee Bundle` slots
is taken by traps instead, drawn by `trap_weights` (0 by default: no trap). What each trap does, and how:
[traps.md](traps.md).

| Archipelago item | Count | In the game |
|---|---:|---|
| Spirit Orb | 20 | one Spirit Orb |
| Ancient Core | 10 | one ancient core |
| Star Fragment | 8 | one star fragment |
| Korok Seed | 0 | one Korok seed: none in the pool, the Koroks give theirs |
| Fairy | 6 | one fairy |
| Rupee Bundle | depends on the locations | 20 rupees |
| Weapon Shatter, Blood Moon, Rupoor, Hearts Down, Strip Down, Cucco Swarm | none fixed | traps, see below |

A received item is delivered by the game itself: its get window when it has one, the download screen for a rune,
otherwise straight into the inventory. Given back after the reload of an older save, it returns quietly, then an
Archipelago window lists the items given back (see [messages and deliveries](ap_messages.md)).
