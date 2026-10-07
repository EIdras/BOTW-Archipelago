# Traps

Six Archipelago items that hurt: how each one acts in the game, how a received trap is delivered, and how to add
one. Five are the game's own EventFlow actions and queries, in one entry of the resident `OperationGuide`, or of
`Demo007_1` for the Blood Moon ([`botw_patch/traps.py`](../../botw_patch/traps.py)); nothing in the executable is
touched. All five were seen working in the game. The sixth, Cucco Swarm, is played by the client through the game's own
functions, as no EventFlow action can do it ([below](#cucco-swarm)).

## The traps

| Item | Entry | What it does |
|---|---|---|
| Weapon Shatter | `APTrapWeaponShatter` | the melee weapon in Link's hand is deleted |
| Blood Moon | `APTrapBloodMoon` | the Blood Moon rises at once: its cutscene, and the monsters come back |
| Rupoor | `APTrapRupoor` | takes up to 100 rupees |
| Hearts Down | `APTrapHeartsDown` | takes up to two hearts, never the last quarter |
| Strip Down | `APTrapStripDown` | weapon, shield, bow and armor go back in the pouch |
| Cucco Swarm | none: the client's | the angry cuccos' swarm on Link, for 10 s |

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

- **No window.** The Archipelago journal announces the item as any ("Alice sent Rupoor to Bob"), 2 s later the trap
  strikes, and the journal says what it did ("Rupoor: Rupees slip through your fingers."). The text is the item's
  `delivery.text` in [`data/item_map.json`](../../data/item_map.json).
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
holds its events (presentations, deliveries, the key item, a received DeathLink); the journal and Link's death go on.
The swarm stops when Link dies, and the loop, when it leaves, stops the swarm and waits for it before closing the game
connection.

**It can kill.** The vanilla swarm does damage, and Link with few hearts can die of it. Such a death is not sent as a
DeathLink: while the swarm's attackers may be around (its 10 s, their lifetime and 3 s more), a death whose last
attacker (the actor name the game keeps, as for the DeathLink's cause) is `Kokko_Simple` is the trap's.

## What EventFlow cannot do

Traps that put something in the world (an ambush) are not possible from an entry: what an event creates belongs to it
(see Cucco Swarm). The `AutoPlacement*` flows, which place the ecosystem's enemies, run on map actors and ask
`AutoPlacement` queries (`GroundMat`, `WaterDepth`, `EcoAreaActorName`...) that an entry has no actor to answer. Such a
trap would be played by the client, as Cucco Swarm is.
