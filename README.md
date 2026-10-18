# Breath of the Wild for Archipelago

An [Archipelago](https://archipelago.gg) integration of **The Legend of Zelda: Breath of the Wild**, Wii U version,
played in the [Cemu](https://cemu.info/) emulator.

Shrines, towers, Great Fairies, Divine Beasts, the rune terminals, the Master Sword and, optionally, Beedle's shops and
the village stalls become locations of the multiworld. The paraglider, the runes, the champions' abilities, armor,
heart containers and stamina vessels are shuffled into it, and arrive in your game while you play, presented by the
game itself.

**Status: version 0.1, in testing.** Solo seeds and multiworlds with other games, hosted on archipelago.gg or on
your own server.

## Features

- **212 locations**: 120 shrines, 15 towers, 4 rune terminals, 4 Great Fairies, 4 Divine Beasts and their heart
  containers, the Master Sword, and up to 60 shop and stall items.
- **Items delivered by the game itself**: the game's item window, the Sheikah Slate's download screen for a rune, the
  champions' ability windows. An item is given exactly once per save, even across reloads and disconnections.
- **Reload-safe**: loading an older save gives back what it lost, quietly, then lists it in one window.
- **Shops and stalls**: Archipelago items for sale at Beedle's 16 shops and on 14 village stalls, with their own icon,
  3D model, names and descriptions.
- **Archipelago journal**: the server's messages (items sent and received, hints) in the game's tip frame.
- **Connection status**: an Archipelago logo in the HUD, in color when connected, and an "Archipelago" main quest
  in the Adventure Log with the seed, the slot and the goal, completed once the goal is reached.
- **Goals**: defeat Ganon, free the four Divine Beasts, or clear a number of shrines.
- **Sealed sanctum**: Ganon's sanctum opens only once the seed's requirements are met (Divine Beasts, shrines,
  the Master Sword, the runes; Easy, Medium and Hard presets), and the journal says what is missing.
- **Logic**: each shrine asks only for the runes its trial needs; the burning zones of Eldin, Gerudo Town and the
  waterfalls of Vah Ruta ask for their armor.
- **Region maps**: each region's map is an item, revealed with the game's own animation; a region is in the logic
  once its map is received (an option), and the trackers show the rest as possible but out of logic.
- **Checks never lost**: locations are the game's own saved flags, sent at the next connection when done offline.
- **DeathLink** (option): when Link dies, the other DeathLink players die; when one of them dies, Link dies, as he
  would of a lethal blow (Mipha's Grace and fairies still save him).
- **PopTracker**: a map tracker with the world's logic, which follows the room by itself; the launcher builds it
  from your game and installs it when PopTracker is there.
- **Universal Tracker**: supported without a YAML, and its `/explain` says what a location still asks for.
- **Weapons**: 83 of the game's weapons, bows and shields in the filler, the weaker first and the amiibo's
  treasures last (option); with a full pouch, a weapon falls at Link's feet.
- **Traps** (option): a share of the filler turns into Weapon Shatter, Blood Moon, Rupoor, Hearts Down, Strip
  Down, Cucco Swarm, Yiga Ambush, Paranoia and Downpour, which strike when received. The cuccos, the Yiga and the storm's
  lightning can kill, and a trap given back by a reload is spent, not suffered twice.

## Requirements

- Windows, Cemu 2.x, Breath of the Wild **Wii U, European (EUR), American (USA) or Japanese (JPN) version, update
  v208 (1.5.0) and DLC**, from your own console, installed in Cemu: the native code of the integration is built for
  this exact executable, the same in the three versions.
- To generate or host a seed, [Archipelago 0.6.7](https://github.com/ArchipelagoMW/Archipelago/releases) with this
  world, `botw.apworld`.

No game file is part of this repository: the game pack of a seed is built from your own copy of the game.

## Getting started

Download the [latest release](https://github.com/EIdras/BOTW-Archipelago/releases):
`BOTW-Archipelago-<version>-Windows.zip` for the players, `botw.apworld` for the host. The [setup guide](botw_world/docs/setup_en.md)
([en français](botw_world/docs/setup_fr.md)) covers installing, playing, hosting and updating. In short:

1. The host generates the seed with Archipelago and `botw.apworld`, then hosts it, on archipelago.gg for instance.
2. Each Breath of the Wild player unzips the release and starts `BOTW Archipelago.cmd` with their slot file
   (`.apbotw`, on the room's page). The launcher asks for `Cemu.exe` the first time, builds the seed's game pack,
   asks for the room's address and plays. Nothing else to install: the release brings its own Python.

What the world does, its locations, items, goal and logic: [game page](botw_world/docs/en_Breath%20of%20the%20Wild.md).
The French names of every location and item, as the French game shows them: [noms en français](botw_world/docs/names_fr.md).

## Limitations

- Only the Wii U version, update v208, in Cemu on Windows. The texts the integration adds are in English, but for
  the sealed sanctum's line; a DeathLink sent from the Japanese version names no killer.
- The game pack is built for one seed: Archipelago's website cannot generate a seed with this world, which is
  generated with Archipelago on a computer (then hosted anywhere).

## Documentation

- [Architecture](docs/architecture.md): the world, the game pack, the client and how they work together.
- [Development](docs/development.md): running from source, layout, tests, reproducible builds, changing the world,
  releases.
- [Technical notes](docs/reference/README.md): what was measured in the game, and why.

## Credits

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago), the multiworld randomizer this integrates with.
- [oead](https://github.com/zeldamods/oead), [evfl](https://github.com/zeldamods/evfl) and
  [rstb](https://github.com/zeldamods/rstb) by leoetlino and the zeldamods community, for BOTW's file formats.
- [botw-tools](https://github.com/MrCheeze/botw-tools) by MrCheeze, whose GameData flag list served to map the locations.
- The [zeldaret/botw](https://github.com/zeldaret/botw) decompilation, as a reference for the engine.
- [Zelda Wiki](https://zeldawiki.wiki/), whose shrine and quest walkthroughs served to check the logic of every
  location.
- [Switch Toolbox](https://github.com/KillzXGaming/Switch-Toolbox), used to author the Archipelago item's 3D model.

## License

This project is free software, under the [GNU General Public License, version 3 or later](LICENSE): you may use, study,
share and modify it, and any version you distribute stays under the same license, with its source.

The license covers the project's own work. The Legend of Zelda: Breath of the Wild and its assets are © Nintendo; this
project is not affiliated with or endorsed by Nintendo. The icons attached to the `tracker-icons` release, which
the launcher downloads for the PopTracker pack, are Nintendo's images: they are not part of the repository and
not under its license.
