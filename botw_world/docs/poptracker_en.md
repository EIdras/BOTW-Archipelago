# PopTracker Guide

[PopTracker](https://github.com/black-sliver/PopTracker) shows a map of Hyrule with every location of your seed,
colored by what your items let you reach. It connects to the Archipelago room by itself: the items you receive and
the locations you check appear as you play, with nothing to click.

There is no pack to download: the launcher builds it from your own copy of the game, in the release's folder, and
you install it in PopTracker yourself.

## Setting it up

1. **Install PopTracker**, version 0.26.2 or later, from its
   [releases page](https://github.com/black-sliver/PopTracker/releases) (on Windows, the `win64` zip: unzip it
   anywhere).
2. **Start a session with `BOTW Archipelago.cmd`**, as the [setup guide](setup_en.md#playing) says. Before Cemu
   starts, the launcher asks once whether you want the PopTracker pack:

       PopTracker pack: none in this folder yet. PopTracker is an optional map tracker that follows the room (see the PopTracker guide).
       Build the PopTracker pack? (a few seconds) (Y/n):

   Press Enter. The pack is written to the `PopTracker` folder of the release:

       PopTracker pack built: <release folder>\PopTracker\botw_archipelago.zip
         To use it, drag this file onto PopTracker's window.

3. **Install the pack**: open PopTracker and drag `botw_archipelago.zip` onto its window. (You can also copy it into
   PopTracker's `packs` folder.)

You do this once per version of BOTW Archipelago. Every launch then says where the pack stands, in one line:

| The launcher says | What it means |
|---|---|
| `PopTracker pack: up to date, not rebuilt (...)` | Nothing to do: the pack in the folder is the latest. |
| `PopTracker pack rebuilt, it was out of date: ...` | Your icons or your game changed: drag the new file onto PopTracker again. |
| `PopTracker pack: not built, as you answered ...` | You said no; you will be asked again with the next version. |
| `PopTracker pack: not built (...)` | Something went wrong, the reason is in brackets; the game starts all the same. |

If you said no and change your mind, open a command prompt in the release's folder and run
`python\python.exe -I tools\build_poptracker.py`: it builds the pack in the same `PopTracker` folder.

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
freed, shrines cleared...), and a few that it does not need but you may want to follow: Master Cycle Zero, the
Travel Medallion, Epona, the Korok Mask and the pouch upgrades. A bright icon is an item you have; a number is how
many you have (a progressive item, a pouch upgrade). The region maps have their own two rows.

Everything is updated from the room; you never need to click anything. Without a connection, you can still mark
items and locations by hand with the mouse.

## Icons

The map and part of the icons (hearts, stamina, Divine Beasts, shrines...) are drawn from your own game. The
launcher downloads the rest once, when it builds the pack, from the `tracker-icons` release of this project.
Without an internet connection, those items show a text label instead, which works just as well.

You can also use your own icons: put PNG files named after the items (`Paraglider.png`, `Zora Armor.png`...;
subfolders are fine) in `%LOCALAPPDATA%\BOTW Archipelago\poptracker\icons`. The next session rebuilds the pack with
them.

## Troubleshooting

- **No `PopTracker` folder in the release.** The pack is only built when you answer yes, at the start of a session.
  Look at the launcher's PopTracker line: it says why, and how to build the pack.
- **PopTracker still shows the old pack.** Drag the new `botw_archipelago.zip` onto its window again, then load the
  pack.
- **The map is a plain grid.** Your game is a `.wud` or `.wua` file: the map is drawn from a game installed as a
  folder (with `code`, `content` and `meta`). The tracker works all the same.
- **Nothing updates.** Click **AP** again and check the address and the slot name. The room's address changes
  when it restarts on archipelago.gg: take the new one from the room's page.
- **A location is red but you could get it.** The tracker follows the world's logic, which can be stricter than
  the game. You can do it anyway: it is checked all the same.
