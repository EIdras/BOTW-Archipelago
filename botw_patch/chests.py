"""Chests that hold an Archipelago item (the world's chest_sanity: ap_items).

Every chest of Hyrule's map units that is a location of the world
(botw_world/data/chests.json) holds an item of its own, AP_Chest_<nnnn>, in
place of its own contents (the others keep theirs): the chest opens as usual
and shows the item, with the Archipelago model and icon, named as the seed says
(the item it sends) or, without names, as a generic Archipelago item in the
game's language. The numbers follow every chest's flag in order: the same in
every seed, so that the map units do not depend on the seed, only the texts do.
Its saved flag MainField_<chest actor>_<HashId> rises once the contents are
taken (at the end of the opening; for a wooden chest burnt open, when what it
dropped is picked up), and the client counts it as the chest's location. A
chest burnt with its contents left comes back with them, the flag still false.

  * AP_Chest and the numbered items are declared in ActorInfo and made as the
    shops' items are (botw_patch/shop_items.py): actor packs cloned from amber,
    the Archipelago model, which the shops' stage adds too when the seed has
    shops; one icon file, AP_Chest's, which the others name as theirs;
  * in the DLC map units (served loose once AocMainField.pack is emptied, as
    for the stalls), each chest's DropActor becomes its item and nothing else
    changes; units another stage already rewrote (towers, stalls) are built on;
  * the Divine Beasts' chests that have a flag (MainFieldDungeon_<actor>_<HashId>)
    are numbered after the shrines' (beast_numbering) and hold theirs too: in the
    DLC's Pack/RemainsXXX.pack (about 7 MB each, the game loads them: only they
    have the Champions' Ballad's links), both static units, which the game
    loads one or the other of;
  * a quiet entry of OperationGuide per item, APChestRemove_<nnnn>, takes it
    out of the pouch if it is there (Demo_DeletePorchItemInEquip removes one
    item whatever DeleteNum says, -1 included): the client requests it when the
    chest's flag rises, and at connection for every chest already open.

Left as they are: the Master Mode chests (IsHardModeActor, absent from a
normal game), the One-Hit Obliterator trial's (IsIchigekiActor) and the three
gamble chests of the Gerudo Desert, which have no flag, as Vah Ruta's five of
Set_Dungeon_RemainsWater. The shrines keep their maps in Pack/DungeonNNN.pack
(the base game's, then the DLC's), with everything else of the shrine (models,
collision, navigation: about 7 MB each, none of it elsewhere, 910 MB for the
base game's): their chests are numbered after the field's (shrine_numbering),
the base game's are locations, and they keep their contents, unless the slot
asks for shrine_chest_items: then this stage only declares their items, and the
shrines themselves are built once, shared by every seed (botw_patch/shrine_chests.py).
The catalog says which numbers hold their item (held()), for the client to tell.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile

import oead
from evfl.entry_point import EntryPoint
from evfl.util import make_rindex

from botw_client import regions
from botw_patch import traps
from botw_patch.delivery_flow import QUIET_EVENT_INFO, QUIET_FLOW
from botw_patch.events import graph_snapshot, read_flow, write_flow
from botw_patch.resources import ResourceBuilder, canonical, digest, unpack, vanilla_digest
from botw_patch.shop_items import (MODEL_PARTS, MSBT, ApShopItem, add_declarations, add_item_texts,
                                   check_model, clone_actor_pack, model_size, rename_model,
                                   wrap_description)
from botw_patch.stalls import AOC_PREFIX, MAP_ARCHIVE, TABLE_PREFIX

ACTOR = "AP_Chest"
ENTRY = "APChestRemove"
ACTOR_INFO = "Actor/ActorInfo.product.sbyml"
TITLE = "Pack/TitleBG.pack"
BOOTUP = "Pack/Bootup.pack"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
EVENT_INFO = "Event/EventInfo.product.sbyml"
CHEST_PREFIX = "TBox_Field"
LEFT_ACTORS = ("TBox_Field_Gamble",)
LEFT_PARAMETERS = ("IsHardModeActor", "IsIchigekiActor")
CHEST_COUNT = 1190
# The chests of the shrines (Dungeon000-136: the base game's 120, then the DLC's),
# numbered after the field's; the DLC's are not yet locations.
DUNGEON_PREFIX = "TBox_Dungeon"
SHRINES = 137
BASE_SHRINES = 120
SHRINE_CHEST_COUNT = 205
# The Divine Beasts' chests that have a flag, in the DLC's packs (Pack/RemainsXXX.pack,
# which the game loads: only they have the Champions' Ballad's links), after the shrines'.
BEASTS = ("RemainsElectric", "RemainsFire", "RemainsWater", "RemainsWind")
BEAST_CHEST_COUNT = 35
BEAST_FIRST = CHEST_COUNT + SHRINE_CHEST_COUNT + 1
# The European DLC's packs (vanilla_digest), whose static units the stage changes.
BEAST_PACK_HASHES = {
    "RemainsElectric": "fee1380f8811408e0e0a77122ed7cae12dc0ee52789e4c3db99e0be360d2bed4",
    "RemainsFire": "da5dd532cd9d230115fd64f1672eca0d1760a3432b5ef10e6a73612e919567b5",
    "RemainsWater": "1b449d899313bc31f1b32c7cbd418be89c75d7ce336881cc714e0e9acecfd542",
    "RemainsWind": "99a01b25edc52be6241dc8f5cc475a11fe81e5ca79b09679b278d4dc9363a2ed",
}
# The numbers whose chest holds its item (first, last): the field's and the Divine
# Beasts'; the shrines' between them keep their contents, but with shrine_chest_items.
HELD = ((1, CHEST_COUNT), (BEAST_FIRST, BEAST_FIRST + BEAST_CHEST_COUNT - 1))
SHRINES_HELD = (CHEST_COUNT + 1, CHEST_COUNT + SHRINE_CHEST_COUNT)
# The Master Mode chests (IsHardModeActor: absent from a normal game, each on the
# platform of an Octorok balloon), with the world's master_mode: numbered after the
# Divine Beasts', in the field's map units and F-4_Static (MASTER_MAP_HASHES).
MASTER_CHEST_COUNT = 118
MASTER_FIRST = BEAST_FIRST + BEAST_CHEST_COUNT
MASTER_HELD = (MASTER_FIRST, MASTER_FIRST + MASTER_CHEST_COUNT - 1)
# The world's (botw_world/catalog.py): a chest's location id is this plus its number.
CHEST_ID_BASE = 10000
# The world's chest_sanity value (botw_world/options.py) for chests holding their AP items.
AP_ITEMS = 2
# The chests that are the world's locations, by number (tools/chest_locations.py).
LOCATIONS = Path(__file__).resolve().parents[1] / "botw_world/data/chests.json"
MASTER_LOCATIONS = LOCATIONS.with_name("master_chests.json")
# (name, description) per language: its own, else its European counterpart's.
TEXTS = {
    "EUen": ("Archipelago Item", "An item from the Archipelago multiworld. It has been sent to its owner."),
    "EUfr": ("Objet Archipelago", "Un objet du multimonde Archipelago. Il a été envoyé à son destinataire."),
    "EUde": ("Archipelago-Gegenstand",
             "Ein Gegenstand aus der Archipelago-Multiwelt. Er wurde seinem Besitzer geschickt."),
    "EUes": ("Objeto Archipelago", "Un objeto del multimundo Archipelago. Se ha enviado a su destinatario."),
    "EUit": ("Oggetto Archipelago", "Un oggetto del multimondo Archipelago. È stato inviato al suo destinatario."),
    "EUnl": ("Archipelago-voorwerp", "Een voorwerp uit de Archipelago-multiwereld. Het is naar de eigenaar gestuurd."),
    "EUru": ("Предмет Archipelago", "Предмет из мультимира Archipelago. Он отправлен своему владельцу."),
    "JPja": ("Archipelagoのアイテム", "Archipelagoのマルチワールドのアイテム。持ち主に送られた。"),
}
# The European update's files read here (their other versions: regions.inputs).
INPUT_HASHES = {
    ACTOR_INFO: "07f440eadb27109f9fa6511a12a9f6c8b76047ca539b24b32a301ba27183e6a2",
    "Pack/Bootup_EUde.pack": "d68f8d06da6542d7bbb5c4437ce291306a53a053e5860e427ccae0664b352aaf",
    "Pack/Bootup_EUen.pack": "e6e7593fb7e5aba3858fa3ff6d646585dd08d83562551ed392d28a9515dfd5f8",
    "Pack/Bootup_EUes.pack": "8a4dbf21d7ea474d2673d8d7d2c55a8d93d5831fb621b501fc5e73afb235eff0",
    "Pack/Bootup_EUfr.pack": "8597171f9053fad2da85584cb8f9496bf3ffabecb5b27d61e517b3ca0066cdb7",
    "Pack/Bootup_EUit.pack": "fa768b456a3b078b4588e25c16e4b623cc6d27da67552de907425ad3958b5632",
    "Pack/Bootup_EUnl.pack": "2e3472118604e27bb026650293ac94f340af7530131ce8f4fda6deccb28c264c",
    "Pack/Bootup_EUru.pack": "baccba9b2ea127eb94024a506beacf532a886d7ce36229e58e20f3f066eb4eaf",
}
# The DLC map units that hold chests (Map/MainField/<unit>.smubin), European hashes.
MAP_HASHES = {
    "A-1/A-1_Static": "b5cec2d798248c748fb030f37c355a42216e7b0f1944c58189f865f411fa14c9",
    "A-1/A-1_Dynamic": "c930729e52995a377a5025a51c10e5b2a598ec356141163d13da62e0d564cdd1",
    "A-2/A-2_Static": "2b200d3ffe2cb96a62be2a161fe951fbc44bb9a720fe1f1c1ce068cb3499325e",
    "A-2/A-2_Dynamic": "84675f068da932bfa780eda3a5ed66cb4ce393e22b1d5b4394db3c76ededf015",
    "A-3/A-3_Static": "7f31509988ff375a4d09bca215a6a1a4e7a2fbc239ed8eb03f19012d1e2a5f5c",
    "A-3/A-3_Dynamic": "9c2132b24376c127333904306d1af8bb632d59a6c74a5fdff0f77caa29ece45e",
    "A-4/A-4_Static": "4d5ea8b0b73217b18b7c030f1ee3c5251650dac251ab2239fb4e29967bb27504",
    "A-5/A-5_Dynamic": "e9bdda64eb2606ee716fb26b8d04cdb7a4c2fef8f9b07bfccc0896d5bc188c10",
    "A-6/A-6_Static": "e385609e671b4b30085f0c43a230f106329c9ffc6b32f35f699e13d300133a59",
    "A-6/A-6_Dynamic": "7f74daf79870b00d46e40e5f6ebbc8d4a46f69651061f68f684b4f7b7821bfe7",
    "A-7/A-7_Static": "28853744f1a60dbeecd11fd571b499c4dfc1cee0a7d79c11b51a270dc2180ab8",
    "A-7/A-7_Dynamic": "a3263d904885849875b993fef84cf70d19feff1c244ed96ffd544b5eb0c73e3f",
    "A-8/A-8_Static": "371b39ec899a1552c7b55b7d1fa5571978b8eb0cc30d9eb83ec049b36ed38046",
    "A-8/A-8_Dynamic": "d692471f693074a62bf55300806b721a71a1368913803b09157cd5acb9da0465",
    "B-1/B-1_Static": "5a6b4d9501456985c1816dd6709cee6dde34749b6073db3ad912961f16192adc",
    "B-1/B-1_Dynamic": "a37d23809e55a2ae555236e38b42696e50626c2c71d8243179ce39c0c75b43db",
    "B-2/B-2_Static": "7b74ad1effcc87d981588b317c75cc2f92f0a6fe88bf0958f09749bcd5345fd9",
    "B-2/B-2_Dynamic": "f84c38738adcf88c9b2b3f7f8e4de6500f0ee690b1ab65c4d517fc7fe4b49e10",
    "B-3/B-3_Static": "7c3e86af0c9e509f72440bdde0720e2050aed4591aca985268315d07dc4139b9",
    "B-3/B-3_Dynamic": "51b5523d03abeb5e25e4daed52cb28d473917d6301898bc271b258d9fc2a1444",
    "B-4/B-4_Static": "9bbd64ff2bf3063a1607e4b0190e60ee1a5348d128326f2dfe182b49686dacf6",
    "B-4/B-4_Dynamic": "e9f529e86b6f1c8165e271e35888c2f58029c80e7ae09a991de316c250eae3d2",
    "B-5/B-5_Static": "7c2fe30d865f2dad399f8b4b99823d738552ec4539818e5d598e87fbb6650730",
    "B-5/B-5_Dynamic": "02e660a7f5ad8030b6080207bc471b2a1a552bd42176a7cd1c32718e414d6cca",
    "B-6/B-6_Static": "c1ace4d3282293650d4b3fa43dc1564094e4432c77b8e9ab7069ca28860a7cac",
    "B-6/B-6_Dynamic": "8af4658291e62220c20e91e69ed2e99548d66b20a0eaf60f78ada0931e3fcfce",
    "B-7/B-7_Static": "a92a406e27fa0226c9bd43c462ff2982040f9d25bff65785aa024400d22f533f",
    "B-7/B-7_Dynamic": "88e4758200bfd002c05fef43a516f7e2fc455ee0c9bb0a4c441ec35fcf0c6eb9",
    "B-8/B-8_Dynamic": "6c562daa75ae7a6782d8877bd45c1491e09235e6394706d78e9068b236f8916d",
    "C-1/C-1_Static": "d9b8c8be3e866643a6d36e652936768302b5e3f890dea09d503969906d16fe79",
    "C-1/C-1_Dynamic": "1ae0d27eda05e2c3742bf7d26f28ebb89c020de70348f1a2c58e0d75d19d0115",
    "C-2/C-2_Static": "dbd7a7f2a227bdca41f7a30ef9528e8c11dc19e8432b002b3ec01fa3b6ce1a0f",
    "C-2/C-2_Dynamic": "9b8e2d0e6731f1f95bfc191cf5a11ca10ced09c10aa746f9fc6b0072fa576cfb",
    "C-3/C-3_Static": "a934247f7fbfcd8075c3040b46d00b29e2f2a96484ea56a56ed2714e37aa6ed0",
    "C-3/C-3_Dynamic": "0b0a6c6d279dafd62375471245f696a671c3fdc3290b7f649096f294c43dd648",
    "C-4/C-4_Static": "ff44a50847c46ba722001a4305783d2e916143364b5f4d865405e200cc23d55a",
    "C-4/C-4_Dynamic": "44df228aafb902e4058e41f9c5c10ef03524a043ee2f4560c0487acac711ee7e",
    "C-5/C-5_Static": "2154a49d81922fe10d2cda90fcacfbac3971904a29ef3441b0e2af0066f9b764",
    "C-5/C-5_Dynamic": "5f38dc793f5c4298caf9667dafb228d314b96eb9e04a64d32238f860b735b075",
    "C-6/C-6_Static": "33c89ecbbb9d82c42674959c24763afe1262244af54d0d554dfe4a3d76422c47",
    "C-6/C-6_Dynamic": "0bb32638e04b71945075a38a2b9cea4a1adffd46bad27504e6380bbc63a507c1",
    "C-7/C-7_Static": "7ed28f66b9b7283cc6f70c761a926ad556a027a1e43a2cc2daf0e970e7bf1807",
    "C-7/C-7_Dynamic": "c92a621317ef5fe05aa25269411162280f075937f584d8c2ac33877da4b25e4b",
    "C-8/C-8_Dynamic": "e8ef1d628c273228a5cac2e7432cb7509fe20c498214f18e23e5419430d1b6b2",
    "D-1/D-1_Static": "9a91051634efb30dbc07bb5cd75d4e6b604cd8311d78c654c96614051a21c419",
    "D-1/D-1_Dynamic": "726cd20cd1f5bec5fa002f993e1ff8b019ff5463e183f9d05adaa254b9befd1f",
    "D-2/D-2_Static": "5d8b8391fa3cecaa5fac9059de94f22fcefcbea36e128df81061fe60ad5cdd92",
    "D-2/D-2_Dynamic": "038e3282d438eb8bc0a1b580e71bc39ad6723e0aeec9f59bc85a909a0a8cdf2e",
    "D-3/D-3_Static": "3c5fbb07200e9cad78288fc0927e2586588528ad4f88fed2935b2e9ae41d0516",
    "D-3/D-3_Dynamic": "591f09a19444aeac831b261763be6ef00d66dc439a48708b4290469ca2a1e1ce",
    "D-4/D-4_Static": "4e3496b57dc4ba7e5bea6580033b7ddd17e21e7f970a0a7b0cdfbf5adad89226",
    "D-4/D-4_Dynamic": "4f4a71d4ffb6dcc78a8f950618753c7bca25bfb45f2710d4089242db6e3dcef7",
    "D-5/D-5_Static": "1df5258504832980e79c956d2a0a9a1fc7f925e1e7c5775b538e5d4f916eecdf",
    "D-5/D-5_Dynamic": "f1c1055c2d26018f4666baaa03677645cb04ab79dfec5e77d7c70c271ba1f941",
    "D-6/D-6_Static": "1a7c18b297367e911cc4f504d3a2c04089693543fbbb793974a7e2b766c4f017",
    "D-6/D-6_Dynamic": "a971d8d236dbbcbd126533776f65bafc2ed5f63eee6721847f89aa369e3e923d",
    "D-7/D-7_Static": "6fe0d5b1930ba8a7d67a3cc37856c8bd59ecbe2ebf3d7e76fa2d675401c15070",
    "D-7/D-7_Dynamic": "70f51a837033968bd27862db13d1cdd8caae915d2e15ce12df528d9ebd983f14",
    "D-8/D-8_Dynamic": "37612ae02a8f5732af48d18c229cffd8e282e12b8137db935097bd3b5cdefb1b",
    "E-1/E-1_Static": "da55e18011258e085f929475c23f49e2105092aea81c8316cbb2104c5e38eb61",
    "E-1/E-1_Dynamic": "5388104729b877f6eb84917a89bd97afbfb221011371d2aa6454b6552722e9df",
    "E-2/E-2_Dynamic": "f4af314e5d686818b289ef892410afecc3249faeff377d828d90d37343153608",
    "E-3/E-3_Dynamic": "e1e8e9ab1d044b3d6cd28e8e8174251997eeafdc0fabb41cfc5f75c00fd4f390",
    "E-4/E-4_Static": "aa1700609c31a89c171e07d0cbf2b164e20bf0b73b15f725ea235b5c27c10c07",
    "E-4/E-4_Dynamic": "14fe16298541891969bff5bc74a9d10b078dfd1f98a5107bd8ad09c399c79875",
    "E-5/E-5_Static": "f1966d89a9cd4d1338a757fd665d1277637c041da7021f266fabd4069faef98c",
    "E-5/E-5_Dynamic": "3a8b960189a3c2cf864d2df25d32de4ccc21096246eeba44b790426daddb44f9",
    "E-6/E-6_Static": "7fb769d6bf2fc480d81cb101fc72470f70232721493ab109aec539e02e32102c",
    "E-6/E-6_Dynamic": "1bf42125767423024d33951b741f67721fb77b667e3e6bc68f7fffdc2cd34368",
    "E-7/E-7_Static": "9580d3c7edecc6f8b1dd8c149c2e74b3b37dd42ab41623c70d6e439cef1939d7",
    "E-7/E-7_Dynamic": "405ead6bf62411bd0cde29c45be31833d7babcf64cc9566014c8f46306b28d3d",
    "E-8/E-8_Static": "e3d24c3583319f53cf1768550727447131d31fc40d5f75f8f82193e746d30285",
    "E-8/E-8_Dynamic": "e5887d10f59ee1b0126cced0a169efb25d51779eb32fb318b61b99a97a2fcd8c",
    "F-1/F-1_Static": "5b6d775d95fda250eca70688af83afc985b781b99a0e82781d7621975f618117",
    "F-1/F-1_Dynamic": "43f5f860b4978741a6d084f9b34814da568f2968c38051515e7047093e0d895c",
    "F-2/F-2_Dynamic": "a8c87230c2cd0e3fced6f33ae6cd8012941660b86efed56f0b1ecb9198d8cee9",
    "F-3/F-3_Static": "470bff5bf7d31fccc0f07172491960824cc448801b6a229ef4ea6b46a575732d",
    "F-3/F-3_Dynamic": "996281f08f53124a0911080bd8a8428a995ca58476f49c25114384fede93e9c0",
    "F-4/F-4_Dynamic": "80ea73cab1f6a5045081886be1f65c7695beb6919740daf9fb09dc18f670d82f",
    "F-5/F-5_Static": "b54e80af2644a51ba1ba8685718be25256a5f728339153e5a9100c93f3ed41e1",
    "F-5/F-5_Dynamic": "b5e29fd8e7638dbea4c697ce43446985dd763c57e397ca0eddbeea0def275582",
    "F-6/F-6_Static": "53f773ab2817da9ccc3dd5753b7a0845dac528c3ca36be7fb193454f58d410a5",
    "F-6/F-6_Dynamic": "68c565262154dc339395a63f6cec1860a0828957c9ed12192f6a8248e7ea714f",
    "F-7/F-7_Static": "958a5872a39c9f3af34d0cd0e0ef450bb5503d801dc65a28b75fa7409b4f52e5",
    "F-7/F-7_Dynamic": "a2216cc488f663a5c45836f0bde8e035f95770dcb993b5cb85eb844cb9e9951e",
    "F-8/F-8_Static": "9a944a289d0d4bdc585aa75985b14fe557d2f3a159f300559fd06f8109fe53a4",
    "F-8/F-8_Dynamic": "568f03e09bedaf03abc070d5cb71874aa6a24ff5624cf2d3e7e934c535a1b7fb",
    "G-1/G-1_Dynamic": "1213dc1cebabe38b404e714a67a81e8b5766a2d20f874fa9a2722918a7e842be",
    "G-2/G-2_Static": "a793d3795c27ec406152852d382423dd5d3e72afb2ece5c37ebcf52bf74b346c",
    "G-2/G-2_Dynamic": "51fd94e6082515f595dec795fb74dfcb8d8388293207f369d183c17c71bb06e9",
    "G-3/G-3_Static": "d3ab2c964638bf4fc406f4075f498fd18a7e3f381aeb68a410cb9b6b2cda29df",
    "G-3/G-3_Dynamic": "97efa8197eb30970efb101486599e78a75341abeec0806ea7497a9728a168e0a",
    "G-4/G-4_Static": "bfe5184a95431693cc19a458853a654830a269f52ac9049d7fc8bcb993475a3b",
    "G-4/G-4_Dynamic": "016a13a0498f598d02096c46b93001e3fd690e51fa57962627eb9027b1fc08b9",
    "G-5/G-5_Static": "ab69fba1ae647dfd5fc000134908ca65b8f89d5bac9c1df29ac34cf4265d6cec",
    "G-5/G-5_Dynamic": "2d91ef2d14dcecf969cc3df9cbc7a8906e6873e3c7b515b1818525bedbad64eb",
    "G-6/G-6_Static": "2aebf7fd5192aae8b4cfce6ef9a4eb201445917a762c06dd6c2ac976e26addb3",
    "G-6/G-6_Dynamic": "2847b469922a3e72282faa2630f2c030c518854d98f6979fec9c812ff5f300f0",
    "G-7/G-7_Static": "432791cdf16c7d9b035255469f03f6c429426b10ac5a44d9ca2cf4fff2a4ee6d",
    "G-7/G-7_Dynamic": "abff7a42e88692edd377483abea339bd260424d4deabf9bf0fb8906afb7fa177",
    "G-8/G-8_Static": "8e76a9a37a6234ec239aeb4063bd38e6d5f05a002e1ab4ddf0e5a0587d8d7ef4",
    "G-8/G-8_Dynamic": "efa7345c76c8047b99c06251fd8f7ccdb5f2255ac6a55949e4237ad0da5f9ab8",
    "H-1/H-1_Dynamic": "b4070bcbfdf4a1f7ce0c9bba180d518242299ca6c9387197d94c93e900d907ac",
    "H-3/H-3_Static": "7266574584182bec51f98506f5996bb943290b13f892ff53296e4c018b166f21",
    "H-3/H-3_Dynamic": "e90901b28dc0fa45b7deeba197170b7ebd1990fb6f165caf40a4df3e3432f901",
    "H-4/H-4_Static": "db3730d8f85a618aa3fd7146dde65134e1bdc233629540c1f2012885bed157ef",
    "H-4/H-4_Dynamic": "efce8374352273066bdc77932264fc7a6440253238529ede7fe00814639b045b",
    "H-5/H-5_Static": "448cab0f30a35370756045dc96f29aaf230384f57cc8cccb8f5ba859e31211a1",
    "H-5/H-5_Dynamic": "4346decdcbb4f5b3e498e7881f5c8146401d825136512c665328ad8cd15a2348",
    "H-6/H-6_Static": "10088863cebad4056282e0de3c419aa8349e2f2af72698e5ae19dee39a1c2b7e",
    "H-6/H-6_Dynamic": "2f655b85678436372555ff70fd671eff91d80409d9a0349e50adb0289dad7ea7",
    "H-7/H-7_Static": "e25fca97c455da6d1912b9766d567b0214acb52d3d01165af089678d184213ab",
    "H-7/H-7_Dynamic": "3b1c6bf7cf7ea6eb1525aac2144014ddef6c691b1fa0689fa496bf7f0862674f",
    "H-8/H-8_Static": "641b827e4e3d28e9373c2bee205959c3ce9c954c60264d69717581c26f7848aa",
    "H-8/H-8_Dynamic": "7541a7ba05714af49f2505107ffbdca6de6c1a564ce6f6a44e80a2e16ee75ea5",
    "I-1/I-1_Static": "2bc95ebb8527af8645a7ff5a8f65ba73f0b08305b0c1a0430cb8856a1a66ca89",
    "I-2/I-2_Static": "eefefdfc49a69821ebd72ecc6616521b3687ecd50cf877f24e9ba34383a213ed",
    "I-2/I-2_Dynamic": "bd0cb1d66e9c72cf2881d7bf2cd23ad1f99b6b6a4345073c8cedb549423e2976",
    "I-3/I-3_Static": "d2fc9160bba05cb95a1b083cdf873de7d7d74b0025fe178768ac6338830ab5cd",
    "I-3/I-3_Dynamic": "ded671f6b9acbd701149a20b328e6a12ce7607bf9ea7aac4b0fdaa39ee547b50",
    "I-4/I-4_Static": "6cadc2c717023be64311738ffe022abd1a8867f81c2fab2c8babf50e082b6552",
    "I-4/I-4_Dynamic": "384efb7a899665c91b420cbac4175ddeef9b55f241811636b5cde4a131f5d590",
    "I-5/I-5_Static": "4307a5c5efbd1e67450af485568334c02b8599f1349dbe796cf2c5abbeac9b99",
    "I-5/I-5_Dynamic": "f301734b0516e1cad1974b3d3bb3afaaa3932ef3bde08e4245b4c87109d745a9",
    "I-6/I-6_Static": "33529362d86761645e0290c057c6df69f075b477b535cc0260d5af1cb51701aa",
    "I-6/I-6_Dynamic": "4a071eb2ead5623f74e7ea7fb53e16c59745074e674ed3d8c4f0c6752aaacef4",
    "I-7/I-7_Static": "0d8808b7eb5e7297bbe027e671513733e5d379169f96396bd467269416638ef8",
    "I-7/I-7_Dynamic": "f585466511b660ef7980a9c151cda6b2bf9b7503e4d3fd29dc2c065eb3f7359b",
    "I-8/I-8_Static": "87055def43d0eee693b4986111fe342f45b86cf30e22cc6dba1ec596eb543857",
    "I-8/I-8_Dynamic": "0e56c76397c725042becdbbf87d12baa2a0f4725523402b3ddd93033fa946deb",
    "J-1/J-1_Static": "d19217bd165beb27a10fa90c4799a934a4fe316ba3f9fe4d2fe4b1d8e09eaa23",
    "J-1/J-1_Dynamic": "169998a15637390d17fa03836665df4a7ab57c3d3aaccef057d9ea4e3e2baabb",
    "J-2/J-2_Static": "a15eef313ac0121702a8e427d342c45cc92515e6099c4e0827830b2dbe4ef782",
    "J-3/J-3_Dynamic": "11274d773828e1bfc62da56e6a431a1c44077d79d9241ab766c75b31c75ceb11",
    "J-4/J-4_Static": "955e7b217543eb52c4bee7d3c5894a8d505995eb7dbb66ed906542cb3ddd3e52",
    "J-4/J-4_Dynamic": "131f02f1e8a64385d1d6389289fff887f9625cb340c2532ce196fb5f82a39b29",
    "J-5/J-5_Static": "2882721c502284bdcfedd1bfcb4ea85bebb1ce2b32c967129af267792c4ba968",
    "J-5/J-5_Dynamic": "5cae93ddfd757e08f96a1803bde01b8034899892ec0a63015f40553abc404a63",
    "J-6/J-6_Dynamic": "c791247c0d35f7216b5087e3c2ae0d3caa94a8b044b2ba8e15101a18e59234fd",
    "J-7/J-7_Static": "68f81104e5e3e29db1b9b758f7e530194ec6e8e8b6c7e57d97a39b1d0965a1e6",
    "J-7/J-7_Dynamic": "cc17f0bc2073a6b3a8871976e95b1a371ac92a25ce9a379d2f1aabb31deb6ff6",
    "J-8/J-8_Static": "ebe20aa32e60cc31d5506abd9e6b02acc31a1b8ba2cde2e9db5a80278340a9e9",
    "J-8/J-8_Dynamic": "dcea0ec111517121cb64df6efd41575fe9bc0c414b3970cc9534afd6faedab08",
}
# The unit holding Master Mode chests but no other (European hash).
MASTER_MAP_HASHES = {"F-4/F-4_Static": "55ab7975b1e7b185d6c322a9fa15d850c73a75beed8968a4b08eb26b8c50dba9"}
# Read for a seed that has them only, so that the others keep their identity.
MASTER_SOURCE_FILES = ("botw_world/data/master_chests.json",)
SOURCE_FILES = ("botw_patch/chests.py", "botw_world/data/chests.json", "botw_patch/shop_items.py",
                "assets/wiiu/Item_AP_Jewel.sbitemico",
                *(f"assets/models/ap_item/wiiu/AP_Item{part}.sbfres" for part in MODEL_PARTS))


def enabled(status: dict | None) -> bool:
    """The slot's chests hold their AP items (the world's chest_sanity: ap_items).
    With check_only, the chests keep their contents: the pack leaves them alone."""
    return bool(status and int(status.get("slot_data", {}).get("chest_sanity", 0)) == AP_ITEMS)


def shrines_asked(status: dict | None) -> bool:
    """The slot asks for the shrines' chests to hold their AP items too (the
    world's shrine_chest_items), which takes the shared shrines."""
    return enabled(status) and bool(status.get("slot_data", {}).get("shrine_chest_items"))


def master_asked(status: dict | None) -> bool:
    """The slot's Master Mode chests are locations holding their AP items (the
    world's master_mode)."""
    return enabled(status) and bool(status.get("slot_data", {}).get("master_mode"))


def held(shrines: bool = False, master: bool = False) -> tuple[tuple[int, int], ...]:
    """The ranges of numbers whose chest holds its item."""
    return (*HELD, *((SHRINES_HELD,) if shrines else ()), *((MASTER_HELD,) if master else ()))


def unit(name: str) -> str:
    return f"Map/MainField/{name}.smubin"


def flag(obj) -> str:
    """The saved flag of a chest of a map unit."""
    return f"MainField_{obj['UnitConfigName']}_{int(obj['HashId'])}"


def is_chest(obj) -> bool:
    """A chest of a normal game that has a flag."""
    actor = str(obj["UnitConfigName"])
    if not actor.startswith(CHEST_PREFIX) or actor in LEFT_ACTORS:
        return False
    parameters = obj["!Parameters"] if "!Parameters" in obj else {}
    return not any(name in parameters and bool(parameters[name]) for name in LEFT_PARAMETERS)


def is_master_chest(obj) -> bool:
    """A chest of Master Mode only (IsHardModeActor) that has a flag."""
    actor = str(obj["UnitConfigName"])
    if not actor.startswith(CHEST_PREFIX) or actor in LEFT_ACTORS:
        return False
    parameters = obj["!Parameters"] if "!Parameters" in obj else {}
    return "IsHardModeActor" in parameters and bool(parameters["IsHardModeActor"]) \
        and not ("IsIchigekiActor" in parameters and bool(parameters["IsIchigekiActor"]))


def field_chest(obj) -> bool:
    """A chest of the field, of a normal game or of Master Mode."""
    return is_chest(obj) or is_master_chest(obj)


def actor(number: int) -> str:
    """The item of the chest numbered `number` (from 1)."""
    return f"{ACTOR}_{number:04d}"


def entry(item_actor: str) -> str:
    """The quiet entry that takes `item_actor` out of the pouch."""
    if not item_actor.startswith(ACTOR + "_"):
        raise ValueError(f"not a chest item: {item_actor}")
    return ENTRY + item_actor[len(ACTOR):]


def numbering(maps: dict[str, bytes], chest_of=is_chest, first: int = 1) -> dict[str, str]:
    """{chest flag: its item}: the flags of the vanilla units in order, numbered from 1."""
    flags = sorted(flag(obj) for raw in maps.values()
                   for obj in oead.byml.from_binary(unpack(raw))["Objs"] if chest_of(obj))
    if len(set(flags)) != len(flags):
        raise ValueError("two chests share a flag")
    return {name: actor(number) for number, name in enumerate(flags, first)}


def master_numbering(maps: dict[str, bytes]) -> dict[str, str]:
    """{chest flag: its item} of the Master Mode chests (`maps`: the field's units and
    MASTER_MAP_HASHES'): their flags in order, after the Divine Beasts'."""
    return numbering(maps, is_master_chest, MASTER_FIRST)


def shrine_unit(dungeon: str) -> str:
    """The static map unit of a shrine (DungeonNNN), which holds its chests."""
    return f"Map/CDungeon/{dungeon}/{dungeon}_Static.smubin"


def shrine_flag(obj) -> str:
    """The saved flag of a shrine's chest."""
    return f"CDungeon_{obj['UnitConfigName']}_{int(obj['HashId'])}"


def holds_item(number: int, shrines: bool = False, master: bool = False) -> bool:
    """Whether the chest numbered `number` holds its item (held())."""
    return any(first <= number <= last for first, last in held(shrines, master))


def beast_pack(beast: str) -> str:
    """A Divine Beast's pack, the DLC's (under aoc/0010/)."""
    return f"Pack/{beast}.pack"


def is_dungeon_chest(obj) -> bool:
    return str(obj["UnitConfigName"]).startswith(DUNGEON_PREFIX)


def beast_units(beast: str) -> tuple[str, str]:
    """The two static map units of a Divine Beast (RemainsXXX), which both hold
    its chests: the game loads one or the other."""
    return tuple(f"Map/MainFieldDungeon/{beast}/{beast}_{name}.smubin"
                 for name in ("Static", "Static_NoGrudgeMerge"))


def beast_flag(obj) -> str:
    """The saved flag of a Divine Beast's chest."""
    return f"MainFieldDungeon_{obj['UnitConfigName']}_{int(obj['HashId'])}"


def _numbering(units: dict[str, bytes], flag_of, first: int) -> dict[str, str]:
    flags = sorted(flag_of(obj) for raw in units.values()
                   for obj in oead.byml.from_binary(unpack(raw))["Objs"]
                   if str(obj["UnitConfigName"]).startswith(DUNGEON_PREFIX))
    if len(set(flags)) != len(flags):
        raise ValueError("two chests share a flag")
    return {name: actor(number) for number, name in enumerate(flags, first)}


def shrine_numbering(units: dict[str, bytes]) -> dict[str, str]:
    """{chest flag: its item} of the shrines' chests (`units`: {DungeonNNN: its
    static unit}, all SHRINES of them, the DLC's too, so that adding these as
    locations later moves no number): their flags in order, after the field's."""
    return _numbering(units, shrine_flag, CHEST_COUNT + 1)


def beast_numbering(units: dict[str, bytes]) -> dict[str, str]:
    """{chest flag: its item} of the Divine Beasts' chests (`units`: {RemainsXXX:
    its Static unit}): their flags in order, after the shrines'."""
    return _numbering(units, beast_flag, BEAST_FIRST)


def item(language: str, item_actor: str = ACTOR, text: tuple[str, str] | None = None) -> ApShopItem:
    """`item_actor` named `text` (name, description), else the generic texts of `language`."""
    from botw_patch.shops import MODEL_ACTOR, MODEL_FOLDER
    if text is None:
        text = regions.localized(TEXTS, language) if language in TEXTS or \
            regions.european(language) else TEXTS["EUen"]
    name, description = text
    return ApShopItem(item_actor, None, name, wrap_description(description), model_actor=MODEL_ACTOR,
                      model_folder=MODEL_FOLDER, model_unit=MODEL_FOLDER,
                      icon_actor=None if item_actor == ACTOR else ACTOR)


def placed_names(status: dict, shrines: bool = False, master: bool = False) -> dict[str, tuple[str, str]]:
    """{item: (name, description)}: what each chest's location sends, as the seed
    placed it, in English as the shops say it (botw_patch/shops.py); the shrines'
    too with `shrines`, the Master Mode chests' with `master`."""
    from botw_patch.shops import item_texts
    names = {}
    for row in status.get("placements", []):
        number = int(row["location_id"]) - CHEST_ID_BASE
        if holds_item(number, shrines, master):
            names[actor(number)] = item_texts(
                row["item_name"], row["recipient_name"], row["recipient_game"], int(row["flags"]),
                row["recipient"] == status["slot"], row.get("location_name", str(row["location_id"])))
    return names


def _snapshot(obj):
    """A map object as plain values, to compare."""
    if isinstance(obj, (oead.byml.Hash, dict)):
        return {key: _snapshot(value) for key, value in obj.items()}
    if isinstance(obj, (oead.byml.Array, list, tuple)):
        return [_snapshot(value) for value in obj]
    if isinstance(obj, (str, bool, int, float)) or obj is None:
        return obj
    return (type(obj).__name__, getattr(obj, "v", str(obj)))


def patch_map(raw: bytes, items: dict[str, str] | None = None, flag_of=flag,
              chest_of=is_chest) -> tuple[bytes, list[dict]]:
    """One map unit with its item in each chest ({flag: item}: the chests left out keep
    their contents; else AP_Chest in all), nothing else changed. A Divine Beast's:
    beast_flag, is_dungeon_chest."""
    doc = oead.byml.from_binary(unpack(raw))
    before = _snapshot(doc)
    chests = []
    for obj in doc["Objs"]:
        if not chest_of(obj) or items is not None and flag_of(obj) not in items:
            continue
        parameters = obj["!Parameters"]
        if "DropActor" not in parameters:
            raise ValueError(f"chest without contents: {flag_of(obj)}")
        held = items[flag_of(obj)] if items is not None else ACTOR
        chests.append({"flag": flag_of(obj), "vanilla": str(parameters["DropActor"]), "item": held})
        parameters["DropActor"] = held
    after = _snapshot(doc)
    if {k: v for k, v in before.items() if k != "Objs"} != {k: v for k, v in after.items() if k != "Objs"} \
            or len(before["Objs"]) != len(after["Objs"]):
        raise ValueError("the map unit changed beyond its chests")
    for old, new in zip(before["Objs"], after["Objs"]):
        if old != new:
            old["!Parameters"].pop("DropActor"), new["!Parameters"].pop("DropActor")
            if old != new:
                raise ValueError(f"a chest changed beyond its contents: {new['HashId']}")
    out = bytes(oead.byml.to_binary(doc, big_endian=True, version=2))
    return bytes(oead.yaz0.compress(out)), chests


def _removal(b, item_actor: str):
    delete = b.action("Delete", b.system, "Demo_DeletePorchItemInEquip",
                      {"IsWaitFinish": True, "DeleteNum": 1, "PorchItemName": item_actor})
    return b.switch("Holds", "HasPorchItem", {"PorchItemName": item_actor, "Count": 1}, {1: delete, 0: None})


def add_entry(raw: bytes, items: list[str]) -> tuple[bytes, list[str]]:
    """OperationGuide<APChestRemove_nnnn> for each item, the existing events untouched."""
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    if chart.name != QUIET_FLOW:
        raise ValueError(f"wrong host flowchart: {chart.name}")
    names = {event.name for event in chart.events} | {point.name for point in chart.entry_points}
    for item_actor in items:
        name = entry(item_actor)
        if name in names:
            raise ValueError(f"entry already present: {name}")
        names.add(name)
        point = EntryPoint(name)
        point.main_event = make_rindex(_removal(traps.Builder(chart, name, names), item_actor))
        chart.entry_points.append(point)
    result = write_flow(flow)
    after = graph_snapshot(read_flow(result))
    for name, node in before["events"].items():
        if after["events"].get(name) != node:
            raise ValueError(f"existing event changed: {name}")
    return result, [f"{QUIET_FLOW}<{entry(a)}>" for a in items]


def add_info(raw: bytes, items: list[str]) -> tuple[bytes, list[str]]:
    """The entries' EventInfo: quiet, as the other entries of the host."""
    info = oead.byml.from_binary(unpack(raw))
    keys = [f"{QUIET_FLOW}<{entry(a)}>" for a in items]
    for key in keys:
        if key in info:
            raise ValueError(f"EventInfo already present: {key}")
        info[key] = oead.byml.Hash(copy.deepcopy(QUIET_EVENT_INFO))
    packed = oead.byml.to_binary(info, big_endian=True)
    return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else bytes(packed)), keys


def generate(files: dict[str, bytes], content, model: dict[str, bytes] | None = None,
             names: dict[str, tuple[str, str]] | None = None,
             shrines: bool = False, master: bool = False) -> tuple[dict[str, bytes], list[dict]]:
    """Add the chests' item, maps and removal entry to an overlay being built.

    `files` must already hold the size table, Bootup.pack and TitleBG.pack
    (with the quiet deliveries); what it lacks is read from the game's files
    `content` (botw_patch/game_files.py: the update and the DLC), checked.
    `names`: {item: (name, description)} shown in every language; an item
    left out (or all, without `names`) has the generic texts. With `shrines`, the
    shrines' chests that are locations have their items declared too (their maps
    are the shared shrines', botw_patch/shrine_chests.py). With `master`, the Master
    Mode chests that are locations hold their items too."""
    from botw_patch.game_files import GameFiles
    from botw_patch.shops import (ICON, ICON_TABLE_MARGIN, MODEL_ACTOR, MODEL_FOLDER, MODEL_REFERENCE,
                                  TITLE_SHA256, model_files)
    game = GameFiles.of(content)
    for name in (TABLE, BOOTUP, TITLE):
        if name not in files:
            raise ValueError(f"{name} expected in the overlay")
    languages = regions.of_content(game.content).languages
    inputs = {name: game.checked(name, expected)
              for name, expected in regions.inputs(INPUT_HASHES, game.content).items()
              if name not in files}
    source_title = game.original(TITLE)          # the amber lent to the item: the game's own
    if vanilla_digest(source_title) != TITLE_SHA256:
        raise ValueError(f"unexpected update resource: {TITLE}")
    amber = bytes(oead.Sarc(unpack(source_title)).get_file(f"Actor/Pack/{MODEL_ACTOR}.sbactorpack").data)
    has_model = all(f"Model/{MODEL_FOLDER}{part}.sbfres" in files for part in MODEL_PARTS)
    vanilla_maps = {name: game.checked_aoc(unit(name), expected)
                    for name, expected in {**MAP_HASHES, **(MASTER_MAP_HASHES if master else {})}.items()}
    numbered = numbering(vanilla_maps)
    if len(numbered) != CHEST_COUNT:
        raise ValueError(f"{len(numbered)} chests found, {CHEST_COUNT} expected")
    master_numbered = master_numbering(vanilla_maps) if master else {}
    if master and len(master_numbered) != MASTER_CHEST_COUNT:
        raise ValueError(f"{len(master_numbered)} Master Mode chests found, {MASTER_CHEST_COUNT} expected")
    beast_packs = {beast: unpack(game.checked_aoc(beast_pack(beast), expected))
                   for beast, expected in BEAST_PACK_HASHES.items()}
    beast_archives = {beast: oead.Sarc(raw) for beast, raw in beast_packs.items()}
    beasts_numbered = beast_numbering({beast: bytes(archive.get_file(beast_units(beast)[0]).data)
                                       for beast, archive in beast_archives.items()})
    if len(beasts_numbered) != BEAST_CHEST_COUNT:
        raise ValueError(f"{len(beasts_numbered)} Divine Beast chests found, {BEAST_CHEST_COUNT} expected")
    # Only the chests that are locations hold an item: the others keep their contents.
    located = {row["number"] for row in json.loads(LOCATIONS.read_text(encoding="utf-8"))}
    items = {name: held for name, held in numbered.items() if int(held.rsplit("_", 1)[1]) in located}
    beast_items = {name: held for name, held in beasts_numbered.items()
                   if int(held.rsplit("_", 1)[1]) in located}
    shrine_items = [actor(number) for number in sorted(located)
                    if shrines and SHRINES_HELD[0] <= number <= SHRINES_HELD[1]]
    master_located = {row["number"] for row in json.loads(MASTER_LOCATIONS.read_text(encoding="utf-8"))} \
        if master else set()
    items.update({name: held for name, held in master_numbered.items()
                  if int(held.rsplit("_", 1)[1]) in master_located})
    actors = sorted([*items.values(), *beast_items.values(), *shrine_items])
    names = names or {}
    if set(names) - set(actors):
        raise ValueError(f"names for no chest: {sorted(set(names) - set(actors))[:5]}")
    changes: list[dict] = []
    aoc_files: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        stage = Path(temp)
        for name, raw in {**inputs, **files}.items():
            if name.startswith(AOC_PREFIX):
                continue
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        builder = ResourceBuilder(stage)
        table = builder.table

        builder.outputs[ACTOR_INFO], detail = add_declarations(
            files.get(ACTOR_INFO, inputs.get(ACTOR_INFO)), [item("EUen", a) for a in (ACTOR, *actors)])
        changes.append({"resource": ACTOR_INFO, "declarations": len(detail)})
        for declared in (ACTOR, *actors):
            builder.outputs[f"Actor/Pack/{declared}.sbactorpack"], _detail = clone_actor_pack(
                amber, MODEL_ACTOR, declared, MODEL_FOLDER, MODEL_FOLDER, None)
            for kind, ext in (("Actor/Pack", "bactorpack"), ("Actor/ActorLink", "bxml"),
                              ("Actor/ModelList", "bmodellist"), ("Actor/GeneralParamList", "bgparamlist")):
                table.set_size(f"{kind}/{declared}.{ext}", table.get_size(f"{kind}/{MODEL_ACTOR}.{ext}"))
        icon = ICON.read_bytes()
        builder.outputs[f"UI/StockItem/{ACTOR}.sbitemico"] = icon
        table.set_size(f"UI/StockItem/{ACTOR}.bitemico", len(unpack(icon)) + ICON_TABLE_MARGIN)
        changes.append({"resource": "actor", "actor": ACTOR, "items": len(actors), "icon_sha256": digest(icon)})
        if not has_model:
            # The Archipelago model, as the shops' stage adds it (botw_patch/shops.py).
            model = model if model is not None else model_files()
            report = check_model(model, {part: MODEL_REFERENCE[part]["summary"] for part in MODEL_PARTS})
            renamed, rename_detail = rename_model(model, MODEL_ACTOR, MODEL_FOLDER)
            for part in MODEL_PARTS:
                builder.outputs[f"Model/{MODEL_FOLDER}{part}.sbfres"] = renamed[part]
                table.set_size(f"Model/{MODEL_FOLDER}{part}.bfres", model_size(
                    table.get_size(f"Model/{MODEL_ACTOR}{part}.bfres"),
                    MODEL_REFERENCE[part]["unpacked_size"], renamed[part]))
            changes.append({"resource": "model", "check": report, "renamed": rename_detail})

        for language in languages:
            def messages(raw, language=language):
                archive = oead.Sarc(unpack(raw))
                writer = oead.SarcWriter.from_sarc(archive)
                new, detail = add_item_texts(bytes(archive.get_file(MSBT).data),
                                             [item(language, a, names.get(a)) for a in (ACTOR, *actors)])
                writer.files[MSBT] = new
                packed = bytes(writer.write()[1])
                return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else packed), detail
            builder.patch_archive(f"Pack/Bootup_{language}.pack",
                                  {f"Message/Msg_{language}.product.ssarc": messages})
        builder.patch_archive(TITLE, {f"EventFlow/{QUIET_FLOW}.bfevfl": lambda raw: add_entry(raw, actors)})
        builder.patch_archive(BOOTUP, {EVENT_INFO: lambda raw: add_info(raw, actors)})

        count = 0
        for name, vanilla in sorted(vanilla_maps.items()):
            source = files.get(AOC_PREFIX + unit(name), vanilla)
            new, chests = patch_map(source, items, chest_of=field_chest if master else is_chest)
            count += len(chests)
            builder.account(TABLE_PREFIX + unit(name), new, vanilla)
            aoc_files[AOC_PREFIX + unit(name)] = new
            changes.append({"resource": AOC_PREFIX + unit(name), "chests": chests})
        if count != len(items):
            raise ValueError(f"{count} chests given an item, {len(items)} expected")
        count = 0
        for beast, archive in sorted(beast_archives.items()):
            writer = oead.SarcWriter.from_sarc(archive)
            given = []
            for member in beast_units(beast):
                vanilla = bytes(archive.get_file(member).data)
                new, chests = patch_map(vanilla, beast_items, beast_flag, is_dungeon_chest)
                given.append(sorted(chest["flag"] for chest in chests))
                writer.files[member] = new
                # The size table lists the static unit the game loads (under Aoc/0010/).
                if table.is_in_table(canonical(TABLE_PREFIX + member)):
                    builder.account(TABLE_PREFIX + member, new, vanilla)
                changes.append({"resource": f"{AOC_PREFIX}{beast_pack(beast)}//{member}", "chests": chests})
            if given[0] != given[1]:
                raise ValueError(f"{beast}: its two static units hold other chests")
            count += len(given[0])
            aoc_files[AOC_PREFIX + beast_pack(beast)] = bytes(writer.write()[1])
        if count != len(beast_items):
            raise ValueError(f"{count} Divine Beast chests given an item, {len(beast_items)} expected")
        aoc_files[MAP_ARCHIVE] = b""
        changes.extend(builder.changes)
        outputs = builder.finish()
    expected = {ACTOR_INFO, TABLE, BOOTUP, TITLE, f"UI/StockItem/{ACTOR}.sbitemico",
                *(f"Actor/Pack/{a}.sbactorpack" for a in (ACTOR, *actors)),
                *(f"Pack/Bootup_{language}.pack" for language in languages),
                *(() if has_model else (f"Model/{MODEL_FOLDER}{part}.sbfres" for part in MODEL_PARTS))}
    if set(outputs) != expected:
        raise ValueError(f"unexpected outputs: {sorted(set(outputs) ^ expected)}")
    return {**files, **outputs, **aoc_files}, changes


__all__ = ["ACTOR", "ENTRY", "CHEST_COUNT", "CHEST_ID_BASE", "placed_names", "actor", "entry", "numbering", "MAP_HASHES", "INPUT_HASHES", "SOURCE_FILES", "enabled",
           "is_chest", "flag", "patch_map", "generate"]
