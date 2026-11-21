# The Legend of Zelda: Breath of the Wild

[Setup](setup_en.md) · [In the game](ingame_en.md) · **Options** · [Hosting](hosting_en.md) ·
[Trackers](poptracker_en.md) · [Mods](mods_en.md) · [Troubleshooting](troubleshooting_en.md)

## What does randomization do to this game?

The rewards of the game's milestones become Archipelago locations: clearing a shrine, activating a tower, a Great
Fairy, freeing a Divine Beast, and more. What those milestones gave in the normal game (the Paraglider, the runes,
the champions' abilities, key armor, heart containers and stamina vessels) is shuffled into the multiworld instead,
and arrives in your game from wherever it was found.

The game runs on the Wii U version in the Cemu emulator. A game pack built for your seed replaces those rewards in the
game's own resources, and the Archipelago client delivers items while you play: see [In the game](ingame_en.md).

## Where are the options?

In the player's YAML file. The release brings a ready one, `players\BOTW.yaml`, and the Archipelago Launcher writes a
template with "Generate Template Options". Every option is explained [below](#options).

## Locations

| Locations | Count |
|---|---|
| Shrines (4 on the Great Plateau) | 120 |
| Sheikah Towers | 15 |
| Rune terminals of the Great Plateau | 4 |
| Great Fairy fountains | 4 |
| Divine Beasts, and their heart containers | 4 + 4 |
| Master Sword | 1 |
| Purah's rune upgrades, in Hateno | 3 |
| Songs of the Champions' Ballad | 4 |
| Beedle's shops (option) | 0 to 32 |
| Village stalls (option) | 0 to 28 |
| Koroks (option `korok_sanity`) | 0 to 900 |
| Side quests (option `side_quest_sanity`) | 0 or 73 |
| Shrine quests (option `shrine_quest_sanity`) | 0 or 42 |
| Goddess Statue offerings (option [`spirit_orbs`](#spirit-orbs)) | 0, or 1 to 30 |

The Koroks are many: by default, 95 % of those that are locations hold filler of your own world
(`korok_local_filler`), so that they don't flood the other players with filler. With
`korok_progression`, the others may hold items needed to finish a game, and the logic asks what each
Korok's puzzle takes (bombs, Magnesis, the Gerudo Set in Gerudo Town).

A quest is checked once it is finished, and still gives its reward, but for the pieces of set items:
Thunder Magnet's Rubber Helm and Lynel Safari's Zora Greaves, which the Rubber and Zora Sets bring. The
quests hold nothing needed to finish a game. A shrine quest asks what its shrine asks. Left out of the side quests: Slated for
Upgrades (Purah's upgrades are locations already), A Gift from the Monks, The Statue's Bargain, and the
EX quests of The Master Trials.

## Items

**Progression and key items**

- The **Paraglider**, and the four runes: Magnesis, Cryonis, **Progressive Remote Bomb** and **Progressive Stasis**
  (the first copy is the rune, the second its upgrade, Remote Bomb+ or Stasis+).
- The **Progressive Sheikah Sensor**: the Sheikah Sensor, then the Sheikah Sensor+. Purah's camera no longer comes
  with it.
- Armor: Warm Doublet, Snowquill Set, Flamebreaker Set, Desert Voe Set, Zora Set, Rubber Set, and the Gerudo Set,
  which lets Link into Gerudo Town. Goron City's armor shop no longer sells the Flamebreaker Set, nor Vilia the
  Gerudo Set.
- The four champions' abilities, progressive: the first copy is the ability, the second the upgraded power of the
  Champions' Ballad (shorter recharge).
- Progressive Climbing Gear and Progressive Stealth Set (three pieces each).
- 17 Heart Containers and 5 Stamina Vessels, or 88 more Spirit Orbs in their place ([`spirit_orbs`](#spirit-orbs)).
- The maps of the 14 regions (all but the Great Plateau's), with the [`tower_maps`](#region-maps) option.

**Useful items**

- The Master Sword, the Hylian Shield, the Champion's Tunic, the Ancient Bridle and Saddle, the Barbarian, Ancient
  and Radiant sets.
- Pouch upgrades: 4 for weapons, 3 for bows, 4 for shields. Each one is one of Hestu's, who offers one fewer.
- The Master Cycle Zero (The Champions' Ballad), the Travel Medallion and the Korok Mask (The Master Trials).
- Epona, registered at the stables.
- Spirit Orbs, Ancient Cores, Star Fragments and Fairies. The Koroks still give their seeds, as in the game, even
  when they are locations.

**Filler**

- Arrows (normal, fire, ice, shock, bomb, ancient), elixirs, gems and rupees.
- Weapons, bows and shields: 83 of the game's, from the soldiers' to the Lynels', elemental and ancient ones, a few
  jokes (a Soup Ladle, a Pot Lid) and, rarely, the amiibo's treasures (Biggoron's Sword, the Twilight Bow...).
- [Traps](#traps), with the `trap_percentage` option.

## Goal

The `goal` option says what finishes your game:

| `goal` | Finished when |
|---|---|
| `ganon` (default) | Calamity Ganon is defeated |
| `divine_beasts` | the four Divine Beasts are freed |
| `shrines` | `goal_shrines` shrines are cleared (1 to 120, default 60) |

Whatever the goal, Ganon's sanctum stays [sealed](#the-sealed-sanctum) until its own requirements are met.

## Logic

The Great Plateau is the only region reachable at first: its terminals need nothing, each of its four shrines needs
its rune, and leaving it needs the Paraglider. Beyond, the logic asks only for what the game itself blocks:

- **Runes on the way to a shrine's monk** (its chests left out). Where the game offers two ways, either rune is
  enough (Maka Rah's spiked balls: Magnesis or Stasis), unless one way is clearly the game's own. An entrance
  blocked by cracked rocks asks for Remote Bomb. The Divine Beasts ask for all four runes.
- **The Flamebreaker Set** where Link catches fire: Death Mountain, Goron City and the canyon around it, and Tarrey
  Town's arrow stall, whose merchant comes through the Southern Mine. Cold and desert heat are crossed with food and
  elixirs, as in the game: no armor is required for them.
- **The Zora Set** up the waterfalls to Vah Ruta.
- **The Gerudo Set** for Gerudo Town, for Vah Naboris, whose quest goes through the town, and for the shrine quests
  given in the town.
- **Purah's upgrades** once her quest Locked Mementos is done, which Impa gives in Kakariko. Each also asks for
  three ancient parts that Guardians drop, which the logic leaves out, as it does food.
- **The Champions' Ballad** once the four Divine Beasts are freed; its trials on the Great Plateau want the four
  runes, and each song what the way to its champion's region asks.
- **A freed Divine Beast** for its heart container, and for the shrines whose quest opens after it.
- **13 hearts for the Master Sword**, as in the game: 10 Heart Containers, or 40 Spirit Orbs with
  [`spirit_orbs`](#spirit-orbs) on `vanilla_statues`.

Only what these rules name is progression. The champions' abilities, the other armor, the climbing gear and the
stamina vessels help without being required.

## Options

| Group | Option | Default | In short |
|---|---|---|---|
| Goal | [`goal`, `goal_shrines`](#goal) | `ganon`, 60 | What finishes your game |
| Sanctum | [`sanctum_divine_beasts`](#the-sealed-sanctum) | 2 | Divine Beasts freed before Ganon |
| | [`sanctum_shrines`](#the-sealed-sanctum) | 0 | Shrines cleared before Ganon |
| | [`sanctum_master_sword`](#the-sealed-sanctum) | true | The Master Sword before Ganon |
| | [`sanctum_runes`](#the-sealed-sanctum) | true | The four runes before Ganon |
| Shops | [`beedle_shop_items`](#shops-and-stalls) | 0 | Archipelago items at each of Beedle's 16 shops (0 to 2) |
| | [`stall_items`](#shops-and-stalls) | 0 | Archipelago items on the village stalls (0 to 28) |
| Weapons | [`weapon_order`](#weapon-order) | `smoothed` | Weaker weapons first, stronger later |
| Maps | [`tower_maps`](#region-maps) | `region_keys` | Region maps are items, and keys of the logic |
| | [`early_map`](#region-maps) | `gentle` | One map among the Great Plateau's first checks |
| | [`towers_need_maps`](#towers-need-maps) | false | A tower needs its region's map too |
| | [`region_lock`](#region-lock) | false | Regions open from the Great Plateau outward |
| | [`map_travel_points`](#map-travel-points) | false | A map received opens a travel point |
| Master Cycle Zero | [`bike_anywhere`](#master-cycle-zero-anywhere) | false | The bike in the desert and on Death Mountain |
| Cutscenes | [`cutscene_skip`](#skip-cutscenes) | false | + alone skips a cutscene, from a first game on |
| Spirit Orbs | [`spirit_orbs`](#spirit-orbs) | `containers` | Hearts and stamina as items, or from the statues |
| Traps | [`trap_percentage`, `trap_weights`](#traps) | 0 | Share of the filler turned into traps |
| | `death_link` | false | [DeathLink](#deathlink) |

### The sealed sanctum

Hyrule Castle's sanctum, where Ganon waits, stays sealed until what the `sanctum_` options ask is met, whatever the
goal ([what you see](ingame_en.md#the-sealed-sanctum)). Each option asks for one thing; 0 or `false` asks for
nothing. Three levels, as the options' presets set them:

| Preset | Divine Beasts | Master Sword | Runes |
|---|---|---|---|
| Easy | 4 | yes | yes |
| Medium (default) | 2 | yes | yes |
| Hard | 0 | no | no (Ganon whenever Link likes, as in the game) |

### Shops and stalls

- `beedle_shop_items`: Beedle sells that many Archipelago items, listed first, at each of his 16 shops (the 15
  stables and Kara Kara Bazaar).
- `stall_items`: that many Archipelago items, as jewels, spread at random over the 14 village stalls, 2 at most on
  one.

Buying one checks its location ([what you see](ingame_en.md#shops-and-stalls)).

### Weapon order

`weapon_order` orders the weapons wherever they land in the multiworld, by the logic's spheres:

- `smoothed` (default): the weaker first, the stronger as the game goes on, the amiibo's treasures last;
- `loosely_smoothed`: the same order, with some chance: a weapon may come a level earlier or later, never a treasure
  among the first;
- `anywhere`: wherever the fill put them, a treasure on the Great Plateau too.

The jokes come anywhere. With the region maps as keys, each map opens a sphere of its own, and the weapons grow region
after region.

### Region maps

A tower reveals one area of the game's map; each location belongs to the region of the tower whose map shows it.
`tower_maps` makes these maps items:

| `tower_maps` | The 14 maps are items | The logic asks for them |
|---|---|---|
| `region_keys` (default) | yes | yes: a region's locations are in the logic once its map is received |
| `items` | yes | no |
| `vanilla` | no: each tower reveals its own map | no |

With the maps as items, climbing a tower still counts as its location and opens its travel point, but no longer
reveals the map: a map received does, with the game's own animation.

> [!TIP]
> Nothing is locked in the game: a location done without its map counts all the same, it was just out of logic.
> The trackers show it as possible but out of logic.

With `region_keys`, the Great Plateau and Calamity Ganon need no map, nor do the towers unless `towers_need_maps` or
`region_lock` is on. A location whose quest goes through
another region needs that region's map too: Tarrey Town's arrow stall (its quest starts in Hateno once Link owns the
house there, then recruits in Eldin, the Wasteland and Tabantha), Purah's upgrades (Impa, in Kakariko, sends Link to
her), Shoqa Tatone (its quest wants pictures of Central Hyrule's Guardians, taken with Purah's camera), Kah Yah (its
quest wants Purah's camera), Shae Katha and Tutsuwa Nima (their doors want a scale of Farosh or Dinraal, who fly only
once Link has met Impa), Kah Mael (reached from Akkala's cliffs) and Revali's Song (one of its trials is in
Ridgeland).

`early_map` places one map among the Great Plateau's first checks (its rune terminals and its tower), so that a region
opens besides the towers (or at all, with `towers_need_maps`) once Link leaves the Plateau:

- `gentle` (default): one of the regions the game leads to first (Dueling Peaks, Hateno, Lake or Faron);
- `any`: one of the 14;
- `none`: none early.

What each combination asks for, with `tower_maps: region_keys`:

| Options | A region's locations need its map | A tower needs its map | A region must border one in the logic | The game keeps Link out |
|---|---|---|---|---|
| none of these | yes | no | no | no |
| `towers_need_maps` | yes | yes | no | no |
| `region_lock` | yes | yes | yes | yes |
| `region_lock` and `map_travel_points` | yes | yes | no: its travel point is warped to | yes |

### Towers need maps

`towers_need_maps` (with `tower_maps: region_keys` only) puts each tower behind its region's map, like the rest of its
region, in any order. Off, the towers need no map, so that the early game has room before the maps come in: with
`early_map: none`, only the Great Plateau is in the logic until a map comes. `region_lock` always has the towers need
their map.

### Region lock

`region_lock` (with `tower_maps: region_keys` only) opens the regions from the Great Plateau outward, as the game's
map cuts them: a region is in the logic once its map is received **and** it borders a region already in the logic.
The Great Plateau borders Central, Dueling Peaks, Lake and the Wasteland. The logic leaves out the few borders the
game offers no way across (the cliffs around the Gerudo Highlands, the climb from Ridgeland to Hebra).

A tower then needs its region's map too, Calamity Ganon needs Central, a quest through another region needs to reach
that region, and `early_map` draws only among the Great Plateau's neighbours. The client keeps Link out of the regions
not yet in the logic ([what you see](ingame_en.md#region-borders)). Universal Tracker and the PopTracker pack follow
this option, from the seed's own borders: a location whose regions are out of reach shows as out of logic.

### Map travel points

`map_travel_points` (with the maps as items) makes a map received also open the travel point of one shrine near
where its region begins, once Link has the Paraglider, so that he can warp there at once; the game shows the shrine's name as it opens. The shrine stays
a location, cleared as ever. With `region_lock`, a region is then in the logic once its map and the Paraglider are
received, whether or not it borders a region in the logic (its tower still needs it), and `early_map` draws as without
`region_lock`.

### Master Cycle Zero anywhere

The game refuses the Master Cycle Zero in the Gerudo Desert and on Death Mountain, and the invisible walls that stop
horses stop it too. With `bike_anywhere`, it can be summoned and ridden there and goes through those walls. Indoors
still refuse it, and flying onto the desert or Death Mountain from a cliff outside still throws Link off just before
landing. The logic does not change.

### Skip cutscenes

With `cutscene_skip` on `fast`, + alone skips a cutscene, without X first, and from a first game on: an Archipelago game always
starts as one. The + prompt shows as soon as a cutscene can be skipped, without waiting for X. The black-screen intro
before Link wakes is gone, and a cutscene can be skipped while it fades in.
The cutscenes the game never lets be skipped can be too: the Shrine of Resurrection's pedestal and exit, and the first
view of the Great Plateau. A skip leaves the game as the cutscene does: the Sheikah Slate taken, the doors open. A page of
text shows at once, without its pauses. The animations and waits the game plays within dialogues, terminals and towers do
not change yet. The logic does not change.

On `removed` (experimental), every cutscene `fast` skips is skipped at once, without +: what it gives or opens is kept.
The mode can be changed once the game pack is built: in Cemu, Options > Graphic packs, the Archipelago pack's Cutscenes
preset ("Skipped with +" or "Removed (experimental)"). Change it before the game starts: Cemu pauses some seconds when it
is changed in game, and it takes effect when the game restarts. The launcher keeps the choice for the seed.

### Spirit Orbs

As in the game, any Goddess Statue (the Temple of Time's on the Great Plateau too) trades four Spirit Orbs for a heart
container or a stamina vessel, as you choose.

| `spirit_orbs` | Items | The Master Sword asks for |
|---|---|---|
| `containers` (default) | 17 Heart Containers, 5 Stamina Vessels, 20 Spirit Orbs | 10 Heart Containers |
| `vanilla_statues` | 108 Spirit Orbs: the statues give every heart and stamina vessel | 40 Spirit Orbs |
| `statue_checks` | 17 Heart Containers, 5 Stamina Vessels, four Spirit Orbs per offering | 10 Heart Containers |

With `vanilla_statues`, the logic counts on the statues' hearts: trading for stamina, or trading hearts back at the
Horned Statue in Hateno, keeps the Master Sword waiting. Only 40 orbs are needed; the others may lie anywhere, a Korok or
a chest that holds nothing needed too. The 66 more items need room: without it, generation stops and says so.
`chest_sanity`, or `korok_sanity` with a lower `korok_local_filler`, gives it.

With `statue_checks`, each trade at a statue is a location, "Goddess Statue - Offering 1" to the number
`statue_offerings` sets (5 by default, up to 30). The statue still takes the orbs and asks for a heart or stamina, then
gives nothing more: the offering sends its item, whatever you chose. Offering k asks for 4×k orbs, and the Temple of
Time's statue for a shrine cleared first, as in the game. Five offerings take the 20 orbs of `containers`; above some
ten, the orbs need locations that may hold progression: `korok_progression` or `chest_progression` gives them.

### DeathLink

With `death_link`, Link's death kills the other DeathLink players of the room, with what killed him ("Player was slain
by a Bokoblin", "Player froze to death"...), and their deaths kill Link, as a lethal blow would: the death animation,
the Game Over screen and the reload of the last save. Mipha's Grace and fairies still save him; the received death is
then spent. It waits for a safe moment: not during a cutscene, a menu or a loading screen.

### Traps

`trap_percentage` turns that share of the filler (arrows, elixirs, weapons, gems and rupees) into traps, drawn by
`trap_weights` (a trap of weight 0 or left out never comes up). A trap strikes when it is received, at a safe moment.

| Trap | What it does |
|---|---|
| Weapon Shatter | The melee weapon in Link's hand is deleted. Empty hands, or the Master Sword: nothing. |
| Blood Moon | The Blood Moon rises at once and the defeated monsters come back. Where the game allows none, the next midnight is the Blood Moon instead. |
| Rupoor | Takes up to 100 rupees: the largest of 100, 50, 20, 10, 5 or 1 the purse holds. |
| Hearts Down | Takes up to two hearts, never the last quarter. |
| Strip Down | Link's weapon, shield, bow and armor go back in the pouch. |
| Cucco Swarm | The angry cuccos rush at Link from every side for 10 s. It can kill. |
| Yiga Ambush | Two Yiga Footsoldiers and a Yiga archer appear around Link and attack. |
| Paranoia | A Guardian takes aim at Link from behind, beeping, and vanishes just before it fires. |
| Downpour | Rain for 2 minutes (the walls get slippery), or a thunderstorm for 90 s (its lightning strikes metal). Nothing in a shrine; a death or a reload ends it. |

A trap given back after loading an older save is spent without effect: a trap is not suffered twice.

## Current limitations

- Only the Wii U version (European, American or Japanese), update v208, in Cemu on Windows.
- A few mods are left out of the Archipelago game: see [Mods](mods_en.md#what-is-left-out).
