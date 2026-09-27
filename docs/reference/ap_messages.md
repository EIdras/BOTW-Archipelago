# Messages AP généraux — 25 septembre 2026

## Décisions de Simon (25/09)

- **Canal : le cadre des conseils** (en haut à droite, `MessageTipsRunTime_00`).
  Non bloquant, 3 lignes, couleurs, disparaît seul. La fenêtre de dialogue
  (style sanctuaire) est écartée pour le journal : elle bloque le jeu.
- **Contenu par défaut : ce qui concerne le joueur** — objets envoyés par lui,
  objets reçus des autres, indices le concernant ; chat en option ; trafic des
  autres joueurs désactivé par défaut.
- **Objets reçus : une seule présentation.** « de Alice » dans le journal
  *avant* la fenêtre d'obtention vanilla ; l'annonce AP en double disparaît.
- **Statut de connexion** : annonces dans le journal (connexion, perte,
  reprise) d'abord ; puis un objet d'inventaire (catégorie importante) à
  description fixe par seed (serveur, seed, slot) ; indicateur sur le HUD plus
  tard.

## Essai du dialogue (25/09, pack `e03f02834ceb58cc`)

Texte AP affiché, fermeture et retour au contrôle corrects. Mais : fenêtre
bloquante ; attente de plusieurs dizaines de secondes (« Native presentation
resource not ready », réessais) ; texte long sur une seule ligne (pas de
retour automatique) ; un objet reçu pendant l'affichage le coupe. D'où le
changement de canal.

## Cadre des conseils, mesuré (10h, 25/09)

- `0x02fd4848(this, index)` pose seulement le texte : appelée seule, **rien ne
  s'affiche** (le cadre n'est pas ouvert).
- **`0x02fd4730(this, index, forcer)` est la demande publique** : verrou du
  widget (`this+0x1b6c`), refus si `index >= 23` ou déjà affiché, refus si le
  drapeau `GuideS_…` du conseil est vrai (un conseil ne sort qu'une fois),
  refus si le jeu est occupé sauf `forcer`, puis mise en file ; la mise à
  jour par image ouvre le cadre et appelle `0x02fd4848`.
- Par cette demande (drapeau remis à faux, `forcer` = 1), puis remplacement
  du texte par `0x03082d88(this->0x18, 'T_Text_00', {ptr, longueur})` :
  **notre texte s'affiche au bon endroit, vite, sans bloquer, couleurs
  comprises** (Simon, `tools/cemu/tipsprobe.py --request`).
- **Pas de retour à la ligne automatique** : le texte long déborde à droite,
  hors de l'écran. Les conseils vanilla ont leurs retours écrits à la main :
  **3 lignes de 34 caractères au plus** (fr, en, de).

Implémentation prévue (propre, sur le modèle du pont de dialogue) : demande
par `0x02fd4730` sur un index réservé, drapeau remis à faux juste avant,
substitution du texte **au point où le jeu pose le sien** (`0x02fd48c8`, avant
`bl 0x03082d88`) pour notre seule demande (génération), sans éclair du texte
vanilla ; découpage à 34 caractères hors codes de couleur, 3 lignes par
conseil, message plus long en conseils successifs ; file côté client, un
conseil à la fois, priorité aux objets.

## Journal AP dans le cadre des conseils — validé en jeu (25/09), dans tous les paquets (26/09)

- **Natif** ([`tools/build_tip_channel.py`](../../tools/build_tip_channel.py),
  composé par `tools/build_native_from_source.py` dans le code injecté de
  tous les paquets depuis le 26/09 ;
  contrat [`botw_client/tip_protocol.py`](../../botw_client/tip_protocol.py)) :
  conseil emprunté index 21, `GuideS_RelicControl` (« contrôle d'une créature
  divine », une fois, dans les créatures). `apTipSubmit` (fil du jeu, via
  l'invocateur par image, sous le verrou commun) : refus si un conseil AP est
  actif ou si l'index est en file/à l'écran ; drapeau lu par le lecteur du jeu
  (`0x02fd4730` le lit ainsi), puis bit de valeur mis à 0 (objet vérifié par son
  hash) ; génération publiée ; demande officielle `0x02fd4730(widget, 21, 1)` ;
  si le jeu ne l'a pas mise en file, drapeau rendu aussitôt. **Substitution** à
  `0x02fd48c8` (composée dans le hook existant) : seulement même widget, même
  index, phase « demandé » ; le jeu pose lui-même notre texte. **Fin** (composée
  dans le hook par image de `0x02fd4a1c`) : l'index n'est plus ni en file
  (`+0x1ba8`) ni à l'écran (`+0x1bb0`, remis à -1 par `0x02fd4bc0`) → drapeau
  rendu à sa valeur d'origine, génération terminée. Rien d'autre du jeu ne
  change ; le conseil emprunté garde son texte et sort une fois, comme en
  vanilla. Tests : le vrai code généré exécuté sur un modèle du widget
  (`tests/test_tip_channel.py`) ; `tools/patch_lint.py` sur le patch composé.
- **Client** ([`botw_client/tip_channel.py`](../../botw_client/tip_channel.py)) :
  données trouvées par leur signature dans le code cave ; pages de 3 lignes de
  34 caractères, couleurs `{N}…{/}` (joueurs `{2}`, objets `{1}`) ; un conseil
  à la fois, le suivant quand le jeu a refermé le cadre.
- **Contenu** ([`botw_client/ap_journal.py`](../../botw_client/ap_journal.py)) :
  envoyé par toi, reçu des autres, indices te concernant, chat (désactivable),
  rien des autres par défaut ; objets trouvés pour toi-même non répétés. Plus
  les annonces du client : connecté, connexion perdue, reconnecté.
  Seuls les messages de la session en cours et de moins de 5 min.
- **Lanceur** : journal actif par défaut, le paquet le déclare
  (`manifest.json` : `"ap_journal": "tip_channel"`). `--native-tips` est encore
  accepté et ne fait rien. `--native-messages`, le canal de dialogue
  expérimental, le désactive. Console `/ap-tip <texte>` pour essayer. Les
  anciens paquets `tip-play-packs` (canal ajouté après coup) ne servent plus.
- **Messages du serveur** (Simon, 25/09) : le journal affiche le texte AP du
  serveur (PrintJSON), joueurs `{2}` et objets `{1}` colorés, pour tout ce qui
  concerne le slot : objets reçus (d'un autre joueur **ou trouvés dans son
  monde**), objets envoyés, indices ; chat désactivable ; trafic des autres
  masqué par défaut.
- **Objet reçu** : sa ligne serveur (« Alice sent Hookshot to Simon (Temple) »,
  « Simon found their Paraglider (…) ») est retrouvée par objet, location et
  expéditeur et affichée d'abord ; sans ligne serveur en 3 s (reçu hors
  ligne, `/send` de console), la même phrase au format du serveur. 2 s de
  lecture, puis la présentation : fenêtre vanilla seule si la livraison en a
  une, sinon fenêtre AP. Crochet `announce` de la session de présentation :
  rien n'est inscrit derrière une ligne pas encore affichée.
- **Location dont l'objet part chez un autre** : plus de fenêtre AP, la ligne
  serveur « Simon sent … to Bob » suffit.
- **Livraison par la fenêtre vanilla** (`GetDemo<GetItemByName>`,
  `botw_client/delivery_plan.py` `pouch_kind`) pour tous les objets de
  l'inventaire : armures (une fenêtre par pièce), armes, bouclier, paravoile,
  noix korogu, orbe, fée, matériaux, en plus des cœurs, de l'endurance et des
  rubis ; **validé en jeu** (Simon, 25/09). **Pouvoirs des prodiges** : la
  fenêtre du jeu (`GetDemo<ShowGetDemoDialogByName>`, présentation spéciale)
  remise à sa place vanilla dans l'entrée (inventaire, équipement, fenêtre,
  drapeau) ; la variante « pouvoir amélioré » de l'étape 7 reste sans fenêtre
  (une attribution GetDemo du pouvoir DLC hors Ballade a planté en 9l) : ligne
  du journal seulement dans ce cas rare. Restent en fenêtre AP : runes, bride
  et selle. **Prodiges à valider en jeu** (pack
  `.build/tip-play-packs/3aa311ac14416556` sur `7fcbe6ba9289d56c`) ; les deux
  tests de construction reproductible ont une nouvelle référence en attente
  de cette validation.
- **Prodiges** : fenêtre du jeu validée en jeu (Mipha, Simon, 25/09).
- **Objets rendus après chargement** (Simon, 25/09) : le client retient le plus
  haut index jamais livré (`delivered_high`) ; en dessous, après un
  rechargement, l'objet est rendu par l'**entrée jumelle silencieuse** de
  l'étape (`quiet_entry` du catalogue : inventaire direct, prodige par la
  chaîne 9w ; l'étape 7 branche aussi la Ballade sur elle), puis **une seule
  fenêtre AP « Objets rendus »** les nomme (4 lignes de 40, « et N autres »).
  **Rubis** (piste 2) : la jumelle silencieuse du paquet de rubis est
  l'action vanilla `Demo_IncreaseRupee {Value, IsWaitFinish}`, celle des
  récompenses de quête (Npc_Goron018 Event179, Demo035_0 Event136) ; valeur
  tirée de l'acteur GetDemo (PutRupee_Red = 20). Pas l'écriture brute du
  compteur, qui avait échoué en 7h. Cœurs et endurance gardent leur fenêtre.
  Pack `.build/tip-play-packs/346af84f4187d55e` (sur `f8f17c898cbe0955`),
  **à valider en jeu**.
  Essai 25/09 : (1) un état écrit avant `delivered_high` rendait tout avec
  fenêtre ; le client le déduit maintenant de la liste `applied`. (2) En
  silencieux les livraisons s'enchaînent dans la même seconde : #5/1 demandée
  une image après le commit de #5/0 a été acceptée puis jamais jouée (le commit
  précède GuardOFF et la fermeture de l'événement). Hypothèse : on attend
  désormais `SETTLE_FRAMES` = 30 images du jeu après chaque commit avant la
  demande suivante ; si le cas revient, l'erreur donne l'écart en images.
  Validé au 3e essai (16 étapes rendues, une fenêtre « Objets rendus »).
  Retour de Simon : chaque objet rendu fige le jeu en masquant le HUD, et
  l'animation des rubis fige le joueur. Pour le HUD, voir « Objets rendus sans
  pause ni clignotement du HUD » plus bas.
  Rubis : `Demo_IncreaseRupee` passe à `IsWaitFinish: False` pour ne plus
  figer le joueur pendant l'animation. **Validé en jeu** (Simon, 25/09) :
  +60 pour 3 paquets, animation visible, joueur libre.
- **Objets rendus sans pause ni clignotement du HUD** (validé en jeu, Simon,
  26/09 : rechargement d'une vieille sauvegarde, aucun clignotement, fenêtre
  « Objets rendus » présente). Chaque objet rendu figeait le jeu une fraction
  de seconde en masquant le HUD.
  - **Cause** : la clé d'EventInfo `is_pause_non_demo_member`. Absente, un
    événement met en pause tout ce qui n'y participe pas. Les événements de
    fond du jeu la mettent à `False`, par exemple `Npc_King_Vagrant001<Near>`,
    qui ne touche pas au HUD.
  - **Correction** : les jumelles silencieuses sont enregistrées comme ces
    événements, avec `delivery_flow.QUIET_EVENT_INFO` =
    `{disable_event_start_interval, is_pause_non_demo_member: False,
    is_timeline: False, mode: Seamless}`. Elles sont hébergées dans le
    flowchart résident `OperationGuide` (`delivery_flow.QUIET_FLOW`), qui
    garde ses entrées intactes, comme `Demo007_1`, et le catalogue porte
    `quiet_flow` pour la demande. La requête passe par le wrapper du jeu,
    sans rien de natif. Les livraisons avec fenêtre vanilla restent dans
    `Demo007_1`, en cinématique comme les dons du jeu.
  - **Pas en cause, mesuré** : les drapeaux de requête. Ils viennent du nom du
    flowchart (préfixe `Demo` = `0xf`) et du type (zeldaret/botw,
    `evtMetadata.cpp`, `initFlags_`). Avec des sondes vides, sans la clé, le
    HUD clignote aussi en `0x64` (défaut), `0x19a` (`Near`, les drapeaux
    exacts du PNJ) et `0x1fe` (`Background`). Avec la clé, plus aucun
    clignotement.
  - **Impasses** : un flowchart neuf `EventFlow/APDelivery.bfevfl` ajouté à
    `TitleBG.pack` est accepté par le jeu puis jamais exécuté, car un fichier
    ajouté n'est pas trouvé comme les flowcharts résidents d'origine. Un
    passage du type par le wrapper (code natif) s'est révélé inutile et a
    été retiré. Non essayé : `Demo007_1` avec la clé.
  - **Outil gardé** : en console, `/ap-evt [n|reset]` décode la trace des
    requêtes d'événement du jeu (`patch_event_request.asm`) : flowchart,
    entrée, type, drapeaux (`tools/cemu/event_request_trace.descriptor_fields`,
    offsets Wii U de `evt::Metadata` : type `+0xf8`, drapeaux `+0x108`).
- **Statut de connexion** (25/09) : le journal annonce la connexion, **une
  seule** ligne par coupure (plus une par tentative), puis « Reconnecté …
  après N s de coupure ». Test en console : `/ap-coupure [s]`.
- **Objet « Archipelago »** (25/09, `botw_patch/status_item.py`) : objet clé
  cloné des maracas de Noïa, avec le logo. Sa description donne la seed, le
  joueur (slot) et l'objectif, dans chaque langue EU. L'entrée
  `Demo007_1<APStatusItem>` l'ajoute seulement s'il manque (HasPorchItem).
  Le client la demande une fois par connexion au jeu, après les livraisons.
  Présent dans tous les paquets de seed. **À valider en jeu.**
- **HUD** : logo AP en bas à gauche, couleur si connecté, gris sinon : [hud_indicator.md](hud_indicator.md).
- **Runes par l'écran de téléchargement de la tablette** : **validé en jeu le
  26/09** (session `20260926T200314.779273Z`, sonde `20260926T220348.json`,
  Bombes en direct). C'est la présentation native voulue par Simon, sans
  fenêtre AP. Chronologie mesurée, identique au terminal vanilla :
  `IsDownloadDemo`, carte au repos en 60 ms, menu ouvert ≈ 1 s plus tard avec
  la requête gardée, trois états de téléchargement, sélection par le jeu,
  drapeau, commit `#16/0`.

  Retouches possibles notées par Simon :
  - un petit temps avant le menu : attente ramenée de 30 à 10 images (60 ms
    suffisaient dans la mesure), à revoir en jeu ;
  - l'animation où Link range la tablette paraît un peu étrange : elle est
    faite pour la tablette posée sur le terminal.

  L'historique de l'enquête suit.
  - *Trois échecs* (8z le 17/09, deux fois le 26/09) : le menu Modules s'ouvre
    sur des cases vides (« Des données sont manquantes ») et l'écran ne finit
    jamais. En Fork (le dernier essai), la voix et la fermeture du menu se
    jouent, puis l'événement reste bloqué.
  - *Erreur de lecture corrigée* : dans le vanilla (`Demo003_0` `Item01..04`),
    l'écran, l'attente de 70 images, la voix `NPC_DRCVoice` et
    `Demo_CloseItemMenu` sont **à la suite** dans une même branche. La branche
    parallèle ne porte que caméra et animation (`CommonItemDownload`). Tous
    posent `IsDownloadDemo` avant. La voix créée depuis `Demo007_1` marche
    (mesuré le 26/09).
  - *Ce que dit le code* (lecture statique de `U-King.rpx`, 26/09) :
    - classe IA `OpenItemDownloadDemo`, fabrique `0x02ABE750`, vtable
      `0x1008C3EC`, `calc_` en `0x0234D868` ;
    - au premier passage, `ItemType` passe par la table `0x104BA91C`, puis
      `0x0307D504` demande le menu pause (écran UI `0x1F`) et écrit la requête
      en `0x1053F754` (type u32, IsEquip, IsPowerUp ; aucune requête =
      `0xFFFFFFFF`) ;
    - l'action ne finit que quand `0x0307D5BC` voit le menu dans l'état dont
      l'objet est en `0x1053F72C` ;
    - côté menu (`0x02F7F274`), la séquence ne démarre que si la liste
      d'emplacements (`+0x1B7C` nombre, `+0x1B80` tableau de `0x18` octets)
      contient un emplacement du type demandé (`+0x14`) qui porte un objet
      (`+0x00` non nul). Sinon rien ne se passe : c'est le symptôme.
  - *Mesure 11a du terminal vanilla* (`20260926T184407.328329Z-native-rune-download`,
    Oman Au, labo). Lancée par `Test-11a-TelechargementRune.cmd` (mode
    `native-rune-download`), sonde `tools/cemu/download_probe.py`, harnais
    `tools/rune_download_test.py`. Les 8 emplacements portent **déjà** leur
    objet avant toute rune : l'hypothèse de l'emplacement vide est fausse.
    Chronologie :
    - `IsDownloadDemo` passe à 1 au début de la cinématique ;
    - à l'ouverture du menu, la requête « type 2 » est écrite, l'emplacement 2
      est marqué (`+0x10` = 1), et **le menu remet `IsDownloadDemo` à 0** ;
    - le menu écrit lui-même `PlayerEquipItemType` = 2 (IsEquip) ;
    - le menu passe par ses états de téléchargement (`+0xDC` : `0x1053F694`,
      puis `0x1053F6F4`), et l'action rend la main avant la voix ;
    - après la fermeture : `IsGet_Obj_Magnetglove` = 1, requête effacée, état
      `0x1053F724`.
  - *Chaîne actuelle* (`delivery_flow.py`, `DOWNLOAD_FLAG`) : l'ordre exact du
    vanilla, à la suite. `IsDownloadDemo`, écran, attente 70
    (`EventSystemActor[01]`), voix, fermeture, drapeau, sélection. Rendue
    après un rechargement : drapeau et sélection seuls.
  - *Notre livraison mesurée* (`.build/download-probe/20260926T210314.json`,
    Stasis 5 s après le chargement, menu jamais ouvert avant). La requête
    « type 3 » est écrite **avant** que le menu existe. Le menu est construit
    l'image suivante, son constructeur (`0x02F7EE70`, via `0x02F7EE58`) efface
    la requête, et il s'ouvre en menu normal (état `0x105584DC` sans suite).
    L'écran attend alors pour toujours.
  - *Cause* : l'action demande d'abord la construction immédiate du menu
    (`0x03080A14(0x1F)`, puis le chargeur `0x03058E84`). Le chargeur ne le
    construit tout de suite que si :
    - la **carte** (écran `0x2A`) est au repos (`+0x96` = 0 et `+0x95` ≤ 0,
      `0x03A3E4DC`) ;
    - la carte est chargée (chargeur en `+0x21AC`, état `+0xD8`/`+0x124` = 13
      et `+0x100` = 0, `0x02F359F0`) ;
    - l'**inventaire** (écran `0x22`, chargeur en `+0x9080`) est chargé.

    Sinon le menu est construit plus tard, après la requête. En 11a, le menu
    avait été ouvert avant le terminal, donc la carte était chargée. Écrans
    identifiés par la fabrique `0x0305EB18` : `0x1F` menu pause, `0x22`
    inventaire, `0x25` HUD, `0x29` cadre des conseils, `0x2A` carte.
  - *Essai du 26/09 au soir* (session `20260926T192753.665775Z`, sonde
    `20260926T212850.json`) :
    - la carte n'est presque jamais au repos en jeu (état 2), seulement un
      instant autour d'un événement ou de l'ouverture du menu ; carte et
      inventaire, eux, sont chargés (13) ;
    - après une ouverture manuelle du menu par Simon, le téléchargement s'est
      joué en entier : requête gardée, trois états du menu, drapeau, commit ;
    - Link est resté ensuite dans la pose où le menu l'avait laissé, sans
      contrôle.
  - *Correctifs* :
    - client (`botw_client/pause_menu.py`, lecture seule) : il diffère une
      livraison `rune_download` tant que carte et inventaire ne sont pas
      chargés. Le repos (`at_rest`) ne sert qu'à la sonde. La jumelle
      silencieuse n'attend pas ;
    - événement : 30 images d'attente après `IsDownloadDemo`
      (`DOWNLOAD_SETTLE`), pour que la carte se repose, HUD masqué, avant
      l'écran. Le terminal, lui, a 20 s de cinématique avant ;
    - fin de l'événement : la partie joueur de `Demo041_0<SheikPadSetOff>`
      (`GameROMPlayer` `Demo_PlayASAdapt` `SheikPadSetOff` en attendant la
      fin, puis `DemoWait`), puis 20 images, comme le terminal.
  - Non repris du terminal : caméras, animations du terminal, musique et le
    conseil `Guide_ItemUse`.
- **Livraisons sans fenêtre du jeu** (Tablette : capteur ; bride, selle) :
  hébergées dans `OperationGuide` avec `QUIET_EVENT_INFO`, comme les jumelles,
  pour ne pas mettre le jeu en pause ni faire clignoter le HUD (vu le 26/09
  avec une rune livrée sans écran). Catalogue : `flow` sur l'étape
  (`host_of`).
