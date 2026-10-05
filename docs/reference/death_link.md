# DeathLink

How the integration kills Link when another player dies, and how it recognizes Link's own death. Both were measured in
the game: lethal damage from an EventFlow entry, natural deaths (a fall, bombs), a rescue by Mipha's Grace, and a
reload from the menu.

## Killing Link

Writing `CurrentHart = 0` in GameData does not kill Link: the flag changes, the game does not react. The game has
an EventFlow action that does: `GameROMPlayer.Demo_ApplyDamage {Value, IsWaitFinish}`, damage in quarter hearts. The
game uses it once, in `Demo331_0` (the woman of the "don't damage the flower" quest slaps Link), where the flow
compares the player's hearts first (`ComparePlayerHeart`) and never applies a lethal value.

The pack adds one entry, `OperationGuide<APDeathLink>` ([`botw_patch/death_link.py`](../../botw_patch/death_link.py)):

1. `Demo_FlagON APDeathLinkKill`, a volatile bool added to the game's GameData (not saved);
2. `Demo_ApplyDamage` with a value of 1000, above any life (30 hearts and 10 extra hearts are 160 quarter hearts);
3. `ComparePlayerHeart {Threshold: 1}` (as `Demo331_0` uses it): only if Link is still alive, `Demo_FlagOFF`.

A death the entry causes therefore finds the flag set, and the reload that follows the death resets it. The entry is
registered as the game's background events are (`delivery_flow.QUIET_EVENT_INFO`, see
[ap_messages.md](ap_messages.md)): it pauses nothing. `OperationGuide` declares only `EventSystemActor`; the player is
declared as `Demo007_1` declares it.

What the entry does, measured:

- Link dies at once, in the frame the entry runs, exactly as in a natural death: the death animation, the game's death
  cutscene `Demo006_0`, the Game Over screen, then the reload of the last save.
- The game's own protections apply. Mipha's Grace, when ready, saves Link (`CurrentHart` goes to 32: full hearts and
  five extra hearts); the received death is then spent. Fairies are expected to behave the same (not measured).
- A lower value removes that many quarter hearts, with no animation and no sound: only the HUD's hearts change.

## Recognizing a death

Measured on a death from the entry and on natural deaths:

| Moment | `CurrentHart` | Event request | UI screen |
|---|---|---|---|
| Death | 0, at the frame of the request | `Demo006_0<Demo006_0>` (flags `0x4`) | |
| About 3 s later | 0 | | `0x30`, the Game Over screen |
| Reload, after about 9 s | 99999, for one frame, then the saved value | `Demo025_0<Demo025_0>` | `0x55` during the load |

- A rescue by Mipha's Grace never goes through 0 (5, then 32).
- A reload from the menu, without dying, goes through 99999, never through 0, and shows neither `Demo006_0` nor the
  Game Over screen (screens `0x2f`, `0x39`, `0x55`, request `Demo025_2`).

So `CurrentHart <= 0` is Link's death (`BotwGame.is_dead`), and it lasts long enough (about 9 s) to be seen by the
client, which reads it at every tick.

## What killed Link

The game keeps the type of the last damage Link took and the actor that dealt it, for the tips of the Game Over
screen (`TipsGameOver.bfevfl`). Static reading of the executable, then measured at deaths by fire, a fall, an enemy, a
bomb, drowning and cold ([`botw_client/death_cause.py`](../../botw_client/death_cause.py)):

- The EventFlow query `CheckPlayerDeadCause` (its name's CRC32 `0x749d8ed7` in the query factory table, factory
  `0x02b09588`, vtable `0x10192a9c`) has its `doQuery` at `0x02a6bc18`. It does not use its object: it takes the player
  through the `PlayerInfo` singleton (`*0x10463f38`, player at `+0x30`) and maps `0x02b72c30(player)` (low 16 bits a
  damage type, high 16 bits an attribute) to 0-13. The client calls it through the cave's per-frame hook.

  | Value | Cause | Value | Cause |
  |---|---|---|---|
  | 0 | heat (raw type 1), and the default: an enemy's blow | 7 | drowning |
  | 1 | cold | 8, 13 | fall |
  | 2 | ice | 9 | bomb |
  | 3 | poison | 10 | crushed |
  | 4 | fire | 11 | the Master Sword |
  | 5 | shock | 12 | sudden death |
  | 6 | lightning | | |

- The query `CheckLastDamageAttacker` compares its name with the `sead::SafeString` at player `+0x974`: the name of
  the last actor that hurt Link (`Enemy_Bokoblin_Junior`, `RemoteBomb`...). Damage from the environment and a reload
  clear it.

It is the type of the last damage, not a cause of death: the entry's `Demo_ApplyDamage` sets none, so a death from a
received DeathLink keeps the type of whatever hurt Link before (measured: Cold after cold damage, 0 after a reload).
That is why the entry marks its deaths with its own flag.

The pack's delivery catalog carries the English names of what can kill Link (`death_link.attackers`), read at build
time from the player's own game files (the `_Name` texts of `ActorType/Enemy.msbt`, `Guardian.msbt`... in
`Bootup_EUen.pack`).

## The client

`BotwClientRuntime._deathlink_tick` ([`botw_client/runtime.py`](../../botw_client/runtime.py)), when the seed has
the `death_link` option (slot data):

- **Sending**: on the edge from alive to dead, once, with what killed Link: "Zelda was slain by a Bokoblin", "Zelda
  burned to death", "Zelda fell to their death", "Zelda was caught in their own bomb blast"... or "Zelda died in
  Hyrule" when the game says nothing more. A death while disconnected is sent at the reconnection. Being dead when the
  client starts is not a death.
- **Receiving**: the latest received death waits for a safe moment (the delivery gate: no menu, event, cutscene or
  loading), is announced in the Archipelago journal ("DeathLink: ..."), and 3 s later requests the entry. Deaths
  received while one waits are one death; a death still waiting after 2 minutes is dropped.
- **No echo**: a death that finds the entry's flag set is the received DeathLink's, and is not sent back. The flag
  counts for 60 s after the request, in case it stayed set although Link survived. A pack whose catalog names no flag
  falls back on the time: a death within 5 s of the request.
- A pack built before the entry existed has no `death_link` in its delivery catalog: the death is dropped, with a
  message asking to rebuild the pack.

The console command `/ap-deathlink [cause]` kills Link as a received DeathLink would, without sending anything.
