# Breath of the Wild Multiworld Setup Guide

This guide sets up the tools of the BOTW Archipelago project on Windows: generating a seed, building the game pack of
that seed, and playing it in Cemu with the Archipelago client, alone or with other players, on a room of
archipelago.gg or on your own server. The commands run from the project's folder.

## Requirements

- Windows 10 or 11.
- [Cemu](https://cemu.info/) 2.x, with **The Legend of Zelda: Breath of the Wild, Wii U, European version (EUR)**,
  from your own console: the game in Cemu's game list, its update **v208** (1.5.0) and the DLC installed in Cemu
  (File > Install game title, update or DLC). Start the game once in Cemu.
- Python 3.12.
- To generate or host a seed: [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) **0.6.7**. Joining a
  room hosted by someone else needs only your slot file.

Other versions of the game (US, JP, Switch) are not supported: the native code of the integration is built for this
exact executable.

## Installation

From the folder of the project:

```bat
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## Generating a seed

A seed is generated with [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) **0.6.7**, as for any
game, by the person who hosts it (alone, that is you):

1. Put `botw.apworld` in Archipelago's `custom_worlds` folder (`venv\Scripts\python tools\package_native.py` writes it
   to `dist\`).
2. Put every player's YAML file in Archipelago's `Players` folder. For Breath of the Wild, start from
   `players\BOTW.yaml` (player name, goal, shop options, DeathLink, traps), or from the template the Archipelago
   Launcher writes ("Generate Template Options").
3. Run "Generate" in the Archipelago Launcher. The seed's zip, in Archipelago's `output` folder, holds a slot file
   `AP_<seed>_P<n>_<name>.apbotw.json` for each Breath of the Wild player.

To host the seed on [archipelago.gg](https://archipelago.gg), upload that zip on its "Host Game" page: the room's page
gives its address, `archipelago.gg:<port>`, and each player's slot file to download. To host it on your computer,
open the zip with "Archipelago Server" in the Archipelago Launcher; the players connect to `localhost:38281` (the
others to your computer's address, port 38281, forwarded to it over the Internet).

From a source checkout of Archipelago 0.6.7, `venv\Scripts\python tools\prepare_ap_runtime.py --source <checkout>`
copies its core and this world into `.build\ap-runtime`; `venv\Scripts\python tools\generate_native.py` then
generates from the YAML files of `players\` into `.build\native-seeds\`, and the launcher can host a seed's zip on
this computer.

## Playing

Start `BOTW Archipelago.cmd`, or drop your slot file (`.apbotw.json`) or the seed's zip on it:

1. **The first time**, it asks where `Cemu.exe` is. It finds Breath of the Wild, its update and the DLC in that
   installation and checks their versions, then copies Cemu, the update, the DLC and your saves into an isolated
   profile (about 5 GB). Your Cemu installation is never modified.
2. **The seed**: a seed already prepared, or a new one, from your slot file (`.apbotw.json`, downloaded from the room's
   page or taken from the seed's zip) or the seed's zip. A new seed's game pack is built, in about a minute.
3. **The room**: its address, as the room's page shows it (`archipelago.gg:<port>`), remembered for the seed, and its
   password if it has one. A seed prepared from its zip can also be hosted on this computer: type `local`.

Cemu then starts on its isolated profile with only the seed's pack, then the client. Start a **new game**
for a new seed: saves are bound to the seed they were started with. Play normally; close Cemu to end the session.

Lines typed in the console go to the server as commands (`/hint`, `/players`, `/status`...; sent to a remote room as
`!hint`, `!players`...) or as chat. The client adds its own commands:

| Command                | What it does                                                 |
|------------------------|--------------------------------------------------------------|
| `/ap-tip <text>`       | show a line in the in-game Archipelago journal (test)        |
| `/ap-disconnect [s]`   | simulate a server disconnection for `s` seconds              |
| `/ap-evt [n\|reset]`    | list the game's last event requests (diagnostic)             |
| `/ap-deathlink [cause]` | kill Link as a received DeathLink would (test, sent to nobody) |

### The command-line tools

The launcher runs these tools, which can also be used directly:

- `venv\Scripts\python tools\cemu_profile.py --cemu <path to Cemu.exe>` makes the isolated profile, in
  `.build\cemu-validation`. When Cemu's user folder (the one holding `settings.xml`) is not found, name it with
  `--user-data`. `tools\cemu_install.py` shows what is found, without copying anything.
- `venv\Scripts\python tools\play_seed.py <seed file>` prepares a seed: it checks the seed, keeps a copy of the file
  in `.build\play-seeds\<seed>\`, builds the pack bound to your slot from the update copied into the profile and
  selects it. When the zip holds several Breath of the Wild players, name yours with `--slot <name>`.
- `Play.cmd --seed <seed> --connect archipelago.gg:<port> [--password <password>]` plays in a room hosted elsewhere.
  `Play.cmd --seed <seed>` hosts the seed's zip on this computer, port 38281, keeping the server's state next to the
  seed so that progress carries over between sessions; with `--host`, the server listens on the network too: the
  other players connect to your computer's address, port 38281 (over the Internet, that port must be forwarded to
  your computer).

## Troubleshooting

Each session writes its logs to `.build\play-seeds\<seed>\sessions\<date>\`: the client's log, Cemu's log and a
summary. Include that folder when reporting a problem.
