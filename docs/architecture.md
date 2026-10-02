# Architecture

Breath of the Wild has no mod loader and no scripting API. The integration therefore has three parts that work
together: an Archipelago world for generation, a game pack built for each seed, and a client that watches and drives
the running game through Cemu.

```
players/*.yaml ──> Archipelago + botw_world ──> AP_<seed>.zip (multidata + per-slot .apbotw)
                                                        │
       Cemu's update and RPX (profile) ──> tools/play_seed.py ──> game pack of the seed (Cemu graphic pack)
                                                        │
      Cemu (isolated profile, pack) <── memory ──> botw_client <── websocket ──> Archipelago server
```

## The world (`botw_world/`)

A standard Archipelago world, packaged as `botw.apworld` (`tools/package_native.py`). Its data files
(`botw_world/data/items.json`, `locations.json`) follow the project's sources: `data/locations_master.csv` for the
locations, whose identifiers are append-only (a test checks that both agree), and `data/item_map.json` for what each
item does in the game. `generate_output` writes, for each slot, a slot file `.apbotw` (`botw_world/slot_file.py`), an
Archipelago player container that a room on archipelago.gg offers its player to download: the placements of the slot's
locations and the prices drawn for its shop locations. The game pack is built from it.

## The game pack (`tools/build_pack_from_source.py`)

A Cemu graphic pack, built from the player's own game files and the seed. It is content-addressed (its folder is named
after the hash of its content), reproducible, and verified before every use (`verify_pack`). Two builders compose it:

- **Resources** (`tools/build_resources_from_source.py`, library `botw_patch/`): edits of the game's own files.
  - The rewards of the checked locations are taken out where the game gives them (rune terminals, pedestals, Divine
    Beasts...): the check still happens, the vanilla reward does not.
  - EventFlow entries appended to resident flowcharts (`Demo007_1`, `OperationGuide`): one guarded entry per delivery
    step of each item, which the client requests (`botw_patch/delivery_flow.py`).
  - GameData flags of the integration: the session token of the save, the delivery cursor, shop records.
  - Beedle's stocks and the village stalls, with an Archipelago item actor, icon, 3D model and texts in every language
    (`botw_patch/shops.py`, `botw_patch/stalls.py`).
  - The Archipelago logo in the HUD (`botw_patch/hud_layout.py`) and on the loading screen
    (`botw_patch/loading_icon.py`), and the "Archipelago" key item (`botw_patch/status_item.py`).
  - The DeathLink entry (`botw_patch/death_link.py`), and the traps' (`botw_patch/traps.py`).
  - The resource size table, updated for every changed file.
- **Native code** (`tools/build_native_from_source.py`): Cemu patches (`patch_apInject.asm` and companions) assembled
  from `native/cemu/` and a chain of transformations (`tools/build_*.py`). They install a code cave with a mailbox the
  client writes to, and a per-frame hook that runs the client's requests on the game's own thread: requesting an
  EventFlow entry, showing a line in the tip frame, selecting a rune. The pack refuses any RPX other than the EUR v208
  one it was built for (SHA-256).

The pack is bound to its seed: a token derived from the seed, team, slot and data package is written into the pack
and, on the first connection, into the save (`APBindSession`). A save bound to another seed is refused. The world
writes the data package's checksum into the slot file (`BotwWorld.data_package_checksum`, the same as the client's,
`botw_client/session.py`), and the team is always 0: `tools/play_seed.py` binds a pack from the seed's zip or from the
slot file alone, without reaching any server.

## The client (`botw_client/`)

`BotwClientRuntime` (`botw_client/runtime.py`) connects to the Archipelago server (`protocol.py`) and to Cemu's memory
(`game.py`, with the memory layer of `tools/cemu/`):

- **Checks**: the locations are GameData flags of the game (shrine cleared, tower activated...). They are read from
  the live GameData table at 5 Hz (`locations.py`) and sent to the server. Being saved by the game, a check done while
  disconnected is sent at the next connection.
- **Items**: each received item is delivered by requesting its EventFlow entry (`native_delivery.py`). The entry
  performs the game's own presentation (item window, rune download screen), then advances `APReceivedCursor`, saved in
  the game's save, under `SaveProhibition`: an item is given exactly once per save, and reloading an older save gives
  back, quietly, what it lost. A delivery is requested only when the game is in a safe state (no menu, event, cutscene
  or loading).
- **Presentation**: the Archipelago journal (`tip_channel.py`) shows server messages in the game's tip frame; an
  Archipelago window (`presentation_session.py`) summarizes items given back after a reload; the HUD logo shows the
  connection status (`hud_indicator.py`).
- **Shops**: when a shop list is open, the client hints the Archipelago items it shows (`shop_state.py`).
- **DeathLink**: Link's death (`CurrentHart` at 0) is sent to the room; a received death is announced in the journal,
  then requests the pack's entry `OperationGuide<APDeathLink>`, the game's own damage action with a lethal value
  ([death_link.md](reference/death_link.md)).
- **Traps**: a received trap item is delivered like any other, by a guarded entry that commits, then calls the trap's
  own entry as a sub-flow; the journal says what it did. Cucco Swarm has no entry of its own: the client plays it once
  it has seen the commit, through the game's actor creation (`cucco_swarm.py`). Given back by a reload, a trap is spent
  without effect ([traps.md](reference/traps.md)).

## The player's Cemu (`tools/cemu_install.py`, `tools/cemu_profile.py`)

Cemu's user folder (the `portable` folder next to `Cemu.exe`, else `%APPDATA%\Cemu`) holds its settings and the list
of the games it found; the update and the DLC are installed in its `mlc01` folder. `cemu_install` finds the three
titles of the European version there and checks them: update v208 as a folder, its `U-King.rpx` the expected
executable, DLC 3.0. `cemu_profile` copies the update, the DLC, the saves and the accounts into an isolated profile
in the data folder, and records where the base game is; packs are built from that copy of the update, the one the
game runs from.

## The launcher (`tools/launcher.py`, `BOTW Archipelago.cmd`)

The one command a player runs: the first time, it makes the Cemu profile from `Cemu.exe`; then it picks a prepared
seed or prepares a new one from a slot file or a seed's zip (`tools/play_seed.py`), asks for the room, and starts the
play session.

## The play session (`tools/play_session.py`)

Runs Cemu on the isolated profile of `tools/cemu_profile.py` with the seed's pack as its only graphic pack, and the
client, until Cemu closes. The client joins the room hosting the seed (`--connect`, archipelago.gg for instance), or
the Archipelago server of the seed, run in process from its zip (its state saved next to the seed; `--host` opens it
to the network for the other players). Each session writes its logs to `play-seeds/<seed>/sessions/` in the data
folder (see [Development](development.md#local-folders)).

## Technical notes

The mechanisms found in the game (EventFlow requests, the tip frame, the HUD, shops and stalls, the rune download
screen...) are described in [docs/reference](reference/README.md).
