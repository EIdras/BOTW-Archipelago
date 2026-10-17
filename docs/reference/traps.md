# Traps

Nine Archipelago items that hurt: how each one acts in the game, how a received trap is delivered, and how to add
one. Five are the game's own EventFlow actions and queries, in one entry of the resident `OperationGuide`, or of
`Demo007_1` for the Blood Moon ([`botw_patch/traps.py`](../../botw_patch/traps.py)); nothing in the executable is
touched. All five were seen working in the game. The other four are played by the client through the game's own
functions, as no EventFlow action can do them: Cucco Swarm ([below](#cucco-swarm)), Yiga Ambush
([below](#yiga-ambush)), Paranoia ([below](#paranoia)), and Downpour, whose weather the pack holds
([below](#downpour)).

## The traps

| Item | Entry | What it does |
|---|---|---|
| Weapon Shatter | `APTrapWeaponShatter` | the melee weapon in Link's hand is deleted |
| Blood Moon | `APTrapBloodMoon` | the Blood Moon rises at once: its cutscene, and the monsters come back |
| Rupoor | `APTrapRupoor` | takes up to 100 rupees |
| Hearts Down | `APTrapHeartsDown` | takes up to two hearts, never the last quarter |
| Strip Down | `APTrapStripDown` | weapon, shield, bow and armor go back in the pouch |
| Cucco Swarm | none: the client's | the angry cuccos' swarm on Link, for 10 s |
| Yiga Ambush | none: the client's | two Yiga Footsoldiers and a Yiga archer fall on Link |
| Downpour | none: the client's and the pack's | rain for 2 minutes, or a thunderstorm for 90 s |
| Paranoia | none: the client's | a Guardian takes aim at Link from behind, and vanishes before it fires |

**Weapon Shatter.** The game's flows delete an item by name (`EventSystemActor.Demo_DeletePorchItemInEquip
{PorchItemName, DeleteNum}`: `Demo604_0` takes `Weapon_Sword_502`, `Demo622_0` a champion's power), and ask what Link
holds with `CheckEquipment {EquipItemName}` (`KorokMini_RodShiren`, `Npc_Zora027`...). The entry asks, for each of the
127 melee weapons ([`botw_patch/melee_weapons.py`](../../botw_patch/melee_weapons.py): every weapon the game's texts
name, Master Sword excepted), whether Link holds it, and deletes the one he does. It then unequips the weapon slot
(`Demo_SwitchPlayerEquipment {UnequipWeapon}`, as `Demo205_1` does), so that no ghost stays in the hand. Bare hands,
a bow or a shield alone: nothing happens. The Master Sword never breaks: it is left out.

**Blood Moon.** The game starts a Blood Moon at a midnight: WorldMgr calls the cutscene `Demo011_0` and resets the
Blood Moon timer `WM_BloodyMoonTimer` to 0 ([ZeldaMods, WorldMgr](https://zeldamods.org/w_botw/index.php?title=WorldMgr)).
The cutscene contains `Demo_OffWaitRevival`, which is what resets the revival flags, so that the defeated monsters and
the weapons left on the ground come back ([ZeldaMods, Blood moon](https://zeldamods.org/wiki/Blood_moon)). The entry does
the same at once: the timer back to 0, then `Demo_CallDemo Demo011_0`, the way the resting flows (`Demo007_0`,
`Demo007_1`) call it after the time has passed.

Only a demo event can call the cutscene. Called from an `OperationGuide` background event, it froze Cemu, then
crashed it, before `Demo011_0` was even requested. The resting flows that call it are demo events whose EventInfo
declares the cutscene and its two movies as children (`child: Demo011_0, Demo165_4, Demo165_5`). The entry is
therefore hosted in `Demo007_1`, the campfire rest, and registered with a copy of the rest's own sub-flow EventInfo
(`Demo007_1<Demo007_1_Sub>`, `traps.DEMO_HOST_INFO`). So is its delivery entry. Measured: the cutscene plays, Link gets
his control back, and a monster killed just before comes back. The cutscene requested alone, `Demo011_0<Demo011_0>`,
as WorldMgr does at midnight, did the same.

WorldMgr does not allow a Blood Moon everywhere: not outside the main field (shrines, Divine Beasts...), not while
`BloodyMoonProhibition` is set by an event. The entry asks the same (`CheckFlag BloodyMoonProhibition`,
`IsCurrentMainFieldStage`, the query `AocResident` uses), and where it would not be allowed it sets `WM_BloodyDay`
instead: the next midnight is the Blood Moon, as when the game's seven days have passed. It zeroes
`WM_bloodyEndReserveTimer` first, the countdown that clears the flag five game minutes after a midnight, so that a trap
received just after midnight is not undone.

**Rupoor.** `Demo_IncreaseRupee {Value: -N}` is how the game charges Link (`Demo035_0`, `Gerudo_CarryIce_mini`), after
`CheckRupee {Value}` has said the purse holds N (case 1). The entry takes the largest of 100, 50, 20, 10, 5 and 1 that
the purse holds, so the count never goes below 0.

**Hearts Down.** `GameROMPlayer.Demo_ApplyDamage {Value}` in quarter hearts: the action of `Demo331_0`, whose ladder of
`ComparePlayerHeart {Threshold}` (case 1: at least Threshold quarters) the entry copies. It takes 8, or all but one
quarter when Link has fewer: for Link with 3 hearts, 11 quarters. A hit leaves no animation and no sound
([death_link.md](death_link.md)); Link never dies of it.

**Strip Down.** `Demo_SwitchPlayerEquipment` with the six `Unequip` flags set and no item named, the form of
`ShieldofKolog`'s weapon, shield and bow. The game's flows set the three armor flags nowhere, so the armor is the part
this relies on without a vanilla example.

## Delivery

A trap is an item like the others: a guarded entry per item (`APD_xxxx_00`, in `OperationGuide` like the steps with
no window of their own, in `Demo007_1` for the Blood Moon: the item map's `delivery.host`), under the save's delivery
cursor. Its mutation, `trap`, is a **sub-flow call** to the trap's own entry in the same flowchart, made once the
cursor is committed and the guard released: the Blood Moon's cutscene runs long after the commit, and a trap cut
short after its commit is spent, never suffered twice. The entries are added first
(`traps.add_entries`), and the delivery builder refuses a trap whose entry is missing. The trap's entry can also be
requested alone.

- **No window, no warning.** Nothing announces a trap: the server's line ("Alice sent Rupoor to Bob") is kept
  until the trap has struck (`BotwClientRuntime._received_announcement`), then the journal shows it in one tip, with
  what the trap did ("Alice sent Rupoor to Bob. Rupees slip through your fingers."; without the server's line,
  "Rupoor: Rupees slip through your fingers."). Seen in play: announced first, the journal named Paranoia before its
  Guardian came; in two tips, the second came long after the trap, the journal showing one tip at a time. A trap of the entries is named at its commit; one the client plays, as it strikes:
  Cucco Swarm at its first attacker, Paranoia as its Guardian takes aim, Yiga Ambush when its Yiga are there,
  Downpour when its weather is held (named once over, the swarm and the Guardian were long gone: seen in play). The text is the item's `delivery.text` in [`data/item_map.json`](../../data/item_map.json).
- **Safe moments only.** The delivery gate is the usual one: no menu, event, cutscene or loading. A trap never runs
  while Link is dead.
- **Not suffered twice.** Loading an older save moves the cursor back and the client gives items back quietly. A
  trap's quiet twin (`APD_xxxx_00Q`) only commits the cursor: no effect, no journal line, and not in the "Items
  restored" window.

## Options

`trap_percentage` (0 to 100, default 0): the share of the filler (arrows, elixirs, weapons, gems, rupees) taken by
traps. `trap_weights`: how likely each trap is compared with the others, by item name; one left out, or at 0, never
comes up; all at 0 with a percentage above 0 is an error at generation. The traps are drawn with the seed's random
generator, so a seed is reproducible. Their classification is `trap`.

## Adding a trap

1. A row in [`botw_world/data/items.json`](../../botw_world/data/items.json) with `"trap": true` and the next free id
   (ids are append-only).
2. A row in `data/item_map.json`: `"delivery": {"kind": "trap", "entry": "APTrap<Name>", "text": "<what the journal says>"}`.
3. A builder and a `Trap(item, entry, builder)` in `botw_patch/traps.py`. The builder chains events with `Builder.action`
   and `Builder.switch`, from the last event to the first, and returns the first.
4. Tests in `tests/test_traps.py`: walk the entry's graph with the queries answered, as `EntryTests` do.

A trap the client plays itself: `"delivery": {"kind": "native_trap", "effect": "<effect>", "text": ...}` in the item map
(step 2), the effect in `botw_client/items.py` (`NATIVE_EFFECTS`) and played by `BotwClientRuntime._native_trap_tick`;
no entry (step 3). A new effect needs a new `client_schema`: an older client cannot play it.

## Cucco Swarm

In the game, a cucco hit often enough gets angry, and its AI (`KokkoAngry`) brings the swarm: for a while it creates
attackers (`Kokko_Simple`), small temporary cuccos that rush at their target and vanish, and gives each one that
target. The trap plays that part itself, without a cucco
([`botw_client/cucco_swarm.py`](../../botw_client/cucco_swarm.py)).

**Why not EventFlow.** An event can create actors (`CreateMode: 1`, as cutscenes create theirs), but they belong to it.
Measured: a cucco and three attackers created by an entry appeared frozen, without their AI, and vanished when the event
ended. The cucco's `Demo_Angry` only plays its animation and its cry.

**What the client calls**, from the cave's per-frame invoker, as the angry cucco does (read in the executable):

1. `ActorCreator::requestCreateActor` (`0x037b5e8c`) with the actor heap, a `BaseProcHandle`, and an `InstParamPack`
   holding the position (`@P`), built by the game's own functions, as the angry cucco's base AI builds it.
2. Once the handle says the attacker is ready, its AI tree variable `AttackTargetActorLink` gets a link to Link, copied
   by the game's own assignment (the angry cucco's callback, `0x026e5ffc`); then the attacker is let go.
3. The rhythm and the place are the angry cucco's parameters (`Kokko.baiprog`, `KokkoAngry`): born in a box of ±10 m,
   ±4 m in height, 5.5 m above Link, not within 5 m, one every 5 frames, for 300 frames. An attacker lives 70 frames.

The invoker makes one call per frame and an attacker takes about eight, so the swarm is thinner than the game's.
Measured: 38 attackers in 10 s, from every side, 1.5 hearts lost, no slowdown. Each attacker cries and rushes through
the air with the game's sounds, except in the Shrine of Resurrection at the start of the game, where the swarm was
seen silent (on the Great Plateau, the same swarm is heard).

**Delivery.** Its entry only commits the cursor, under the guard (`native_trap` in the item map, `effect:
cucco_swarm`); the client plays the swarm once it has seen the commit, one swarm at a time. Given back after a reload,
or committed while the client was stopping, it is spent without effect.

**Sharing the invoker.** The swarm plays on a thread of its own, while the client's loop goes on. Both use the cave's
one request slot, in turns ([`botw_client/invoker_turn.py`](../../botw_client/invoker_turn.py)): each attacker is made
in one turn, and the loop waits for it instead of finding the emulator's mutex busy. For the swarm's 10 s, the loop
holds its events (presentations, deliveries, the quest, a received DeathLink); the journal and Link's death go on:
between two attackers, the swarm lets the turn go (`YIELD`), or the journal, waiting for it, would only name the
swarm once it was over.
The swarm stops when Link dies, and the loop, when it leaves, stops the swarm and waits for it before closing the game
connection.

**It can kill.** The vanilla swarm does damage, and Link with few hearts can die of it. Such a death is a death like
any other: with DeathLink on, it is sent ([death_link.md](death_link.md)).

## Yiga Ambush

The Yiga Clan's squad: two Yiga Footsoldiers (`Enemy_Assassin_Junior`) and a Yiga archer
(`Enemy_Assassin_Shooter_Junior`), created by the client at 6 to 8 m around Link, evenly spread from a random
bearing ([`botw_client/yiga_ambush.py`](../../botw_client/yiga_ambush.py)). The creation is the swarm's
(`ActorCreator::requestCreateActor` with a place, `@P`), without a handle: the Yiga are the game's, with their own AI.
Each comes with its series' first weapon (`EquipItem1`, a string of type 5, as the game's own creations add it): the
Vicious Sickle (`Weapon_Sword_053`), the Duplex Bow (`Weapon_Bow_040`), the Windcleaver (`Weapon_Lsword_074`); the level
sensor raises it as the game goes on. Without it, a Yiga carries what the level sensor finds at the player's progress:
nothing on a new game (seen in play: bare hands, light blows, an archer warping again and again). One time in ten, a
Yiga Blademaster (`Enemy_Assassin_Middle`) comes alone instead. Each one has a block of memory of its own: without a
handle, nothing says when the creator is done with its name and its place, so no block is ever reused.

Measured (lab probes 19 and 21): they come with the Yiga's appearing effect, fight with their weapons, flips and warps,
the archer shoots, they drop their loot (bananas, rupees) when defeated, and vanish if Link runs far away. Two keys of
the game's own creation of an enemy near Link (`0x0214ae5c`) must not be added: with `IsNearCreate` (bool, type 3) the
squad came and went at once, unseen; with `@I` = 6 (int, type 0) nothing came.

**Delivery.** As the swarm's: its entry only commits, then the client creates the squad, in one turn of the invoker,
once Link is in the world (no menu, entry or loading) and once the trap's event has closed (`SETTLE_FRAMES`, 90 frames
after its commit, as a delivery waits before the next one): created a second after the commit, the armed Yiga left at
once in a warp (seen in play). A squad committed while Link was leaving the world waits for him, two minutes at most.
The Yiga can kill: such a death is a death like any other.

## Paranoia

A Decayed Guardian (`Enemy_Guardian_A_Fixed_Moss`) appears 15 m behind Link, turned towards him: the game's own Guardian
sees him at once, beeps, plays its music and points its red laser at him. 6.9 s of the game's time after its waking,
before its shot, the client deletes it: it vanishes at once, its music fades out
([`botw_client/paranoia.py`](../../botw_client/paranoia.py)).

**What the client calls**, from the cave's per-frame invoker, one turn of it per step:

1. The swarm's creation, with a handle and an `InstParamPack` holding the place (`@P`) and the rotation (`@R`: a
   Vec3, type 4, in radians, as the game's own creations add it; its yaw turns the Guardian's +Z towards Link).
2. Once the handle says it is ready, the proc is woken (`BaseProc::wakeUp`, `0x0378a540`): created with a handle, it
   sleeps until then.
3. Its link is read at once, as the swarm reads Link's: its id (`+0x50`) and its `BaseProcLinkData` (`+0x58`), which
   holds the id followed by the proc while the proc lives, and is reused under another id once it is gone.
4. 6.9 s after the wake, while the link data still holds it: `BaseProc::deleteLater(proc, 2)` (`0x0378a374`).

**Why not through the handle.** `BaseProcHandle::deleteProc` deletes the proc its unit holds. Measured: within 2 s of
the wake, the game itself unlinks the unit (no handle, no proc in it), and the call deleted nothing; the Guardian
stayed and fired again and again. Through its link, measured: the proc's state is "deleted" within 0.1 s, the link
still valid at 0.4 s, reused at 1 s.

**The time.** Measured: the Guardian fires about 7.1 s after its waking; deleted at 7.1 s, it had just begun to fire,
and the shot never left. The 6.9 s are the Guardian's own, the game's: the cave's frames, each worth the game's delta
per frame, read from its frame-rate manager (`*0x1047c258 + 0x1c`: the vsyncs between two frames over the nominal,
computed at `0x037932f0`; FPS++ writes 30/fps there). Measured: 1.0 at normal speed and on a vsync three times faster
(a turbo), where the game runs three times faster; counted on the clock, the Guardian fired again and again there.
The clock stays a ceiling: whichever comes first deletes it, so a slowed game, or a delta misread, only sees the
Guardian leave early. The client's log says what was measured ("deleted after 6.9 s of game time (206 frames, speed
x1.00), 2.2 s of wall time").

**Safety.** A Guardian whose link cannot be found is deleted through its handle before its wake, while the unit still
holds it: it never wakes. One gone before its time (defeated, or its area unloaded) is left alone. When Link dies, or
the client stops, it is deleted at once. Over uneven ground, the Guardian, which does not fall, may stand in a slope
or above it; behind a hill, it may not see Link.

## Downpour

Rain for 2 minutes, or a thunderstorm for 90 s (drawn by the client, [`botw_client/downpour.py`](../../botw_client/downpour.py)).
The rain wets the walls: Link slides down them. The thunderstorm brings its lightning, which strikes Link if he carries
metal, and can kill.

**The game's weather.** The flows' `WorldManagerControl.Demo_EventSetWeather` (class `EventSetWeather`, trigger
`0x021c2d50`) calls the weather setter once: `setWeatherType(*0x1047be88, type, 1, 0, 0)` (`0x03679688`), which sets
the type (`+0x649`) and a timer of 4 (`+0x60c`). Every frame of the world, the manager counts the timer down, and at 0
gives the type back to `0xff`, the climate's weather (`0x03677f84`; zeldaret/botw `worldManager.cpp`). One request is
thus 4 frames of weather; the game's weather zones (`ChangeWeatherTag`, Faron's storm) call the setter as long as Link
is in them. Types: 0 Bluesky, 1 Cloudy, 2 Rain, 3 HeavyRain, 4 Snow, 5 HeavySnow, 6 ThunderStorm, 7 ThunderRain,
8 BlueskyRain (zeldaret/botw `worldDefines.h`).

**The pack holds it.** Every pack calls the setter from the per-frame hook, at the head of the per-frame invoker's
block, as long as the cave's `apWeatherFrames` lasts ([`tools/build_weather_native.py`](../../tools/build_weather_native.py)).
The frames are the world's: one is counted when the manager's timer went below 4 since the last call, so that a
menu, which stops the world, does not shorten the weather (to be seen in the game). Another caller of the setter in
the same frame (a weather zone, a Wizzrobe) would keep the timer at 4 and the count still: the hook's passes
(`apWeatherPasses`, three times the frames) end the hold in any case. The client writes the type, the passes, then
the frames (`Cave.force_weather`, [`tools/cemu/mailbox.py`](../../tools/cemu/mailbox.py)).

**A death or a reload ends it.** Held by the pack, the weather would outlive a death and the save loaded after it.
The client marks the downpour with a volatile GameData flag, `APDownpour` (declared by the pack,
[`botw_patch/downpour.py`](../../botw_patch/downpour.py)): not saved, it goes back to false whenever a save is loaded,
and keeps its value across a fast travel, which loads none. While a downpour lasts, the client gives the game its
weather back (0 frames) when Link dies, or when the flag is down.

Measured with the setter called 30 times a second (lab probe 19, 09/10): the rain sets in within 5 to 10 s and the
walls get slippery; in the desert at night, the thunderstorm first looked like a sandstorm, then brought lightning and
rain; it held across a fast travel; the climate's weather came back within a few seconds. Inside a shrine, nothing
shows.

## What EventFlow cannot do

Traps that put something in the world (an ambush) are not possible from an entry: what an event creates belongs to it
(see Cucco Swarm, and Yiga Ambush, which the client plays). The `AutoPlacement*` flows, which place the ecosystem's enemies, run on map actors and ask
`AutoPlacement` queries (`GroundMat`, `WaterDepth`, `EcoAreaActorName`...) that an entry has no actor to answer. Such a
trap is played by the client, as Cucco Swarm and Yiga Ambush are. Nor can an entry hold the weather: its action asks
for 4 frames of it (see Downpour).
