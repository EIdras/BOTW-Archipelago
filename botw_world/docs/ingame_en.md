# In the game

[Setup](setup_en.md) · **In the game** · [Options](en_Breath%20of%20the%20Wild.md) · [Hosting](hosting_en.md) ·
[Trackers](poptracker_en.md) · [Mods](mods_en.md) · [Troubleshooting](troubleshooting_en.md)

What Archipelago adds to Breath of the Wild, as you will see it while playing.

## Receiving items

Your items arrive as the game gives them: the item window, the champions' ability windows, the Sheikah Slate's
download screens for a rune or the Sheikah Sensor.

<!-- ![A rune downloaded to the Sheikah Slate](../../docs/images/rune-download.jpg) -->

- With a full pouch, a weapon falls at Link's feet.
- Epona is registered at the stables: take her out at any of them.
- A region's map opens with the game's own animation (see [region maps](en_Breath%20of%20the%20Wild.md#region-maps)).
- Each item is given exactly once per save, even across reloads and disconnections.

### After loading an older save

Loading an older save forgets what came after it. The client gives those items back quietly, then lists them in a
single Archipelago window.

<!-- ![The items given back after a reload](../../docs/images/items-given-back.jpg) -->

## Sending checks

Clear a shrine, climb a tower, free a Divine Beast: the check is sent at once. The locations are the game's own saved
flags, so a check done offline is sent at the next connection.

## The Archipelago journal

The room's messages appear in the game's tip frame, top right of the screen: the items you send and receive, the
items other players find for you, the hints, and what a trap or a DeathLink did.

<!-- ![The Archipelago journal](../../docs/images/ap-journal.jpg) -->

An item for another player is named there, with its recipient: your own items look as the game shows them.

## Connection status

An Archipelago logo sits in the HUD, by the minimap, and on the loading screen: in color while you are connected,
grey otherwise.

<!-- ![The Archipelago logo, connected and disconnected](../../docs/images/hud-logo.jpg) -->

The Adventure Log has an **Archipelago** main quest, with the seed, your slot and your goal. It is completed once
the goal is reached.

<!-- ![The Archipelago quest in the Adventure Log](../../docs/images/adventure-log.jpg) -->

## Shops and stalls

With the shop options, Beedle sells Archipelago items at the top of his stock, and village stalls show them as a
jewel. Each one shows the item's name and its recipient. Opening Beedle's list, or looking at a stall's jewel, hints
the items for sale there. Buying one checks its location.

<!-- ![Archipelago items in Beedle's shop](../../docs/images/beedle-shop.jpg) -->

<!-- ![An Archipelago jewel on a village stall](../../docs/images/stall-jewel.jpg) -->

## The sealed sanctum

Until the seed's requirements are met, entering Ganon's sanctum sends Link back to its doors: a monk says the seal
holds, and the journal says what is missing ("Sanctum sealed: 1/2 Divine Beasts freed, 3/4 runes"). The
requirements are [options](en_Breath%20of%20the%20Wild.md#the-sealed-sanctum).

<!-- ![The sanctum is sealed](../../docs/images/sanctum-sealed.jpg) -->

## Region borders

With the `region_lock` option, the regions open one by one. Near a region not yet in the logic, the fog thickens over
its last 25 m and the game's "You can't go any farther." stays on screen. Link who sets foot inside is sent back to
the last safe ground outside, his life kept, and the journal says what opens that region.

<!-- ![The fog at a closed region's border](../../docs/images/region-border.jpg) -->

## DeathLink

With the `death_link` option, a death received is first announced in the journal, then Link dies as from a lethal
blow. Mipha's Grace and fairies still save him. When Link dies, the other players read what killed him ("Player was
slain by a Bokoblin").

## Traps

A trap strikes when it is received, at a safe moment, and the journal says what it did. The cuccos, the Yiga and the
storm's lightning can kill. The nine traps are described on the [game page](en_Breath%20of%20the%20Wild.md#traps).

<!-- ![A Cucco Swarm trap](../../docs/images/trap.jpg) -->

---

Next: [the game page and its options](en_Breath%20of%20the%20Wild.md).
