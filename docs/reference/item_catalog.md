# Item catalog

Sources: [`botw_world/data/items.json`](../../botw_world/data/items.json) defines the pool, the identifiers and the
classification; [`data/item_map.json`](../../data/item_map.json) defines what each item does in the game (its
`delivery`). The spoiler log of a seed (`AP_*_Spoiler.txt` in the generated archive) gives the placements.

## Pool size

111 items are declared, completed with `Rupee Bundle` up to the number of locations: 152 locations without the shop
options (41 rupee bundles), up to 212 with two items per shop and per stall (101 bundles). `Defeat Calamity Ganon` is
the victory location and holds no item.

## Progression and equipment

| Archipelago item | Count | In the game |
|---|---:|---|
| Paraglider | 1 | the paraglider (`PlayerStole2`) |
| Magnesis, Remote Bomb, Stasis, Cryonis | 1 each | the rune, presented by the Sheikah Slate's download screen, and selected |
| Sheikah Sensor | 1 | the sensor's flags |
| Warm Doublet | 1 | the doublet |
| Snowquill, Flamebreaker, Desert Voe, Zora, Rubber Set | 1 each | the three pieces of the set |
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

| Archipelago item | Count | In the game |
|---|---:|---|
| Spirit Orb | 20 | one Spirit Orb |
| Ancient Core | 10 | one ancient core |
| Star Fragment | 8 | one star fragment |
| Korok Seed | 15 | one Korok seed |
| Fairy | 6 | one fairy |
| Rupee Bundle | depends on the locations | 20 rupees |
| Blood Moon, Weapon Shatter | 4 each | declared, **not generated**: no automatic effect yet |

A received item is delivered by the game itself: its get window when it has one, the download screen for a rune,
otherwise straight into the inventory. Given back after the reload of an older save, it returns quietly, then an
Archipelago window lists the items given back (see [messages and deliveries](ap_messages.md)).
