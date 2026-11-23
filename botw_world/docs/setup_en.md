# Breath of the Wild Multiworld Setup Guide

**Setup** · [In the game](ingame_en.md) · [Options](en_Breath%20of%20the%20Wild.md) · [Hosting](hosting_en.md) ·
[Trackers](poptracker_en.md) · [Mods](mods_en.md) · [Troubleshooting](troubleshooting_en.md)

This guide gets you from nothing to playing Breath of the Wild in an Archipelago room, on Windows or Linux, in Cemu.
Hosting the room is on [its own page](hosting_en.md).

## What you need

- [ ] Windows 10 or 11, or Linux on a 64-bit PC (x86-64): see [On Linux](#on-linux).
- [ ] [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 or newer.
- [ ] [Cemu](https://cemu.info/) 2.x.
- [ ] Breath of the Wild for **Wii U**, European (EUR), American (USA) or Japanese (JPN), from your own console, in
      Cemu's game list.
- [ ] Its **update v208** (1.5.0) and its **DLC**, installed in Cemu (File > Install game title, update or DLC).
- [ ] The game started once in Cemu.
- [ ] About 5 GB of free disk space, and 140 MB more for each seed. With `shrine_chest_items`, about 1 GB more,
      once for every seed, and the base game installed as a folder (not a `.wua` or `.wud` file).
- [ ] The link of the room's page, or your **slot file** (`.apbotw`): on the room's page, "Download Patch File..."
      next to your name.

> [!NOTE]
> The Switch version is not supported: the integration is built for the Wii U v208 executable. With several versions
> in Cemu, the launcher plays the European one, else the American one.

## Install

1. Install [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) if you do not have it: the
   `Setup` program of its latest release (on Linux, its `AppImage`).
2. Download `botw.apworld` from the [releases](https://github.com/EIdras/BOTW-Archipelago/releases), in the
   release's **Assets**.
3. Open the **Archipelago Launcher**, click **Install APWorld** and choose `botw.apworld`. Close the Launcher and open
   it again.

<!-- ![BOTW Archipelago in the Archipelago Launcher](../../docs/images/ap-launcher.png) -->

That is all: BOTW Archipelago runs inside Archipelago. The host generates the seed with the same `botw.apworld`.

## Your first session

In the Archipelago Launcher, click **BOTW Archipelago**. The first time, it downloads the libraries it needs (about
14 MB, 18 MB on Linux, from the internet), then its window opens.

<!-- ![The first download](../../docs/images/setup-window.png) -->

<!-- ![The game found in your Cemu](../../docs/images/launcher-cemu.png) -->

1. **Cemu.** The first time, click **Choose Cemu...** and pick `Cemu.exe` (on Linux, Cemu's AppImage
   or the `Cemu` of its Linux zip). The launcher shows the game, its update
   and the DLC it found, and the room the profile takes. **Create the profile**: it copies Cemu and your saves into a
   profile of its own (about 5 GB). Your Cemu installation is never modified.
2. **The seed.** Click **Add from a room link...** and paste the link of the room's page
   (`https://archipelago.gg/room/...`): the launcher downloads your slot file from it, and asks which player you are
   when the room has several Breath of the Wild players. You can also click **Add a seed...** (Ctrl+O) and choose
   your slot file, or open it with **Open Patch** in the Archipelago Launcher. The launcher builds the
   seed's game pack, in about a minute. From a seed's zip, it asks which player you are.
3. **The room.** Its address (`archipelago.gg:38281`) is already filled in when your slot file comes from the room's
   page. Type the room's password if it has one, then click **Play**.

<!-- ![A seed added from its room's link](../../docs/images/launcher-room-link.png) -->

<!-- ![A seed ready to play](../../docs/images/launcher-seeds.png) -->

Cemu starts with the seed's game pack, and the window follows the session: the game pack, Cemu, the room, then your
save linked to the seed, with the checks found and the items received.

> [!IMPORTANT]
> **Start a new game** for a new seed: a save is bound to the seed it was started with.

Play normally: your items arrive in the game, and the Archipelago journal, top right of the screen, says what you
send and receive. [In the game](ingame_en.md) shows what to expect.

Close Cemu to end the session; the launcher's window can stay open. **Play again** starts the same seed in the same
room.

## The next sessions

Open **BOTW Archipelago** from the Archipelago Launcher again. The seeds already prepared are listed, the last played
first, with the version that generated them and the day they were last played. Pick one: its room is remembered.
Click **Play**.

To remove a seed you no longer play, select it and click **Delete...**: it deletes the seed and its game pack, and
keeps your saves.

## During a session

The session's log shows the room's messages in the colours of Archipelago's own client: your name in magenta, the
other players in pale yellow, locations in green, and items by kind (progression in purple, useful in blue, traps in
salmon, the others in cyan). **Search the log** highlights what you type in it; Enter goes to the place before,
Shift+Enter to the one after.

The line under the log goes to the room as chat. Archipelago's commands work too: `/hint <item>`, `/players`,
`/status`... are sent to the room as `!hint`, `!players`, `!status`.

<!-- ![A session's log](../../docs/images/launcher-session.png) -->

## Hints

The **Hints** page lists the room's hints for you: where your items are, and the items of other players in your
world, the ones still to find first. It shows only your items, or only your world, and hides the hints already found.
The last hints of a seed stay listed when no session runs.

During a session, once Cemu has started, it asks the room for a hint: choose an item of yours or a location of your
world, start typing its name and pick it in the list, then click **Ask for a hint**. A hint costs hint points, as in
the room's chat.

<!-- ![The Hints page](../../docs/images/launcher-hints.png) -->

## Updating

The launcher looks for a new release when it starts, and offers it at the top of its window: **Install** downloads
the new `botw.apworld` and puts it in place of yours (the previous one is kept in the data folder's `downloads`).
Then close Archipelago and open it again. **Settings** checks again, or turns the check off. Your profile, your seeds
and their saves are kept. The first time you play a seed with the new version, the launcher builds its game pack
again. Give the host the new `botw.apworld` for the next seeds.

Archipelago runs one version of a world at a time. A seed generated by a newer version is shown with **Update to
version X**. A seed generated by an older version that this one cannot play has to be generated again with this
one: the launcher says so.

The seeds of the versions before 0.4.0, when BOTW Archipelago was a program of its own, are shown with their version
in orange: **Play with version X** downloads that version next to this one and opens its own launcher (a console
window for the oldest). The versions installed this way are listed in **Storage**, where one you no longer need is
removed.

### Coming from version 0.3 or older

Install as above: the window finds your profile, your seeds and their saves where they are. The folder where you
unzipped the old release can then be deleted.

## On Linux

The same `botw.apworld` runs in Archipelago's Linux build, on a 64-bit PC (x86-64) with a distribution recent enough
for Archipelago's AppImage. Two differences from Windows:

- **Archipelago** comes as an AppImage: download `Archipelago_<version>_linux-x86_64.AppImage` from its
  [latest release](https://github.com/ArchipelagoMW/Archipelago/releases), make it executable
  (`chmod +x Archipelago_*.AppImage`) and open it.
- **Cemu**: its official AppImage, or the `Cemu` of its Linux zip, from [cemu.info](https://cemu.info/). Not a
  Flatpak or Snap Cemu: its sandbox hides Cemu from the client, so the launcher refuses it.

Nothing else to set up. Cemu very slow, or a session that cannot reach it: see
[Troubleshooting](troubleshooting_en.md#common-problems).

## Where things are

Your profile, your seeds, their game packs and the older versions installed are in the data folder:
`%LOCALAPPDATA%\BOTW Archipelago` on Windows, `~/.local/share/BOTW Archipelago` on Linux. **Storage** shows what
takes room in it, and moves it to another folder or drive. The libraries downloaded the first time are in
Archipelago's cache: `%LOCALAPPDATA%\Archipelago\Cache\botw` on Windows, `~/.cache/Archipelago/botw` on Linux.

## Uninstalling

Delete `botw.apworld` from Archipelago's `custom_worlds` folder (on Linux, `~/.local/share/Archipelago/worlds`),
then the data folder (**Storage** shows where it is): the profile, with the saves of your Archipelago games, and the
seeds. Archipelago's cache folder named above can go too. Your Cemu installation was never modified.

---

Next: [In the game](ingame_en.md). Something went wrong? [Troubleshooting](troubleshooting_en.md). These guides are
also in the launcher: **Help**, at the bottom of its window's sidebar.
Running from the source code instead of a release:
[development](https://github.com/EIdras/BOTW-Archipelago/blob/master/docs/development.md#running-from-source).
