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
- A source checkout of [Archipelago](https://github.com/ArchipelagoMW/Archipelago) **0.6.7**.

Other versions of the game (US, JP, Switch) are not supported: the native code of the integration is built for this
exact executable.

## Installation

From the folder of the project:

```bat
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python tools\prepare_ap_runtime.py --source <Archipelago 0.6.7 checkout>
venv\Scripts\python tools\cemu_profile.py --cemu <path to Cemu.exe>
```

- `prepare_ap_runtime.py` copies the Archipelago core and this world into `.build\ap-runtime`, used for generation
  and for the local server.
- `cemu_profile.py` finds the game, its update and the DLC in your Cemu installation and checks their versions, then
  copies Cemu, the update, the DLC and the game's saves into an isolated profile, `.build\cemu-validation` (about
  5 GB). Your Cemu installation is never modified. When it is not found, name Cemu's user folder, the one holding
  `settings.xml`, with `--user-data`. `tools\cemu_install.py` shows what is found, without copying anything.

## Generating a seed

**Alone**: edit `players\BOTW.yaml` (player name, goal, shop options, DeathLink, traps), then:

```bat
venv\Scripts\python tools\generate_native.py
```

The seed is written to `.build\native-seeds\AP_<seed>.zip`.

**With other players**: the person who generates needs every player's YAML file, and the worlds of their games. For
Breath of the Wild, that is `botw.apworld` (`venv\Scripts\python tools\package_native.py` writes it to `dist\`),
installed in Archipelago's `custom_worlds` folder. Generate with Archipelago as usual; the seed's zip holds, for each
Breath of the Wild player, a slot file `AP_<seed>_P<n>_<name>.apbotw.json`. To host the game on
[archipelago.gg](https://archipelago.gg), upload that zip on its "Host Game" page: it then gives the room's address,
`archipelago.gg:<port>`.

## Building the game pack

```bat
venv\Scripts\python tools\play_seed.py <seed file>
```

- The seed file is the seed's zip, or your own slot file (`.apbotw.json`, taken from the zip), which is all you need
  to play in a room hosted elsewhere. When the zip holds several Breath of the Wild players, name yours with
  `--slot <name>`.
- The pack is built from the update copied into the isolated profile.

The tool checks the seed, keeps a copy of the file in `.build\play-seeds\<seed>\`, builds the pack bound to your slot
of this seed and selects it.

## Playing

In a room hosted elsewhere, archipelago.gg for instance:

```bat
Play.cmd --seed <seed> --connect archipelago.gg:<port>
```

Add `--password <password>` if the room has one. On a server of your own, from the seed's zip:

```bat
Play.cmd --seed <seed>
```

This starts the Archipelago server on this computer, port 38281, keeping its state next to the seed so that progress
carries over between sessions. With `--host`, the server listens on the network too: the other players connect to
your computer's address, port 38281 (over the Internet, that port must be forwarded to your computer).

In every case Cemu starts on its isolated profile with only the seed's pack, then the client. Start a **new game**
for a new seed: saves are bound to the seed they were started with. Play normally; close Cemu to end the session.

Lines typed in the console go to the server as commands (`/hint`, `/players`, `/status`...; sent to a remote room as
`!hint`, `!players`...) or as chat. The client adds its own commands:

| Command                | What it does                                                 |
|------------------------|--------------------------------------------------------------|
| `/ap-tip <text>`       | show a line in the in-game Archipelago journal (test)        |
| `/ap-disconnect [s]`   | simulate a server disconnection for `s` seconds              |
| `/ap-evt [n\|reset]`    | list the game's last event requests (diagnostic)             |
| `/ap-deathlink [cause]` | kill Link as a received DeathLink would (test, sent to nobody) |

## Troubleshooting

Each session writes its logs to `.build\play-seeds\<seed>\sessions\<date>\`: the client's log, Cemu's log and a
summary. Include that folder when reporting a problem.
