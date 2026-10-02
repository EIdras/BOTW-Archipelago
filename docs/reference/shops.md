# Shops and stalls

With the options `beedle_shop_items` and `stall_items`, Archipelago items are sold in the game: by Beedle, from
his list, and on the village stalls, as a medallion laid among the goods. Buying one checks its location. Everything
is done in the game's resources, built for each seed; the client only reads.

## Beedle's shops

- **Option** `beedle_shop_items` (0 to 2, default 0): the number of Archipelago items at each of Beedle's 16 shops
  (the 15 stables and Kara Kara Bazaar). Up to 32 locations, IDs 154 to 185, named "<place> - Beedle Item <n>" (world
  schema 3). Prices are drawn by the seed, 20 to 200 rupees in steps of 5, and written into the slot manifest
  (`shops`). Names, IDs and flags have a single source,
  [`botw_client/shop_catalog.py`](../../botw_client/shop_catalog.py); `data/locations_master.csv` and
  `botw_world/data/locations.json` carry copies of them, checked by a test. Places are read from the map units (the
  nearest `LocationTag`) and named from `LocationMarker.msbt`.
- **Resources** ([`botw_patch/shops.py`](../../botw_patch/shops.py), called by
  `tools/build_resources_from_source.py` when the seed has shop locations; without them, the pack's files are
  unchanged):
  - one actor `AP_Shop_<id>` per location: a declaration cloned from amber, the seed's price, the Archipelago icon and
    3D model (`Model/AP_Item_00`), a name and a description made from the placement in the 7 EU languages (the
    grammar code of a vanilla name is copied in the languages that have one); the name is cut at 30 characters, the
    description holds 4 lines;
  - the stock sheet is reordered: **Archipelago items first**, then arrows and arrow bundles, then what remains of
    insects and materials; stock 1; each Archipelago item carries `ItemLookGetFlg`, so it is listed as long as
    `IsGet_AP_Shop_<id>`, a saved bool true from the start, is not cleared;
  - Beedle's flow (all 16 copies): back from the buy list, for each Archipelago item, `HasPorchItem` →
    `Demo_SetGameDataInt APShop_<id> = 1` → `Demo_FlagOFF IsGet_AP_Shop_<id>` → `Demo_DeletePorchItemInEquip`;
  - the saved s32 flags `APShop_<id>` are declared (GameData and save format).
- **Client**: the `APShop_<id>` flags are locations like any other (live s32 reads; a flag absent from the pack is not
  tracked). Only the seed's locations are scouted and sent. When the buy list is open (`Shop_ScreenType` 1) on an
  `AP_Shop_<id>` (two identical reads of `Shop_SelectItemName`), the client hints the Archipelago items of that shop
  (`create_as_hint=2`), once per location ([`botw_client/shop_state.py`](../../botw_client/shop_state.py)).

## Village stalls

- **Option** `stall_items` (0 to 28, default 0): that many of the 28 locations (IDs 186 to 213, world schema 4), drawn
  at random by the seed; a stall has 2 of them, so it gets none, one or two. Seeds generated before it had
  `stall_shop_items`, 0 to 2 on every stall (still read by `tools/play_seed.py`). Single source: [`botw_client/stall_catalog.py`](../../botw_client/stall_catalog.py); resources:
  [`botw_patch/stalls.py`](../../botw_patch/stalls.py), called by `botw_patch/shops.py`.
- **Stalls**: the 14 that sell consumables through `DisplayShop:Multiple` in their own flow and have an item on sale in
  several copies: Rito Village, Gerudo Town (fruit, arrows, materials), Kara Kara Bazaar (fruit), Korok Forest
  (mushrooms, general store), Goron City, Kakariko Village (arrows, general store), Lurelin Village, Tarrey Town
  (arrows), Zora's Domain and Hateno Village. Left out: armor (mannequins, another mechanism), stalls whose items are
  all single, and four merchants without `DisplayShop` in their flow (Kakariko 006/012/013, the Gerudo Town canal).
- **Objects replaced**: among the items sold in several copies, the most repeated first, never the last copy. The
  stall keeps everything it sold (in Kakariko, for example, 1 arrow out of 10 and 1 fire arrow out of 10).
- **Places and regions**: the nearest `LocationTag`, named from `LocationMarker.msbt`. Region: the nearest tower, the
  rule used for shrines.
- **Map**: the object becomes `AP_Shop_<id>`. Its HashId, position and links (`ForSale`, sold-out tags) stay the
  same. Its rotation is set to the merchant's yaw, so the medallion faces the customer.
- **Respawn**: a new `LinkTagAnd` without inputs, `SaveFlag = IsGet_AP_Shop_<id>`, creates the object through a
  `Create` link. It is the vanilla pattern of 956 tags of these maps (for example `BalladOfHeroGerudo_Activated` →
  `Create` → `Area`). The flag is true until the purchase, so a bought object is never created again, blood moon
  included. The tag's HashId is the crc32 of its name, checked unique; its `SRTHash` is derived from the name (the
  vanilla computation is unknown, with no expected effect on a tag).
- **Price**: a stall reads `Item.BuyingPrice` from the actor's `GeneralParamList`, while the list reads `ActorInfo`:
  each Archipelago actor has its own `GeneralParamList` with the seed's price.
- **Purchase**: recorded as at Beedle's, after the merchant's `DisplayShop` event (checked on the 14 flows).
- **Pack**: the maps are written under `aoc/0010/…` at the root of the pack, with their size counted under
  `Aoc/0010/…` (`tools/build_resources_from_source.pack_path`). Cemu reads the `aoc/` folder of a graphic pack.
- **Not done**: hints on sight for stalls. Beedle's come from his open list; a stall has no list.

## What the game does (measured)

### Shop data

- **92 actors** have a stock sheet (`Actor/ShopData/*.bshop`), **78 unique sheets**, **68 with a `Normal` table**
  (what the merchant sells): **275 entries**. Per entry: `ItemName`, `ItemNum` (quantity in stock),
  `ItemAdjustPrice`, `ItemLookGetFlg` (conditional display), `ItemAmount`. Other tables (`Cooking`, `Compound`,
  `Rain`, `Ancient`…) are stock variants or buy-back.
- Two shared flows do all the selling:
  - `DisplayShop`: 3D stalls, the object is laid out and chosen in place (`Demo_ChangeChoiceNumFor3DShop`);
  - `Yorozuya_Kaiwa`: selling from a list with icons (Beedle, `Npc_TripMaster_00..15`, the monster parts merchant…).
- Each merchant enters the shared flow **from its own flow**, passing its identity (`Self`/`Self2`) and sometimes the
  stock table (`TableName`). Beedle's 16 event packs (`Event/Npc_TripMaster_00..15.sbeventpack`) each hold an
  **identical** copy of the flow `Npc_TripMaster_00`, which calls `Yorozuya_Kaiwa:Zucchi_Konyu {TableName: Normal,
  Self2: Self}`; each appearance has its own sheet `Npc_TripMaster_k.bshop` in its actor pack.
- **The sale is a native action** (`Demo_SellItem`, `Demo_ShopFixedItemNum`), not an EventFlow gift: the item sold
  comes from the native state of the selection, which the flow does not see.
- **A 3D stall has no stock sheet**: each item on sale is an object of the map unit (DLC, `aoc/0010/Map/MainField`)
  linked to its merchant by `ForSale` (and by `DeadUp` to a `LinkTagAnd` whose `SaveFlag` marks the stall sold out,
  for example `Npc_Kakariko010_SoldOut`). The merchant's flow runs `DisplayShop:Multiple` for the object looked at
  (`Npc_Kakariko010`: entry `ClerkAsk` → `Event194` → `Event175 DisplayShop` → `Event174`). Objects are sorted by
  `HashId`, each with an `SRTHash` whose computation is unknown.

### The shop's state is in GameData

EventFlow action names are not in clear in `U-King.rpx`: `Actor/AIDef/AIDef_Game.product.sbyml` (`Bootup.pack`) maps
them to classes, registered in a sorted table (crc32 of the name, factory):

| Class | crc32 | Factory | Constructor | Vtable |
|---|---|---|---|---|
| `NPCSellItem` (sells to Link, `Demo_SellItem`) | `0x0E0CADB9` | `0x02ABD4FC` | `0x02321874` | `0x10085E78` |
| `CheckShopSelectedItemName` | `0x104FA725` | `0x02B09AD8` | `0x02A790EC` | `0x10195A44` |
| `CheckItemShopSelect` | `0xDC704842` | `0x02B091D0` | | |
| `ShopFixedItemNum` | `0x71DD7495` | `0x02AC3D60` | | |

`CheckShopSelectedItemName {PorchItemName}` (`0x02A791D4`) reads the string `Shop_SelectItemName` through the GameData
reader (`0x02E1D5FC`) and compares it with its parameter. The whole family is in the flag table:
`Shop_SelectItemName` / `Shop_SelectItemNameJpn` (string64), `Shop_SelectItemPrice`, `Shop_SelectItemNum`,
`Shop_ItemState`, `Shop_CurrentItemState`, `Shop_PlacedItemStockNum`, `Shop_ScreenType`, `Shop_TradeItemNum` (s32),
`Shop_IsDecide`, `Shop_DecideTrig`, `Shop_IsSelectPurchase` (bool). Read while buying from Beedle:

| Moment | Flags |
|---|---|
| "Buy" chosen | `Shop_IsSelectPurchase` 0 → 1 |
| List open | `Shop_ScreenType` 0 → 1, first entry selected |
| Cursor moved | `Shop_SelectItemName` (actor name), `Shop_SelectItemPrice` (unit price), `Shop_SelectItemNum` (stock left) follow the cursor |
| Purchase decided | `Shop_DecideTrig` pulse, then `Shop_IsDecide` 1 and `Shop_SelectItemNameJpn` = **the name of the item bought** |
| Quantity | `Shop_TradeItemNum` |
| Payment | `CurrentRupee` drops (price × quantity), after the confirmation |
| End of purchase | `Shop_IsDecide` 0, `Shop_SelectItemNum` decreases |
| Leaving | `Shop_ItemState` -1, then `Shop_ScreenType` 0; name and price stay |

- The byte `0x40` before a string's text is the size of its buffer; old names remain after the final zero.
- The entries and prices are exactly the sheet's `Normal` table, in order, and the stock is live (20 → 19).
- These flags do not say which shop is open, nor its whole list: only the entry under the cursor. That is why each
  Archipelago location has **its own actor, listed first**: the list opens with it selected, and its name tells both
  the shop and the location.
- A string can be read while the game writes it: the client requires **two identical consecutive reads**.

### A sellable item

Model: amber (`Item_Ore_F`).

| Part | Where | For amber |
|---|---|---|
| Declaration | `Actor/ActorInfo.product.sbyml` (a loose file of the update, 7934 actors, `Actors` + `Hashes` sorted) | `profile: Item`, `itemBuyingPrice 120`, `itemSellingPrice 30`, `sortKey`, `tags`, `bfres`/`mainModel` |
| Actor pack | `Actor/Pack/Item_Ore_F.sbactorpack`, **in `Pack/TitleBG.pack`** | 15 members: `ActorLink`, `GeneralParamList`, model, physics, pickup AI… |
| 3D model | `Model/Item_Ore_F.sbfres` (+ `Tex2`), in `TitleBG.pack` | |
| Icon | `UI/StockItem/Item_Ore_F.sbitemico` (update) | |
| Name and description | `Bootup_<language>.pack` → `Message/Msg_<language>.product.ssarc` → `ActorType/Item.msbt`, labels `Item_Ore_F_Name` / `_Desc` | one language per pack |

- A created actor, cloned from amber, is listed and sold like a vanilla item: name, icon, price and description as
  written. It needs no model of its own to be sold, but a description needs explicit line breaks. Adding a label to
  `Item.msbt` means rebuilding its `LBL1` hash table too.
- **Bought, it goes into the pouch** (Materials tab), where it could be held, dropped or sold back at amber's price.
  The game's action `DeletePorchItemIncludeEquip` (`Demo_DeletePorchItemInEquip {PorchItemName, DeleteNum}`), used at
  the end of the Champions' Ballad to take the base ability back, removes it: Beedle's flow deletes every Archipelago
  item of the shop right after its buy sub-flow returns (`Npc_TripMaster_00`: `Event18 → Event150`). Deleting an item
  the pouch does not hold does nothing.
- **Beedle restocks at every opening of his list**, so a bought item comes back. `ItemLookGetFlg` lists an entry only
  while `IsGet_<item>` is true: each Archipelago item's `IsGet_AP_Shop_<id>` starts true (its initial value, also taken
  by a save that does not know the flag) and the flow clears it at the purchase, before removing the item. The item
  then leaves the list for good.
