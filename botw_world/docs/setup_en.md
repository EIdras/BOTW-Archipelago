# Breath of the Wild Multiworld Setup Guide

This guide sets up the tools of the BOTW Archipelago project on Windows: generating a seed, building the game pack of
that seed, and playing it in Cemu with the Archipelago client. The commands run from the project's folder.

## Requirements

- Windows 10 or 11.
- [Cemu](https://cemu.info/) 2.x, with **The Legend of Zelda: Breath of the Wild, Wii U, European version (EUR)**,
  update **v208** (1.5.0) and the DLC installed, from your own console.
- The game's `code/U-King.rpx` of that version, dumped from your own console. The pack builder checks its SHA-256.
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
venv\Scripts\python tools\cemu_profile.py --cemu <path to Cemu.exe> --user-data <Cemu user folder>
copy botw_client.example.json botw_client.json
```

- `prepare_ap_runtime.py` copies the Archipelago core and this world into `.build\ap-runtime`, used for generation
  and for the local server.
- `cemu_profile.py` copies Cemu, the game's update, DLC and saves into an isolated profile, `.build\cemu-validation`.
  Your Cemu installation is never modified. The Cemu user folder is the one holding `settings.xml` and `mlc01`.
- In `botw_client.json`, set `game` to the path of the game's `U-King.rpx`.

## Generating a seed

Edit `players\BOTW.yaml` (player name, goal, shop options), then:

```bat
venv\Scripts\python tools\generate_native.py
```

The multiworld archive is written to `.build\native-seeds\AP_<seed>.zip`. Only single-player Breath of the Wild seeds
are supported for now.

## Building the game pack

```bat
venv\Scripts\python tools\play_seed.py .build\native-seeds\AP_<seed>.zip --content <update content folder> --rpx <U-King.rpx>
```

The update content folder is the `content` folder of the installed update, usually
`%APPDATA%\Cemu\mlc01\usr\title\0005000e\101c9500\content`. The tool checks the archive, keeps a copy of it in
`.build\play-seeds\<seed>\`, reads the session identity from a local server, builds the pack bound to this seed and
selects it.

## Playing

```bat
Play.cmd --seed <seed>
```

This starts the Archipelago server on `127.0.0.1:38281`, Cemu on its isolated profile with only the seed's pack, and
the client. Start a **new game** for a new seed: saves are bound to the seed they were started with. Play normally;
close Cemu to end the session. The server keeps its state next to the seed, so progress carries over between sessions.

Lines typed in the console go to the server as commands (`/hint`, `/players`, `/status`...) or as chat. The client
adds its own commands:

| Command                | What it does                                                 |
|------------------------|--------------------------------------------------------------|
| `/ap-tip <text>`       | show a line in the in-game Archipelago journal (test)        |
| `/ap-disconnect [s]`   | simulate a server disconnection for `s` seconds              |
| `/ap-evt [n\|reset]`    | list the game's last event requests (diagnostic)             |

## Troubleshooting

Each session writes its logs to `.build\play-seeds\<seed>\sessions\<date>\`: the client's log, Cemu's log and a
summary. Include that folder when reporting a problem.
