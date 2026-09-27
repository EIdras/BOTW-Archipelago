# Indicateur de connexion AP dans le HUD

Le logo Archipelago en bas à gauche du HUD : **en couleur** quand le client
est connecté au serveur AP, **gris** sinon (client absent, coupure,
reconnexion en cours). Il se cache avec le reste du HUD (menus,
cinématiques).

État : ressources validées en jeu (25/09 : le jeu démarre, le logo s'affiche
au bon endroit, il se masque avec le HUD, la bascule fonctionne et le jeu ne
réécrit jamais nos bits). Suivi de la connexion par le client : **validé
en jeu** (25/09 : gris au chargement, couleur une fois connecté, gris pendant
`/ap-coupure 20`, couleur à la reconnexion).

## Comment ça marche

```
Bootup.pack > Layout/Common.sblarc
  blyt/MainScreen_00.bflyt     le HUD : RootPane > N_All_00 > ... > Pa_Time_00
                                                            > Pa_APStatus_00  (ajouté)
  blyt/PaAPStatus_00.bflyt     notre layout : RootPane > P_APOffline_00 (gris, visible)
                                                       > P_APOnline_00  (couleur, caché)
  timg/Nt_APOffline_00^l.bflim / Nt_APOnline_00^l.bflim   les deux logos, 64x64
```

1. **Ressources** (`botw_patch/hud_layout.py`, appelé par
   `tools/build_resources_from_source.py` pour **tous** les paquets) :
   - une part `Pa_APStatus_00` est ajoutée comme dernier enfant de
     `N_All_00`, le nœud qui porte tout le HUD : elle en hérite la
     visibilité ;
   - elle pointe vers le layout `PaAPStatus_00`, construit depuis le layout
     vanilla `PaIconChallenge_00` (une image, un matériau, une texture), avec
     deux images et deux textures ;
   - le logo gris est visible par défaut : sans client, rien n'est connecté.
2. **Client** (`botw_client/hud_indicator.py`, appelé par le runtime deux
   fois par seconde au plus) :
   - il retrouve nos deux images en mémoire, comme `panes.py` : gestionnaire
     d'interface en `0x1047E650`, table des écrans, layout de chaque écran,
     arbre de panneaux, nom en `+0x80` ;
   - il écrit le bit visible (`+0x44`, bit 0) de chaque image selon
     `ap.connected`. Il n'écrit que si ça change, et vérifie les noms avant
     d'écrire : si l'écran a été reconstruit, il cherche à nouveau (au plus
     toutes les 2 s) ;
   - à l'arrêt propre du client, il remet le logo gris.
3. Les noms communs aux deux côtés sont dans `botw_client/hud_protocol.py`.

Aucun hook de code, aucune écriture à chaque image : une écriture d'un octet
quand l'état change.

## Modifier les réglages

Tout est dans l'en-tête de `botw_patch/hud_layout.py` :

| Réglage | Constante | Valeur actuelle |
|---|---|---|
| Position (centre du logo, repère 1280×720, origine au centre de l'écran, y vers le haut) | `POSITION` | `(-590.0, -310.0)` : bas gauche |
| Taille affichée (pixels du repère 1280×720) | `SIZE` | `44.0` |
| Résolution des textures (diviseur entier de 512) | `TEXTURE_SIZE` | `64` |
| Gris du logo hors ligne (0 = noir, 1 = gris clair) | paramètre `dim` de `grey()` | `0.55` |
| Parent dans le HUD | `PARENT_LAST` (la part est insérée après ce frère) | `Pa_Time_00`, sous `N_All_00` |

Repères utiles : les cœurs sont vers (-434, 310), les pouvoirs des prodiges
en x = -557 (y de 40 à 190), la jauge de température vers (392, -222).

**Changer le logo** : les deux textures sont tirées de
`assets/wiiu/Item_AP.sbitemico` (le logo 512 du dépôt, aussi utilisé pour
l'icône des fenêtres et des boutiques). Changer ce fichier change tout. Son
empreinte est vérifiée par `tools/build_resource_base_from_source.py`
(`ICON_SHA256`) et par `tests/test_resource_base_from_source.py`, à mettre à
jour avec lui.

**Après un changement** :

```
venv\Scripts\python.exe -m unittest tests.test_hud_layout tests.test_hud_indicator
venv\Scripts\python.exe tools\play_seed.py <seed.zip> --content <content> --rpx U-King.rpx
```

Les empreintes de référence de `tests/test_resources_from_source.py` et
`tests/test_pack_from_source.py` changent avec les ressources : les recalculer.

**Vérifier en jeu sans client** :
`venv\Scripts\python.exe tools\cemu\hudprobe.py` trouve la part et ses
logos. Avec `--bascule 10`, le logo couleur s'affiche 10 s, puis l'état
d'origine revient.

## Détails de format (mesurés)

- FLYT et FLIM 5.2, gros-boutistes. Une section = magic, taille (en-tête de
  8 octets compris), corps. Aller-retour octet pour octet vérifié sur les 330
  `.bflyt` de `Common.sblarc`.
- Bloc de panneau : drapeaux (bit 0 visible), origine, alpha, échelle de
  part, nom[24], données utilisateur[8], translation en `+0x24` du corps,
  taille en `+0x44`. Image : index de matériau en `+0x5c`. Part : nombre de
  propriétés, grossissement, nom du layout. Matériau : nom[28], couleurs
  noire et blanche (le modèle est teinté en jaune, nous non), index de
  texture en `+0x28`.
- Textures `^l` = FLIM format 20 (RGBA8 sRGB), tile mode 4, pavage GX2 de
  `tools/bitemico.py`. Largeur arrondie à 32, hauteur à 16. Vérifié sur les 8
  textures vanilla de ce format.
- Taille : `Layout/Common.blarc` passe de 31 418 128 à 31 459 088 octets
  (croissance réelle ajoutée à la marge vanilla).

## Historique

- 25/09, analyse : faisable proprement, le risque étant de savoir si le jeu
  crée une part qu'il ne connaît pas.
- 25/09, étape 1 : ressources, puis essai de Simon. Réponse : oui, écran
  `0x25`, logos atteignables depuis la part, 0 réécriture en 10 s.
- 25/09, étape 2 : suivi de la connexion par le client.
- Écartés : détourner une part existante (information perdue pour le
  joueur) ; dessiner par un hook de rendu (contraire à la règle du projet).
