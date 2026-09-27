# Development

## Layout

| Folder | Content |
|---|---|
| `botw_world/` | The Archipelago world (packaged as `botw.apworld`), its data, player docs and tests |
| `botw_client/` | The client: Archipelago connection, location tracking, item delivery, journal, HUD indicator |
| `botw_patch/` | Game resource editing: EventFlow, GameData, shops and stalls, HUD layout, size table |
| `tools/` | Command-line tools (seed, pack, play session, packaging) and the builders of the game pack |
| `tools/cemu/` | Access to Cemu's memory, the code cave mailbox and the native requests; RPX reading |
| `native/cemu/` | Sources of the Cemu patches the native builder starts from |
| `data/` | Project data: locations (`locations_master.csv`), item effects (`item_map.json`), GameData flags (`gamedata.json`) |
| `assets/` | The Archipelago item icon and 3D model |
| `players/` | Player options read by `tools/generate_native.py` |
| `tests/` | The project's tests |
| `docs/` | Architecture, development and technical notes |

Local folders, ignored by git: `.build/` (builds, the Archipelago runtime, the Cemu profile, seeds and session logs),
`venv/`, `dist/`.

## Tests

```bat
venv\Scripts\python -m unittest discover -s tests
```

Some tests need local material and are skipped without it: the Archipelago runtime (`tools/prepare_ap_runtime.py`),
the game's update installed in Cemu (`%APPDATA%\Cemu\mlc01\usr\title\0005000e\101c9500\content`), the RPX
(`U-King.rpx` at the project's root) or a built seed. The world's own tests (`botw_world/test/`) follow Archipelago's
conventions; `tests/test_apworld.py` runs them on the runtime, and also imports the packaged `botw.apworld` from its zip.

### Reproducible builds

The game pack is content-addressed, and two tests pin the digests of what the builders produce:
`tests/test_resources_from_source.py` and `tests/test_pack_from_source.py`. A change to the pack's content makes them
fail with the new digest (`new pin: ...`); after checking that the change is the intended one, replace the pin.

Files are hashed byte for byte, so git must not convert their line endings: `.gitattributes` turns conversion off.
Keep each file's line endings when editing it (some tests and launchers depend on CRLF).

## Changing the world

- **Locations**: `data/locations_master.csv` and `botw_world/data/locations.json` carry the same rows; identifiers are
  append-only. A new batch of locations is a new world schema: `SCHEMA_LOCATION_COUNTS` in `botw_client/locations.py`
  and `world_schema` in the world's `fill_slot_data`.
- **Items**: `botw_world/data/items.json` for the pool, `data/item_map.json` for the effect in the game (its delivery
  kinds are listed in `botw_client/items.py`). A delivery is compiled into EventFlow entries by
  `botw_patch/delivery_flow.py`.
- **Options**: `botw_world/options.py`, then `players/BOTW.yaml`.

`tests/test_botw_client.py`, `tests/test_world_schema.py` and the world's tests check that these files agree.

## Packaging

```bat
venv\Scripts\python tools\package_native.py
```

writes `dist\botw.apworld`, as Archipelago's "Build APWorlds" component would: the world folder under the name `botw`,
its `archipelago.json` completed with the container version. The project's `LICENSE` is added to it, since a copy of the
world must carry its license.

## Style

The code follows Archipelago's [style guide](https://github.com/ArchipelagoMW/Archipelago/blob/main/docs/style.md):
120 characters per line, double quotes, type annotations on new code.
