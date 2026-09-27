# Boutiques Archipelago

## Implémentation (24/09)

Tout en ressources, construit par seed. **Validé en jeu sur un Terry (10f
ter, `20260924T153401.748335Z`)** : liste, achat, check enregistré, article
retiré de la liste pour de bon, client qui reconnaît la boutique. Reste la
partie réelle (indices et check envoyés au serveur, sauvegarde/rechargement).

- **Option de seed** `beedle_shop_items` (0 à 2, défaut 0) : nombre
  d'articles AP chez chacun des 16 Terry (15 relais + Bazar Assek).
  32 locations au plus, ID 154 à 185, « <lieu> - Beedle Item <n> »,
  schéma de locations 3. Prix tirés par la seed (20 à 200 rubis), écrits
  dans le manifeste de slot (`shops`). Source unique des noms, ID, drapeaux :
  [`botw_client/shop_catalog.py`](../../botw_client/shop_catalog.py) ; le CSV
  et `botw_world/data/locations.json` en sont des copies vérifiées par test.
  Lieux lus dans les cartes (LocationTag le plus proche), noms dans
  `LocationMarker.msbt`.
- **Construction** ([`botw_patch/shops.py`](../../botw_patch/shops.py),
  appelée par `build_resources_from_source` quand la seed a des boutiques ;
  sans boutique, fichiers identiques à avant) :
  - un acteur `AP_Shop_<id>` par location : déclaration clonée de l'ambre,
    prix de la seed, icône AP, modèle de Simon (`Model/AP_Item_00`), nom et
    description d'après le placement dans les 7 langues EU (français pour
    EUfr, anglais ailleurs ; code de grammaire recopié seulement là où la
    langue en a) ; nom tronqué à 30 caractères, description de 4 lignes ;
  - fiche de stock réordonnée : **articles AP en tête**, puis flèches et
    paquet de flèches, puis ce qui reste d'insectes ; stock 1 ; chaque
    article AP porte `ItemLookGetFlg` (listé tant que `IsGet_AP_Shop_<id>`,
    bool sauvegardé à vrai au départ, n'est pas effacé) ;
  - flux de Terry (les 16 copies) : au retour de la liste d'achat, pour
    chaque article AP, `HasPorchItem` → `Demo_SetGameDataInt APShop_<id> = 1`
    → `Demo_FlagOFF IsGet_AP_Shop_<id>` → `Demo_DeletePorchItemInEquip` ;
  - drapeaux s32 sauvegardés `APShop_<id>` déclarés (GameData + format de
    sauvegarde).
- **Client** : les drapeaux `APShop_<id>` sont des locations comme les autres
  (lecture s32 vivante ; absents du pack → non suivis). Seules les locations
  de la seed sont scoutées et envoyées. Liste ouverte (`Shop_ScreenType` 1)
  sur un `AP_Shop_<id>` (double lecture de `Shop_SelectItemName`) → indices
  `create_as_hint=2` pour les articles de ce Terry, une fois par location
  ([`botw_client/shop_state.py`](../../botw_client/shop_state.py)).

Limites connues, à mesurer :

- longueur de nom réellement affichable dans la liste ;
- persistance des drapeaux après une vraie sauvegarde et un rechargement
  (déclarés dans le format de sauvegarde ; un drapeau absent d'une
  sauvegarde prend sa valeur initiale, mesuré en 10f ter) ;
- quel Terry charge quel paquet d'événements (les 16 sont patchés).

Hors périmètre pour l'instant : armures des étals (mannequins), autres
marchands, icône propre aux objets BOTW. Étals 3D de consommables : voir
plus bas, « Étals 3D en locations de seed ».

## Audit statique (23/09)

Lecture seule des ressources montées. Données brutes :
`.build/source-audit-20260923/shop-actors.json` et `shop-stock.json`.

- **92 acteurs** ont une fiche de boutique (`Actor/ShopData/*.bshop`),
  **78 fiches uniques**, dont **68 avec une table `Normal`** (ce que le marchand
  vend) : **275 emplacements**. Par emplacement : `ItemName`, `ItemNum`
  (quantité en stock), `ItemAdjustPrice`, `ItemLookGetFlg` (affichage
  conditionné), `ItemAmount`. Autres tables : `Cooking`, `Compound`, `Rain`,
  `Ancient`… (variantes de stock ou rachat).
- Familles vendues : matériaux et nourriture (`Item_*` 84, `Animal_*` 52),
  flèches et objets (`Obj_*` 70), armures (36), teintures (15), crinières (10),
  armes (5). Beaucoup de consommables **réapprovisionnés** (flèches, fruits).
- Deux flux partagés font toute la vente :
  - `DisplayShop` : étals en 3D, l'objet est posé et choisi sur place
    (`Demo_ChangeChoiceNumFor3DShop`) ;
  - `Yorozuya_Kaiwa` : vente par liste avec icônes (Terry `Npc_TripMaster_00..15`,
    marchand de monstres…).
  Requêtes communes : `CheckItemShopSelect`, `CheckItemShopDecide`,
  `CheckItemShopPorchVacancy`. **La vente est une action native**
  (`Demo_SellItem`, `Demo_ShopFixedItemNum`), pas un don d'EventFlow : l'objet
  vendu vient de l'état natif de la sélection, que le flux ne voit pas.
- Cas à part : teinturerie d'Hatelia (`Demo_DyeShop*`), compendium de
  l'institut (`Demo_SellPictureBookUI`), écurie (crinières).

Conséquences pour la conception (tirées le 23/09 ; la première est
dépassée : un acteur créé pour AP remplace le don, sans point natif, 10c/10d) :

- neutraliser le don vanilla d'un emplacement AP demande un point natif :
  il n'y a rien à remplacer dans le flux ;
- en **liste**, afficher un objet d'un autre jeu est un nom + une icône
  (`Item_AP` existe). Sur un **étal 3D**, il faut aussi un **modèle** posé :
  nettement plus lourd ;
- un drapeau GameData « vendu » par emplacement AP : 275 emplacements
  dépasseraient la moitié du budget (~650 drapeaux custom). Le périmètre doit
  être choisi.

## Décisions de Simon (24/09)

- **Périmètre : option de seed configurable.** Le YAML choisit quelles
  boutiques deviennent des locations. Une valeur n'est exposée dans l'APWorld
  qu'une fois son mécanisme validé en jeu. Ordre de construction proposé :
  1. vente **par liste** (`Yorozuya_Kaiwa`, Terry et ses 16 apparitions) : un
     seul mécanisme, nom + icône `Item_AP` suffisent ;
  2. **équipement unique** sur étals 3D (armures, institut d'Hatelia) : il faut
     en plus un modèle posé pour un objet d'un autre jeu ;
  3. le reste du stock (consommables réapprovisionnés), si le budget de
     drapeaux le permet.
  Valeur par défaut de l'option : aucune boutique, tant que rien n'est validé.
- **Indices : à la vue du stock.** Ouvrir la liste (ou regarder un étal)
  envoie un `LocationScouts` avec `create_as_hint=2` (indice seulement pour ce
  qui n'est pas déjà connu) pour chaque emplacement AP affiché. Le client doit
  donc savoir **quand** le stock est affiché, et lequel : c'est un point de
  plus à instrumenter (voir les requêtes `CheckItemShopSelect`).

## Chemin natif (statique, 24/09)

Les noms d'actions d'EventFlow ne sont pas en clair dans `U-King.rpx` : la table
`Actor/AIDef/AIDef_Game.product.sbyml` (`Bootup.pack`) les relie à des classes,
enregistrées dans une table triée (crc32 du nom, fabrique) :

| Classe | crc32 | Fabrique | Constructeur | Table virtuelle |
|---|---|---|---|---|
| `NPCSellItem` (vente à Link, `Demo_SellItem`) | `0x0E0CADB9` | `0x02ABD4FC` | `0x02321874` | `0x10085E78` |
| `CheckShopSelectedItemName` | `0x104FA725` | `0x02B09AD8` | `0x02A790EC` | `0x10195A44` |
| `CheckItemShopSelect` | `0xDC704842` | `0x02B091D0` | | |
| `ShopFixedItemNum` | `0x71DD7495` | `0x02AC3D60` | | |

Autres classes : `NPCBuyItem`, `ChangeChoiceNumMsgFor3DShop`,
`CheckItemShopDecide`, `CheckItemShopPorchVacancy`, `CheckItemShopSelectBuy`,
`CheckSellResult`.

**Découverte clé : l'état de la boutique est dans des GameData.**
`CheckShopSelectedItemName {PorchItemName}` (`0x02A791D4`) lit la chaîne
`Shop_SelectItemName` par la fonction de lecture GameData (`0x02E1D5FC`) et la
compare au paramètre. La famille complète existe dans la table des drapeaux :
`Shop_SelectItemName` / `Shop_SelectItemNameJpn` (string64),
`Shop_SelectItemPrice`, `Shop_SelectItemNum`, `Shop_ItemState`,
`Shop_CurrentItemState`, `Shop_PlacedItemStockNum`, `Shop_ScreenType`,
`Shop_TradeItemNum` (s32), `Shop_IsDecide`, `Shop_DecideTrig`,
`Shop_IsSelectPurchase` (bool).

Conséquences, **à mesurer avant d'y croire** :

- le client peut **lire** l'article sélectionné, son prix et la décision
  d'achat comme n'importe quel GameData : de quoi déclencher les indices « à la
  vue » et reconnaître un achat, sans hook ;
- un flux peut **brancher sur l'article choisi** (`CheckShopSelectedItemName`,
  non utilisée par le jeu vanilla) avant `Demo_SellItem` : peut-être de quoi
  retenir le don vanilla d'un emplacement AP par ressources seules. Reste à
  savoir distinguer la boutique (les flux de vente sont communs à tous les
  marchands) ;
- l'index GameData vivant du client ne lit aujourd'hui que les scalaires : les
  `string64` demandent une extension.

## Mesuré en jeu : 10a chez Terry (`20260923T235049.551917Z`)

Lecture seule, aucun patch. Premier lancement (`20260923T234512`) perdu sur un
bug du harnais, corrigé.

| Moment | Drapeaux |
|---|---|
| « Acheter » choisi | `Shop_IsSelectPurchase` 0 → 1 |
| Liste ouverte | `Shop_ScreenType` 0 → 1, premier article sélectionné |
| Curseur déplacé | `Shop_SelectItemName` (nom d'acteur), `Shop_SelectItemPrice` (prix unitaire), `Shop_SelectItemNum` (stock restant) suivent le curseur |
| Achat décidé | `Shop_DecideTrig` impulsion, puis `Shop_IsDecide` 1 et `Shop_SelectItemNameJpn` = **nom de l'article acheté** |
| Quantité | `Shop_TradeItemNum` |
| Paiement | `CurrentRupee` baisse (prix × quantité), après la confirmation |
| Fin d'achat | `Shop_IsDecide` 0, `Shop_SelectItemNum` diminue |
| Sortie | `Shop_ItemState` -1, puis `Shop_ScreenType` 0 ; nom et prix restent |

- Les chaînes : l'octet `0x40` avant le texte est la taille du tampon (le « @ »
  des relevés bruts) ; après le zéro final restent des résidus d'anciens noms.
- Les articles et prix sont exactement la table `Normal` de
  `Npc_TripMaster_00.bshop`, dans l'ordre. Le stock est vivant (20 → 19,
  2 → 1). Pas de réordonnancement, rien d'épuisé (Simon).
- **Ce que ces drapeaux ne disent pas** : quelle boutique est ouverte (Terry a
  16 variantes de stock) ni la liste complète ; seul l'article survolé est
  exposé.

Conséquences : le client peut, sans patch, savoir qu'une liste est ouverte,
quel article est regardé, et reconnaître un achat (nom décidé, quantité,
paiement, baisse du stock). Il reste à identifier la boutique, et à décider
comment un emplacement AP est **affiché** (un nom d'acteur est ce que la liste
montre) et **ne donne pas** l'objet vanilla.

## Identifier la boutique (statique, 24/09)

Inventaire de tous les appels aux flux communs :
`.build/source-audit-20260923/shop-callers.json`. **78 appels d'achat, 45
marchands.** Chaque marchand entre dans le flux commun **depuis son propre
flux**, en passant son identité (`Self`/`Self2` = `Npc_TripMaster_00`,
`Npc_Kakariko010`…) et parfois la table de stock (`TableName`).

Terry : les 16 paquets `Event/Npc_TripMaster_00..15.sbeventpack` contiennent
chacun une copie **identique** du flux `Npc_TripMaster_00` (même sha256),
qui appelle `Yorozuya_Kaiwa:Zucchi_Konyu {TableName: Normal, Self2: Self}`.
Chaque Terry a aussi sa propre fiche `Npc_TripMaster_k.bshop` dans son paquet
d'acteur. **Hypothèse non mesurée** : l'acteur `Npc_TripMaster_k` charge le
paquet d'événements de même nom.

Deux façons d'identifier la boutique :

1. **Marquer l'appel** : dans le flux de chaque marchand, juste avant l'appel,
   `Demo_SetGameDataInt APShopId = k` (action déjà validée pour la liaison de
   seed). Un seul drapeau custom. Demande que chaque paquet soit bien propre à
   son acteur (hypothèse ci-dessus).
2. **Laisser le stock s'identifier lui-même** (piste préférée) : le pack étant
   construit par seed, la fiche `.bshop` de chaque boutique AP porterait des
   articles dédiés, un nom d'acteur **unique par location AP**, placés **en
   tête** de la table. À l'ouverture, le premier article est sélectionné
   d'office (mesuré en 10a) : son nom dit à la fois la boutique et
   l'emplacement. Le client peut alors envoyer les indices de tous les
   emplacements AP de cette boutique, et reconnaître un achat par le nom
   décidé. Aucun drapeau custom, aucune modification des flux pour
   l'identification.

La piste 2 reposait sur une question décisive : la liste d'achat accepte-t-elle
un article que la fiche vanilla ne contient pas, puis un acteur créé (nom,
icône, prix) ? **Oui** (10b, 10c) : c'est la piste retenue.

## Ce qu'exige un objet vendable (statique, 24/09)

Modèle : l'ambre (`Item_Ore_F`), vendue en 10b.

| Pièce | Où | Pour l'ambre |
|---|---|---|
| Déclaration | `Actor/ActorInfo.product.sbyml` (fichier libre de la mise à jour, 7934 acteurs, `Actors` + `Hashes` triés) | `profile: Item`, `itemBuyingPrice 120`, `itemSellingPrice 30`, `sortKey`, `tags`, `bfres`/`mainModel` |
| Paquet d'acteur | `Actor/Pack/Item_Ore_F.sbactorpack`, **dans `Pack/TitleBG.pack`** (6 objets courants y sont) | 15 membres : `ActorLink`, `GeneralParamList`, modèle, physique, IA de ramassage… |
| Modèle 3D | `Model/Item_Ore_F.sbfres` (+ `Tex2`), dans `TitleBG.pack` | |
| Icône | `UI/StockItem/Item_Ore_F.sbitemico` (mise à jour) | |
| Nom et description | `Bootup_EUfr.pack` → `Message/Msg_EUfr.product.ssarc` → `ActorType/Item.msbt`, étiquettes `Item_Ore_F_Name` / `_Desc` | une langue par paquet ; la console du labo est en français |

`Item_AP` n'est aujourd'hui **qu'une icône** (`UI/StockItem/Item_AP.sbitemico`) :
pas de déclaration, pas de paquet, pas de texte ; la fenêtre AP injecte son nom
en natif. Le calculateur de tailles sait évaluer la table des acteurs (byml) et
l'archive des textes. `tools/build_message_mod.py` réécrit déjà le texte
d'une étiquette **existante** de `Item.msbt` ; ajouter une étiquette demande de
reconstruire aussi `LBL1` (table de hachage des étiquettes). Leçon déjà payée
(voir l'outil) : un nom plus long que celui prévu dans le fichier déborde en
mémoire ; écrit dans le fichier, il n'y a pas de problème.

**Pistes pour un article AP**

- **A. Un acteur créé par emplacement** (`AP_Shop_000`…) : déclaration clonée
  de l'ambre (prix fixé par la seed), paquet cloné et renommé, icône `Item_AP`,
  nom « objet (joueur, jeu) » écrit par seed dans les textes. Le nom de
  l'article identifie l'emplacement (piste 2 ci-dessus). Tout est ressource,
  tout est déjà construit par seed.
- **Le problème de A : l'achat.** `Demo_SellItem` ajoutera vraisemblablement
  l'acteur à l'inventaire. Un objet AP ne doit rien laisser dans la poche.
  Options : brancher le flux avant la vente (`CheckShopSelectedItemName`,
  mais le flux est commun et il y a une requête par nom), retirer l'objet
  après coup par une entrée de livraison, ou trouver une propriété qui
  l'empêche d'entrer dans la poche. **Il faut d'abord mesurer ce que l'achat
  en fait.**

## Mesuré en jeu : 10c, un objet créé pour AP (`20260924T003100.487897Z`)

`AP_Shop_Test` (clone de l'ambre, icône `Item_AP`, nom et description français,
prix 50) en article 5 du Terry des Monts Jumeaux :

- **affiché comme un objet vanilla** : nom « Objet Archipelago », icône AP,
  prix 50, description telle qu'écrite ; drapeaux : nom `AP_Shop_Test`, prix 50 ;
- **vendu** : décision + nom décidé, rubis 500 → 450, stock 3 → 2, jeu stable ;
- **mais il entre dans la poche**, onglet Matériaux, avec l'icône AP et sa
  description. Tenu en main, Link porte un minerai d'ambre (le modèle cloné),
  qu'il peut poser et reprendre ; le texte de ramassage est la description sur
  une seule ligne qui déborde du cadre (Simon).

Enseignements : un acteur créé n'a pas besoin de modèle propre pour être vendu
et rangé ; la description demande des retours à la ligne explicites ; un
article AP ne doit **pas** rester dans la poche (on pourrait le tenir, le poser,
le revendre : il hérite du prix de revente de l'ambre).

**Retrait** : le jeu a l'action `DeletePorchItemIncludeEquip`
(`Demo_DeletePorchItemInEquip {PorchItemName, DeleteNum}`), déjà utilisée à la
fin de la Ballade pour retirer le pouvoir de base, et mesurée en 9q. Piste
préférée, **tout en ressources** : dans le flux du marchand, juste après le
retour du sous-flux d'achat (`Npc_TripMaster_00` : `Event18 → Event150`),
supprimer chacun des articles AP de ce marchand (`DeleteNum -1`). Le nom et
les emplacements de chaque marchand sont connus à la construction du pack de
seed. Le client, lui, voit l'achat (nom décidé, paiement) et envoie le check.

## Mesuré en jeu : 10d, l'objet AP retiré à la fermeture (`20260924T005448.109900Z`)

Pack `3209f911513992e5` (`botw_patch/shop_items.py`) :

- liste ouverte puis fermée **sans achat** : conversation normale ; supprimer
  un objet absent de la poche est sans effet ;
- description sur plusieurs lignes, dans le cadre ;
- achat : nom décidé `AP_Shop_Test`, rubis 500 → 450, stock 3 → 2 ; curseur
  déplacé ensuite sur d'autres articles sans effet ;
- à la fermeture : rien de visible ; **l'objet n'est plus dans la poche**, les
  rubis restent payés, jeu stable.

**La chaîne complète d'une boutique AP fonctionne en ressources seules** :
objet créé (nom, icône, prix, description), vendu par le marchand vanilla,
retiré de la poche à la fermeture de la liste ; le client voit l'achat.

Piège de lecture : un échantillon a lu `bj_ArrowNormal_A_01`, la chaîne étant
lue pendant que le jeu l'écrivait. Le lecteur du client devra exiger **deux
lectures identiques** consécutives.

## Modèle 3D de l'objet AP

Mode d'emploi et règles : [assets/models/ap_item/README.md](../../assets/models/ap_item/README.md).
**10e validé (`20260924T024633.314331Z`, pack `6c142d0310f96aa1`)** : l'objet
AP de 10c avec le modèle de Simon (`Model/AP_Item_00`, noms internes renommés
à la construction) a sa propre texture et la bonne taille au sol. La position
en main reste bancale : accepté, l'article AP est retiré de la poche après
l'achat (10d). Le test (`Test-10e-ModeleAP.cmd`) reconstruit le pack depuis
`assets/models/ap_item/wiiu/` : il sert de contrôle après chaque retouche du
modèle. Les vraies boutiques utiliseront ce modèle pour tous leurs articles AP.

## Validation

**10f** (`Test-10f-BoutiquesReelles.cmd`, mode `native-shop-record`,
`tools/build_shop_record_probe.py`, pack reconstruit à chaque préparation) :
le code réel de `botw_patch/shops.py` sur le pack de labo, Terry des Monts
Jumeaux (sauvegarde forgée à côté, 500 rubis), deux articles : 154 objet d'un
autre jeu au nom long (50 rubis), 155 objet pour ce slot (20 rubis). Le
harnais relève les drapeaux `Shop_*`, `APShop_154/155` et ce que le client
déduit de la liste (`ShopWatch.seen`). Questions : AP en tête, noms et
descriptions, drapeau 154 à 1 et 155 à 0 après l'achat du premier, objet
retiré, que devient l'article acheté à la réouverture, stabilité.

**10f (`20260924T133321.772947Z`)** : AP en tête, nom long tronqué
(« Progressive Hookshot of the... »), prix, description dans le cadre, objet
retiré de la poche, jeu stable. **Mais l'article acheté revient en stock à
chaque réouverture de la liste** (Terry réapprovisionne à chaque ouverture).
Les drapeaux n'ont pas été mesurés (bug du harnais, corrigé).

**10f bis (`20260924T143406.693670Z`)** : `ItemLookGetFlg` **n'affiche un
article que si `IsGet_<objet>` est vrai** (ambre possédée : en vente ;
baudruche octo jamais obtenue : absente). Mesures perdues (bug du harnais,
corrigé ; le harnais complet est désormais testé sur un faux jeu).

**Solution retenue** : chaque article AP porte `ItemLookGetFlg` ; son bool
sauvegardé `IsGet_AP_Shop_<id>` démarre à vrai (valeur initiale) et le flux
de Terry le passe à faux à l'achat (`Demo_FlagOFF`), avant de retirer
l'objet. **10f ter** (même lanceur, pack `b61e0296994aeb4b`) : l'article
acheté doit quitter la liste pour de bon ; la sauvegarde forgée ne connaît
pas ces drapeaux, ce qui dira aussi si un drapeau absent d'une sauvegarde
prend sa valeur initiale (nécessaire pour les parties déjà commencées).

### Étals 3D (`DisplayShop`) — 10g validé

Mesuré dans les cartes (DLC, `aoc/0010/Map/MainField`) : **pas de fiche de
stock** ; chaque objet en vente est un objet de l'unité de carte lié à son
marchand par `ForSale` (et par `DeadUp` à un `LinkTagAnd` dont le `SaveFlag`
dit l'étal épuisé, ex. `Npc_Kakariko010_SoldOut`). Le flux du marchand lance
`DisplayShop:Multiple` pour l'objet regardé (`Npc_Kakariko010` : entrée
`ClerkAsk` → `Event194` → `Event175 DisplayShop` → `Event174`). Objets triés
par `HashId`, chacun avec un `SRTHash` au calcul inconnu.

**10g** (`Test-10g-EtalCocorico.cmd`, mode `native-shop-stall`,
`tools/build_shop_stall_probe.py`) : pack 10f ter, plus, dans `G-6_Static`,
le paquet de flèches `1217052511` de l'étal de flèches de Cocorico devenu
`AP_Shop_154` (même `HashId`, position, rotation, liens : seul l'acteur
change), et l'enregistrement d'achat après `Event175`. Première modification
d'une unité de carte : entrée de taille `Aoc/0010/…` recalculée. Questions :
Cemu lit-il le dossier `aoc/` d'un pack graphique ; allure du médaillon sur
l'étal ; nom et prix annoncés ; achat enregistré ; retour de l'objet après
un départ de la zone (réapparition = à traiter avant d'en faire des
locations).

**10g (`20260924T165824.970608Z`) — validé, un défaut corrigé.** Cemu lit le
dossier `aoc/` d'un pack graphique ; médaillon à la bonne taille et texture
sur l'étal (inclinaison héritée du paquet de flèches) ; nom, icône et
description AP dans le dialogue d'achat ; achat enregistré (`APShop_154` = 1,
`IsGet_AP_Shop_154` = 0), objet retiré de la poche ; pas de retour après un
départ de la zone. **Défaut** : prix 120 (celui de l'ambre) au lieu de 50 :
les étals lisent `Item.BuyingPrice` du `GeneralParamList` de l'acteur, la
liste lit `ActorInfo`. Corrigé : chaque acteur AP a son propre
`GeneralParamList` au prix de la seed. Reste à voir : lune de sang
(réapparition), inclinaison (`Rotate`, `SRTHash` non compris). Les étals ne
sont pas encore des locations de seed.

### Étals 3D en locations de seed (25/09) — construit, essai en jeu à faire

Option `stall_shop_items` (0 à 2, défaut 0) : 28 locations (ID 186-213,
schéma de monde 4), 2 par étal sur 14 étals. Source unique :
[`botw_client/stall_catalog.py`](../../botw_client/stall_catalog.py) ;
ressources : [`botw_patch/stalls.py`](../../botw_patch/stalls.py), appelé par
`botw_patch/shops.py`. Tests : `tests/test_stalls.py`, et
`tests/test_native_world.py` pour l'option.

- **Étals retenus** : les 14 qui vendent des consommables par
  `DisplayShop:Multiple` dans leur propre flux et ont un article en plusieurs
  exemplaires. Soit Piaf, Cité Gerudo (fruits, flèches, matériaux), Bazar
  Assek (fruits), Forêt Korogu (champignons, général), Village Goron,
  Cocorico (flèches, général), Écaraille, Euzero (flèches), Domaine Zora et
  Elimith. Écartés : armures (mannequins, autre mécanisme), étals où tout est
  en un seul exemplaire, et quatre marchands sans `DisplayShop` dans leur
  flux (Cocorico 006/012/013, canal de la cité Gerudo).
- **Objets remplacés** : parmi les articles vendus en plusieurs exemplaires,
  le plus répété d'abord, jamais le dernier exemplaire. L'étal garde tout ce
  qu'il vendait (par exemple, à Cocorico, 1 flèche sur 10 et 1 flèche de feu
  sur 10).
- **Lieux et régions** : `LocationTag` le plus proche, nommé par
  `LocationMarker.msbt`. Région : la tour la plus proche, règle des
  sanctuaires.
- **Carte** : l'objet devient `AP_Shop_<id>`. Son HashId, sa position et ses
  liens (`ForSale`, étiquettes d'épuisement) restent les mêmes. Sa rotation
  est ramenée au lacet du marchand : le médaillon fait face au client,
  correction de l'inclinaison vue en 10g.
- **Réapparition** : un nouveau `LinkTagAnd` sans entrée, `SaveFlag =
  IsGet_AP_Shop_<id>`, crée l'objet par un lien `Create`. C'est le motif
  vanilla de 956 tags de ces cartes (par exemple
  `BalladOfHeroGerudo_Activated` → `Create` → `Area`). Le drapeau est vrai
  jusqu'à l'achat, donc un objet acheté n'est plus jamais créé, lune de sang
  comprise. HashId du tag : crc32 de son nom, vérifié unique. `SRTHash` :
  valeur dérivée du nom (calcul vanilla inconnu, sans effet attendu sur un
  tag). **À confirmer en jeu.**
- **Achat** : enregistrement de 10f après l'événement `DisplayShop` du
  marchand (vérifié sur les 14 flux).
- **Paquet** : les cartes sortent sous `aoc/0010/…` à la racine du pack,
  avec leur taille comptée sous `Aoc/0010/…`
  (`tools/build_resources_from_source.pack_path`).
- **Pas fait** : indice « à la vue » pour les étals. Celui des Terry vient de
  la liste ouverte ; un étal n'a pas de liste.

Seed de test : `64529533770724516574` (`beedle_shop_items: 2`,
`stall_shop_items: 2`), paquet `.build/packs-from-source/854913a933579ebe`
(sélectionné : `Jouer-Partie.cmd --seed 64529533770724516574`).
**Il faut une sauvegarde neuve** : les sauvegardes actuelles sont liées à la
seed `56866616677933465054`.

Ensuite, dans une vraie partie (acceptation) : une seed générée avec
`beedle_shop_items: 2`, indices à la vue, check envoyé, rechargement.

**10f ter (`20260924T153401.748335Z`) — validé.** Liste « AP (1), AP (1),
flèches, 5 flèches, baudruche » ; drapeaux `IsGet_AP_Shop_154/155` à 1 au
départ alors que la sauvegarde ne les connaît pas (valeur initiale prise) ;
`ShopWatch` voit `[154, 155]` liste ouverte ; achat 50 rubis, épuisé tant
que la liste reste ouverte ; à la fermeture `APShop_154` = 1,
`IsGet_AP_Shop_154` = 0, 155 intact ; article absent à la réouverture et à
une nouvelle conversation ; objet retiré de la poche ; jeu stable.

## Historique des essais

- 10a lecture seule, 10b ambre vendue, 10c acteur AP vendu, 10d retiré à la
  fermeture, 10e modèle AP : détail dans les sections ci-dessus. Les
  constructeurs 10b à 10e restent comme preuves (`tools/build_shop_*_probe.py`,
  `tools/shop_probe_pack.py`).
