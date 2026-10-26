# PopTracker Guide

[PopTracker](https://github.com/black-sliver/PopTracker) shows a map of Hyrule with every location of your seed,
colored by what your items let you reach. It connects to the Archipelago room by itself: the items you receive and
the locations you check appear as you play, with nothing to click.

There is no pack to download: the launcher builds it from your own copy of the game and installs it for you.

## Setting it up

1. **Install PopTracker**, version 0.26.2 or later, from its
   [releases page](https://github.com/black-sliver/PopTracker/releases) (on Windows, the `win64` zip: unzip it
   anywhere).
2. **Run PopTracker once**, then close it. This creates its packs folder, `C:\Users\<you>\PopTracker\packs` (or
   `Documents\PopTracker\packs`). If neither exists after that, create `C:\Users\<you>\PopTracker\packs` yourself.
3. **Start a session with the BOTW Archipelago launcher**, as the [setup guide](setup_en.md#playing) says. Before
   Cemu starts, the launcher builds the pack and copies it into PopTracker's packs folder. Its window says so:

       PopTracker pack installed: C:\Users\<you>\PopTracker\packs\botw_archipelago.zip

   The first build takes a few seconds; afterwards the pack is only built again when something it is made of
   changed (a new version of BOTW Archipelago, new icons).

You do this once. From then on, every session keeps the pack up to date.

## Connecting to the room

1. Open PopTracker and click **Load** (the folder icon at the top left).
2. Choose **Breath of the Wild Archipelago**, variant **Map tracker**.
3. Click **AP** in the top bar and enter:
   - the room's address, as the room's page shows it (`archipelago.gg:38281`);
   - your slot name, as in your YAML;
   - the room's password, or nothing.

The tracker then fills in by itself: the items you already have, the locations already checked, and the seed's
options (which locations exist, whether region maps are needed, what Ganon asks for). PopTracker remembers the pack
and the room: next time, load the pack and click **AP** again.

## Reading the map

Each square is a place on the map; hover it to see its locations, click it to see them in a list.

| Color | Meaning |
|---|---|
| Green | Reachable with your items |
| Red | Not reachable yet |
| Yellow | Possible, but out of logic (a region's map is missing) |
| Grey | Already checked |

A square holding several locations (a stable's two Beedle items, a plateau shrine and its terminal) can show more
than one color. Shops and stalls only appear when your seed has them. Once your slot has reached its goal and is
released, every location is checked and the whole map turns grey.

## The items panel

The panel next to the map shows the items that matter for the logic (runes, Paraglider, armor, Divine Beasts
freed, shrines cleared...). A bright icon is an item you have; a numbered one is a progressive item (the number is
how many you have). The region maps have their own two rows.

Everything is updated from the room; you never need to click anything. Without a connection, you can still mark
items and locations by hand with the mouse.

## Icons

The map and part of the icons (hearts, stamina, Divine Beasts, shrines...) are drawn from your own game. The
launcher downloads the rest once, from the `tracker-icons` release of this project. Without an internet connection,
those items show a text label instead, which works just as well.

You can also use your own icons: put PNG files named after the items (`Paraglider.png`, `Zora Armor.png`...; subfolders are fine) in
`%LOCALAPPDATA%\BOTW Archipelago\poptracker\icons`. They are used from the next session on.

## Troubleshooting

- **The pack is not in PopTracker's list.** The launcher only installs it when PopTracker's packs folder exists:
  check `C:\Users\<you>\PopTracker\packs` (step 2 above), then start a session again. You can also drag
  `%LOCALAPPDATA%\BOTW Archipelago\poptracker\botw_archipelago.zip` onto the PopTracker window: it installs it.
- **"PopTracker pack not built: ... is in use".** PopTracker had the pack loaded, and Windows does not let it be
  replaced. Close PopTracker before starting the session (or load another pack), then start the session again.
- **The map is a plain grid.** Your game is a `.wud` or `.wua` file: the map is drawn from a game installed as a
  folder (with `code`, `content` and `meta`). The tracker works all the same.
- **Nothing updates.** Click **AP** again and check the address and the slot name. The room's address changes when it restarts on archipelago.gg: take the new one from the room's page.
- **A location is red but you could get it.** The tracker follows the world's logic, which can be stricter than
  the game. You can do it anyway: it is checked all the same.
