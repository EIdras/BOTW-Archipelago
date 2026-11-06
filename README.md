# Breath of the Wild for Archipelago

An [Archipelago](https://archipelago.gg) integration of **The Legend of Zelda: Breath of the Wild**, Wii U version,
played in the [Cemu](https://cemu.info/) emulator.

<!-- ![An Archipelago item, received in Breath of the Wild](docs/images/item-received.jpg) -->

Shrines, towers, Great Fairies and Divine Beasts become checks of the multiworld. The Paraglider, the runes, the
champions' abilities, armor and heart containers are shuffled across every game, and arrive in yours while you play,
presented by the game itself.

**Status: in testing.** Solo seeds and multiworlds with other games, hosted on archipelago.gg or on your own server.

## Highlights

- **219 locations**: the 120 shrines, the 15 towers, the Great Fairies, the Divine Beasts, the Master Sword, Purah's
  rune upgrades, the Champions' Ballad and, optionally, Beedle's shops and the village stalls.
- **Delivered by the game**: the item window, the Sheikah Slate's rune download, the champions' ability windows.
  Each item is given once per save, through reloads and disconnections.
- **An Archipelago journal in the game**: items sent and received, hints, all in the game's own tip frame.
- **Region maps as keys**, and optionally a world that opens region by region from the Great Plateau.
- **A sealed sanctum**: Ganon waits until the seed's requirements are met.
- **DeathLink and nine traps**, from a Blood Moon to a Yiga ambush.
- **Trackers**: a PopTracker map pack built from your game, and Universal Tracker.
- **Your mods keep working**: FPS++, graphics packs, UKMM mods.

## What you need

- Windows and [Cemu](https://cemu.info/) 2.x.
- Breath of the Wild for **Wii U** (European, American or Japanese), with **update v208 and the DLC**, from your own
  console. The Switch version is not supported.
- To generate a seed: [Archipelago 0.6.7](https://github.com/ArchipelagoMW/Archipelago/releases).

No game file is part of this project: the game pack of a seed is built from your own copy of the game.

## Quick start

1. Download `BOTW-Archipelago-<version>-Windows.zip` from the
   [latest release](https://github.com/EIdras/BOTW-Archipelago/releases), and unzip it.
2. Get your slot file (`.apbotw`) from the room's page.
3. Start `BOTW Archipelago.cmd`: it finds your Cemu, builds your seed's game pack, connects to the room and starts
   the game.

## Documentation

| I want to… | Read |
|---|---|
| Install and play | [Setup guide](botw_world/docs/setup_en.md) ([démarrage rapide en français](botw_world/docs/setup_fr.md)) |
| See what Archipelago changes in the game | [In the game](botw_world/docs/ingame_en.md) |
| Understand the locations, items, logic and options | [Game page and options](botw_world/docs/en_Breath%20of%20the%20Wild.md) |
| Host a seed | [Hosting](botw_world/docs/hosting_en.md) |
| Follow my game on a map | [Trackers](botw_world/docs/poptracker_en.md) |
| Play with my mods and graphic packs | [Mods](botw_world/docs/mods_en.md) |
| Fix a problem or report a bug | [Troubleshooting](botw_world/docs/troubleshooting_en.md) |
| Read the French names of locations and items | [Noms en français](botw_world/docs/names_fr.md) |

## Limitations

- Wii U version only, update v208, in Cemu on Windows.
- The texts the integration adds to the game are in English.
- A seed is generated with Archipelago on a computer (archipelago.gg's website cannot generate it), then hosted
  anywhere, archipelago.gg included.
- A few mods cannot run with it: see [Mods](botw_world/docs/mods_en.md).

## Contributing

- [Architecture](docs/architecture.md): the world, the game pack, the client and how they work together.
- [Development](docs/development.md): running from source, layout, tests, reproducible builds, releases.
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
project is not affiliated with or endorsed by Nintendo. The icons attached to the `tracker-icons` release, which the
launcher downloads for the PopTracker pack, are Nintendo's images: they are not part of the repository and not under
its license.
