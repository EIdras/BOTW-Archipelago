# In-game messages and item deliveries

How the integration talks to the player inside the game, and how received items reach the inventory: the Archipelago
journal, the connection status, the game's own item windows, items given back after a reload, and the rune download
screen.

## The Archipelago journal (tip frame)

The server's messages are shown in the game's **tip frame** (`MessageTipsRunTime_00`, top right of the screen): it
does not stop the game, holds 3 lines with colors and fades out by itself. The dialog window, used by shrines, is not
used for the journal: it blocks the game while it is open.

### The game's tip frame (measured)

- `0x02fd4848(this, index)` only sets the text: called alone, nothing is shown (the frame is not open).
- **`0x02fd4730(this, index, force)` is the public request**: it takes the widget's lock (`this+0x1b6c`), refuses
  `index >= 23` or a tip already shown, refuses when the tip's `GuideS_…` flag is true (a tip is shown only once),
  refuses while the game is busy unless `force` is set, then queues the tip; the per-frame update opens the frame and
  calls `0x02fd4848`.
- The frame has **no automatic line wrap**: a long text runs off the right of the screen. Vanilla tips are wrapped by
  hand, **3 lines of at most 34 characters** (French, English, German).

### Native side

[`tools/build_tip_channel.py`](../../tools/build_tip_channel.py) adds the channel to the injected code of every pack
(through `tools/build_native_from_source.py`); the contract shared with the client is
[`botw_client/tip_protocol.py`](../../botw_client/tip_protocol.py).

- The channel borrows tip index 21, `GuideS_RelicControl` (the tip about controlling a Divine Beast, shown once, inside
  the Divine Beasts).
- `apTipSubmit` runs on the game's thread, from the per-frame invoker, under the common lock. It refuses when an
  Archipelago tip is active or when any tip is queued or on screen, the game's included: forced over the heat warning,
  which the game asks for again at once, ours evicted it and was evicted in turn, and the warning came back in a loop
  (measured). It reads the flag through the game's own reader
  (as `0x02fd4730` does), sets its value bit to 0 (the flag object is checked by its hash), publishes a generation,
  and makes the official request `0x02fd4730(widget, 21, 1)`. When the game did not queue it, the flag is restored at
  once.
- **Text substitution** at `0x02fd48c8`, where the game sets the tip's text: only for the same widget, the same index,
  and a request in the "requested" phase. The game sets our text itself.
- **End**, in the per-frame hook of `0x02fd4a1c`: once the index is neither queued (`+0x1ba8`) nor on screen
  (`+0x1bb0`, reset to -1 by `0x02fd4bc0`), the flag gets its original value back and the generation ends.

Nothing else of the game changes: the borrowed tip keeps its own text and is still shown once, as in the vanilla game.
`tests/test_tip_channel.py` runs the generated code on a model of the widget, and `tools/patch_lint.py` checks the
composed patch.

### Client side

- [`botw_client/tip_channel.py`](../../botw_client/tip_channel.py) finds the channel's data by its signature in the
  code cave. It cuts text into pages of 3 lines of 34 characters, with colors written `{N}…{/}` (players `{2}`, items
  `{1}`), and shows one tip at a time, the next one once the game has closed the frame. A received item waits for its
  line at most 8 s (`JOURNAL_BLOCK_SECONDS`): in the heat, the warning keeps the frame, and the item then comes first.
- [`botw_client/ap_journal.py`](../../botw_client/ap_journal.py) chooses what is shown: the server's own text
  (`PrintJSON`) for what concerns the slot, meaning items received (from another player or found in the player's own
  world), items sent, and hints; chat, which can be turned off; nothing about other players by default. Items found
  for oneself are not repeated. The client adds its own announcements: connected, connection lost, reconnected. Only
  messages of the current session, less than 5 minutes old, are shown.
- **A received item** is announced first. Its server line is found by item, location and sender; without one after
  3 s (an item received while offline, a console `/send`), the client writes the same sentence in the server's format.
  The line is left 2 s to be read, then the item is presented: by the game's own window when its delivery has one,
  otherwise by an Archipelago window.
- **A location whose item goes to another player** gets no window: the server's "sent" line is enough.

The pack declares the journal (`manifest.json`: `"ap_journal": "tip_channel"`) and the play session turns it on. The
console command `/ap-tip <text>` shows a line in the journal.

## Connection status

- **Journal**: the connection is announced once, then **one** line per outage (not one per attempt), then "Reconnected
  to Archipelago after N s". The console command `/ap-disconnect [s]` simulates an outage of `s` seconds.
- **The "Archipelago" key item** (`botw_patch/status_item.py`): a key item cloned from Hestu's maracas, with the
  Archipelago logo. Its description gives the seed, the player (slot) and the goal. The entry
  `Demo007_1<APStatusItem>` adds it only when the pouch lacks it (`HasPorchItem`); the client requests it once per
  connection to the game, after the pending deliveries. Every seed pack has it.
- **HUD**: the Archipelago logo at the bottom left, in color when connected, grey otherwise:
  [hud_indicator.md](hud_indicator.md).

## Item deliveries

Every item is delivered by requesting an EventFlow entry built for it
([`botw_patch/delivery_flow.py`](../../botw_patch/delivery_flow.py)), under the guard of the save's delivery cursor
`APReceivedCursor`. A delivery is requested only in a safe state (no menu, event, cutscene or loading), and at least
`SETTLE_FRAMES` = 90 frames after the previous commit: an entry requested right after a commit can be accepted and
never played, because the commit comes before the previous event has ended (a Fairy requested 38 frames after a
Heart Container's commit). Such an entry never raises its save guard, which every mutation follows: once 30
seconds of play pass with no guard, commit or rejection seen, it is asked again. An entry that raised its guard
without committing stops the client (possible mutation).

- **The game's get window** (`GetDemo<GetItemByName>`, `pouch_kind` in `botw_client/delivery_plan.py`) for every item
  that goes into the pouch: armor (one window per piece), weapons, shield, paraglider, Korok seeds, Spirit Orbs,
  fairies, materials, heart containers, stamina vessels and rupees.
- **Champions' abilities**: the game's own window (`GetDemo<ShowGetDemoDialogByName>`, a special presentation), at its
  vanilla place in the entry: inventory, equipment, window, flag. The upgraded ability of the Champions' Ballad has no
  window, because granting the DLC power through `GetDemo` outside the Ballad crashes the game: in that rare case the
  journal line is the only presentation.
- **Runes**: the Sheikah Slate's download screen, see below.
- **Region maps**: as a tower's event ends (`Demo004_0`): the map's flag, `IsDownloadDemo` (the menu consumes it as
  it opens and runs its download states), 10 frames for the map to rest, the map's opening
  (`EventSystemActor<Demo_StartMapOpenDemo>`), the tower's 240 frames, the Slate's line "Regional map extracted."
  (`Demo004_0_Text026`), the menu closed, then Link puts the Slate away; `IsDownloadDemo` off last. The game's action
  opens the map of the tower nearest to its actor, which a tower's event is; in a delivery, the native patch
  (`tools/build_tower_maps_native.py`) makes it take the tower the client writes in the cave (`apMapTower`) just
  before. Like a rune, it waits for the pause menu (map and inventory) to be loaded. Before the Great Plateau's
  tower, the Slate has no map: the map is then revealed by its silent twin.
- **Without a game window** (Sheikah Sensor, Ancient Bridle, Ancient Saddle): the entry is hosted in `OperationGuide`
  with `QUIET_EVENT_INFO`, like the quiet twins below, so that it neither pauses the game nor makes the HUD blink. The
  step names its flowchart in the catalog (`flow`, from `delivery_flow.host_of`). An Archipelago window names the item
  and its sender.
- **A filler item received again** (AP flags 0, `BotwClientRuntime._repeat_filler`): as a known item is picked up, its
  journal line and the game's pickup notification on the right, without a window nor a pause. It is delivered by its
  quiet twin; once the entry has closed and Link is back in the world, the client asks for the notification with the
  game's own function, the one a real pickup goes through: `0x03073C2C(SafeString* actor)`, which opens the
  `PickUpWin` screen and adds the line (`CemuNativeDeliveryBackend.show_pickup`, from the per-frame invoker). Measured
  in game: `Demo_OpenPickup` (`IsAddPorch`), the action the Rito brothers hand over materials with
  (`Rito_BrosRock`), calls that same function but showed nothing from our entry; called from the invoker, it shows
  (measured). The item map opts in with `"pickup": true` (Spirit Orb, Ancient Core, Star
  Fragment, Korok Seed, Fairy; `validate_item_map` refuses it on a useful or progression item). A notification not
  shown is only logged. Rupee bundles: their silent twin, `Demo_IncreaseRupee`, whose counter shows them. A unique,
  useful or progression item, or the first of a kind, keeps its window; so do an elixir and a weapon, every time
  (`"window": "always"`).
- **A full pouch**: the entry checks for room first (`CheckAddPorchItem`), shows the game's "pouch full" message and
  gives nothing. Once the message has closed, a weapon (but the Master Sword), a bow, a shield, an arrow bundle or a
  gem falls at Link's feet, created by the game's actor creation, and the step's drop entry only commits it: the
  queue goes on ([`botw_client/item_drop.py`](../../botw_client/item_drop.py)). An item left on the ground is lost
  with the area. Other items wait for room.

The commit comes at the entry's end, after the window, which waits for the player. The client waits for it as long as
the entry runs (its `SaveProhibition` guard up) or a window or menu is open; only 30 s of Link playing with nothing
running end the wait as uncertain (`native_delivery.COMMIT_LIMIT` bounds the whole wait at 10 min). A get window left
open used to stop the client after 30 s.

### Items given back after a reload

Loading an older save moves the delivery cursor back. The client keeps the highest index ever delivered
(`delivered_high`): below it, an item is given back, not new. It is then delivered by the step's **quiet twin**
(`quiet_entry` in the catalog), which puts it straight into the inventory, without its window. Once they are all back,
**one Archipelago window, "Items restored"**, names them (4 lines of 40 characters, "and N more" when they do not fit).
A former reload's window still waiting when another reload is given back is dropped, as long as the game was
never asked for it (`PresentationQueue.withdraw`): the new one names what comes back again.

The items a **release or a collect** sends at once come the same way, named by one window **"Items received"**,
without their journal lines. Archipelago marks no item as released: the server's notice tells it (PrintJSON `Release`
with the released slot, `Collect` with this slot), and the items it sends arrive within seconds of it
(`BULK_WINDOW_SECONDS`, 15). Items of a live packet (not the ones a connection sends again) arrived that close to a
notice, and for a release those of the released world, are given quietly (`BotwClientRuntime._mark_bulk`). A trap
still strikes and a rune keeps its download screen. A release that happened while the client was away cannot be told
apart: its items come one by one, as usual. The journal says once that they are coming ("N items of a release on their
way"). A step after a silent twin waits `QUIET_SETTLE_FRAMES` (20) instead of `SETTLE_FRAMES`: a silent twin neither
pauses nor opens a window, and is over a few frames after its commit.

- **Rupees**: the quiet twin of a rupee bundle is the game's own action `Demo_IncreaseRupee {Value, IsWaitFinish}`,
  the one of quest rewards (for example `Npc_Goron018` Event179, `Demo035_0` Event136), with the value of the bundle's
  `GetDemo` actor (`PutRupee_Red` = 20). `IsWaitFinish` is false, so the counter animation does not freeze the player.
  Writing the rupee counter directly does not work.
- Heart containers and stamina vessels: the Horned Statue's own actions (`Demo_IncreasePlayerMaxHeart`,
  `Demo_IncreasePlayerMaxStamina`, `Value: 1`, as `Demo035_0` trades them), with `IsMoveCenter` off. A bare counter
  write does not give them.

**No pause, no HUD blink.** A quiet twin used to freeze the game for a fraction of a second and blink the HUD. The
cause is the EventInfo key `is_pause_non_demo_member`: without it, an event pauses everything that does not take
part in it. The game's background events set it to `False`, for example `Npc_King_Vagrant001<Near>`, which leaves the
HUD alone. The quiet twins are registered like them, with `delivery_flow.QUIET_EVENT_INFO` =
`{disable_event_start_interval, is_pause_non_demo_member: False, is_timeline: False, mode: Seamless}`, and hosted in
the resident flowchart `OperationGuide` (`delivery_flow.QUIET_FLOW`), whose own entries stay untouched; the catalog
gives the request its `quiet_flow`. Deliveries with a game window stay in `Demo007_1`, as cutscenes, like the game's
own gifts.

- The request flags are not the cause. They come from the flowchart's name (prefix `Demo` = `0xf`) and from the type
  (zeldaret/botw, `evtMetadata.cpp`, `initFlags_`). Without the key, the HUD blinks with `0x64` (default), `0x19a`
  (`Near`, the exact flags of the NPC above) and `0x1fe` (`Background`) alike; with the key, it never does.
- A new flowchart added to `TitleBG.pack` (`EventFlow/APDelivery.bfevfl`) is accepted by the game and never runs: an
  added file is not found the way the original resident flowcharts are.

The console command `/ap-evt [n|reset]` decodes the trace of the game's event requests (`patch_event_request.asm`):
flowchart, entry, type and flags (`tools/cemu/event_request_trace.descriptor_fields`; Wii U offsets of `evt::Metadata`:
type `+0xf8`, flags `+0x108`).

## Runes: the Sheikah Slate's download screen

A received rune is presented as the rune terminals of the Great Plateau present it: the pause menu opens on the
runes, the new rune downloads into its slot, the Slate's voice says the module is enabled, and the rune is selected.
There is no Archipelago window.

### The vanilla sequence

In the terminals' flowchart (`Demo003_0`, entries `Item01` to `Item04`), `IsDownloadDemo` is set first; then, one
after the other in the same branch: the screen (`Demo_OpenItemDownloadDemo`), a 70-frame wait, the voice
(`NPC_DRCVoice`) and `Demo_CloseItemMenu`. The parallel branch only holds the camera and the terminal's animation
(`CommonItemDownload`).

### What the action needs (static reading of `U-King.rpx`)

- AI class `OpenItemDownloadDemo`: factory `0x02ABE750`, vtable `0x1008C3EC`, `calc_` at `0x0234D868`.
- On its first pass, `ItemType` goes through the table `0x104BA91C`, then `0x0307D504` requests the pause menu (UI
  screen `0x1F`) and writes the request at `0x1053F754` (type u32, IsEquip, IsPowerUp; no request = `0xFFFFFFFF`).
- The action ends only when `0x0307D5BC` sees the menu in the state whose object is at `0x1053F72C`.
- Menu side (`0x02F7F274`), the sequence starts only if the slot list (`+0x1B7C` count, `+0x1B80` array of `0x18`-byte
  entries) holds a slot of the requested type (`+0x14`) that carries an item (`+0x00` non-zero). All 8 slots carry
  their item from the start of the game, before any rune.

On the vanilla terminal: `IsDownloadDemo` becomes 1 at the start of the cutscene; when the menu opens, the request is
written, the rune's slot is marked (`+0x10` = 1), and **the menu resets `IsDownloadDemo` to 0**. The menu itself writes
`PlayerEquipItemType` (IsEquip), goes through its download states (`+0xDC`: `0x1053F694`, then `0x1053F6F4`), and the
action returns before the voice. After the menu closes, the rune's flag (`IsGet_Obj_Magnetglove` for Magnesis) is set,
the request cleared, and the menu is in state `0x1053F724`.

### Why the menu must already be loaded

The action first asks for the menu to be built at once (`0x03080A14(0x1F)`, then the loader `0x03058E84`). The loader
builds it at once only if:

- the **map** (screen `0x2A`) is at rest (`+0x96` = 0 and `+0x95` ≤ 0, `0x03A3E4DC`);
- the map is loaded (its loader at `+0x21AC`: state `+0xD8`/`+0x124` = 13 and `+0x100` = 0, `0x02F359F0`);
- the **inventory** (screen `0x22`, its loader at `+0x9080`) is loaded.

Otherwise the menu is built a few frames later, after the request, and its constructor (`0x02F7EE70`, through
`0x02F7EE58`) clears the request: the menu opens as an ordinary pause menu and the download screen waits forever.
In play, the map is almost never at rest (state 2): it rests only while the HUD is hidden, around an event or when
the menu opens. Map and inventory, on the other hand, stay loaded once they have been.

Screens, as numbered by the factory `0x0305EB18`: `0x1F` pause menu, `0x22` inventory, `0x25` HUD, `0x29` tip frame,
`0x2A` map.

### The delivery

- **Client** ([`botw_client/pause_menu.py`](../../botw_client/pause_menu.py), read only): a `rune_download` delivery
  waits until the map and the inventory are loaded. A quiet twin does not wait.
- **Event** (`delivery_flow.py`, the chain of `DOWNLOAD_FLAG`), in the vanilla order: `IsDownloadDemo`; a 10-frame
  wait (`DOWNLOAD_SETTLE`), which lets the map come to rest with the HUD hidden; the screen; a 70-frame wait
  (`EventSystemActor[01]`); the voice; the menu's close; the rune's flag. Then the player's part of
  `Demo041_0<SheikPadSetOff>` (`GameROMPlayer` `Demo_PlayASAdapt` `SheikPadSetOff` until it ends, then `DemoWait`),
  20 frames, as after the terminal, and the rune's selection (`PlayerEquipItemType`). Given back after a reload, a rune
  gets its flag and its selection only.
- The terminal's cameras and animations, its music and the `Guide_ItemUse` tip are not reproduced. The animation in
  which Link puts the Slate away is made for the Slate laid on the terminal, and looks slightly odd outside of it.
- The rune wheel follows the selection: `botw_client/rune_selection.py` synchronizes the game's live selection object
  with `PlayerEquipItemType` after the commit, and on every connection if a delivery was interrupted in between.
