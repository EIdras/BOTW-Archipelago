# Breath of the Wild Multiworld Setup Guide

This guide gets you playing The Legend of Zelda: Breath of the Wild in an Archipelago multiworld, on Windows, in the
Cemu emulator: installing, joining a room, and, for the person who hosts it, generating the seed.

## What you need

- Windows 10 or 11.
- [Cemu](https://cemu.info/) 2.x, with **Breath of the Wild, Wii U, European (EUR), American (USA) or Japanese (JPN)
  version**, from your own console:
  - the game in Cemu's game list;
  - its update **v208** (1.5.0) and the **DLC** installed in Cemu (File > Install game title, update or DLC).

  Start the game once in Cemu. The Switch version is not supported: the integration is built for this exact
  executable. With several versions in Cemu, the launcher plays the European one, else the American one.
- About 5 GB of free disk space, and 140 MB more for each seed.
- The room the game is hosted in: its page on archipelago.gg offers your **slot file** (`.apbotw`, "Download Patch
  File..." next to your name), and shows the **address of the room**.

## Installing

1. Download `BOTW-Archipelago-<version>-Windows.zip` from the
   [releases](https://github.com/EIdras/BOTW-Archipelago/releases) of the project, in the release's Assets (not
   "Source code", which GitHub adds and which has no Python).
2. Right-click the zip > Properties, tick **Unblock**, OK. Otherwise Windows asks to confirm each program the first
   time it runs.
3. Unzip it where you like, your Documents for instance (not in Program Files). Nothing else to install: it brings its
   own Python.

## Playing

Start `BOTW Archipelago.cmd` (or drop your slot file on it). If Windows says it protected your PC, choose
"More info", then "Run anyway".

1. **The first time**, a window asks where `Cemu.exe` is. The launcher finds Breath of the Wild, its update and the DLC
   in that installation and checks them, then copies Cemu, the update, the DLC and your saves into a profile of its
   own (about 5 GB). Your Cemu installation is never modified.
2. **The seed**: choose your slot file. Its game pack is built, in about a minute. The next times, the launcher lists
   the seeds already prepared, the last played first.
3. **The room**: its address, as the room's page shows it (`archipelago.gg:38281`), is already filled in when your
   slot file comes from that page: press Enter, then type the room's password, or Enter if it has none. The address
   is remembered for the seed.

Cemu starts with the seed's game pack, then the Archipelago client, in the launcher's window. **Start a new game** for
a new seed: a save is bound to the seed it was started with. Play normally: your items arrive in the game, the
Archipelago journal (top right of the screen) shows what is sent and received, and the Archipelago logo in the HUD
is in color while you are connected. Close Cemu to end the session, and leave the launcher's window open until then.

**Map tracker**: with [PopTracker](https://github.com/black-sliver/PopTracker) installed (run once, so that its
`PopTracker/packs` folder exists), the launcher installs the "Breath of the Wild Archipelago" pack before the
session. In PopTracker, load the pack, click "AP" and enter the room's address, your slot name and the password:
the map shows every location, colored by what your items allow, and checks them as you go. The map and part of
the icons come from your own game; for the others (armor, runes...), you may put the game's icons, PNG files
named after the items, in `%LOCALAPPDATA%\BOTW Archipelago\poptracker\icons`: they are used at the next
session.

**Universal Tracker**: with [Universal Tracker](https://github.com/FarisTheAncient/Archipelago/releases) and
`botw.apworld` in your Archipelago installation, connect it to the room with your slot name: it lists what your
items let you reach, and `/explain <location>` says what a location still asks for. It needs no YAML: it reads the
seed's options from the room. A seed generated before version 0.2.0 with stall items does not say which stalls it
drew: the tracker may then list other stalls than the seed's.

Lines typed in the launcher's window go to the room as chat, or as commands: `/hint <item>`, `/players`, `/status`...
(sent to the room as `!hint`, `!players`...). The client adds a few, for tests and bug reports:

| Command                 | What it does                                                   |
|-------------------------|----------------------------------------------------------------|
| `/ap-tip <text>`        | show a line in the in-game Archipelago journal                 |
| `/ap-disconnect [s]`    | simulate a server disconnection for `s` seconds                |
| `/ap-evt [n\|reset]`     | list the game's last event requests                            |
| `/ap-deathlink [cause]` | kill Link as a received DeathLink would (sent to nobody)       |

## Generating and hosting a seed

The person who hosts the game generates the seed with [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases)
**0.6.7**, as for any game:

1. Put `botw.apworld`, from the same [releases](https://github.com/EIdras/BOTW-Archipelago/releases), in
   Archipelago's `custom_worlds` folder.
2. Put every player's YAML file in Archipelago's `Players` folder. For Breath of the Wild, start from
   `players\BOTW.yaml` in the release (player name, goal, shop options, DeathLink, traps), or from the template the
   Archipelago Launcher writes ("Generate Template Options").
3. Run "Generate" in the Archipelago Launcher. The seed's zip, in Archipelago's `output` folder, holds a slot file
   `AP_<seed>_P<n>_<name>.apbotw` for each Breath of the Wild player.

To host the seed on [archipelago.gg](https://archipelago.gg), upload that zip on its "Host Game" page: the room's page
gives its address, `archipelago.gg:<port>`, and each player's slot file to download. To host it on your own computer,
open the zip with "Archipelago Server" in the Archipelago Launcher; you connect to `localhost:38281`, the other
players to your computer's address, port 38281 (over the Internet, that port must be forwarded to your computer).

Playing alone is the same: generate a seed with your YAML alone, host it, and join it.

## Updating

Download the new release and unzip it, in place of the old one or anywhere else. Your profile, your seeds and their
saves are kept in `%LOCALAPPDATA%\BOTW Archipelago`, whatever folder the release is in. The first time you play a
seed with the new version, the launcher builds its game pack again.

A release plays the seeds of earlier versions. If a seed needs a newer one, the launcher says which: download it,
and give the host the matching `botw.apworld` for the next seeds.

## Uninstalling

Delete the release's folder, and `%LOCALAPPDATA%\BOTW Archipelago`: the profile, with the saves of your Archipelago
games, and the seeds. Your Cemu installation was never modified.

## Troubleshooting

- **The launcher refuses your Cemu**: its message says what is missing (another version of the game, the update or
  the DLC not installed, a game listed by Cemu that moved...). Fix it in Cemu, start the game once there, and launch
  again.
- **"Close Cemu before preparing a session"**: the launcher starts Cemu itself; close yours first.
- **The game does not react to your controller**: the profile copied no controller setting from your Cemu. In the
  game's window, open Cemu's Options > Input settings and choose your controller for player 1; the profile keeps it.
- **Each session writes its logs** to `%LOCALAPPDATA%\BOTW Archipelago\play-seeds\<seed>\sessions\<date>\`: the
  client's log, Cemu's log and a summary. Attach that folder when you
  [report a problem](https://github.com/EIdras/BOTW-Archipelago/issues).

Running from the source code instead of a release: see
[development](https://github.com/EIdras/BOTW-Archipelago/blob/master/docs/development.md#running-from-source).
