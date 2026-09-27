# Modèle 3D de l'objet AP — mode d'emploi

Le modèle de l'objet Archipelago est posé sur celui de l'ambre (`Item_Ore_F`) :
on garde son squelette, son matériau et ses shaders, on remplace le maillage et
les textures. Il devient le fichier `Model/AP_Item` ; l'ambre du jeu garde le
sien. Il est affiché dans les boutiques et sur les étals.

## Dossiers (`assets/models/ap_item/`)

| Dossier | Contenu | Règle |
|---|---|---|
| racine | `reference.webp` (le logo), `build_ap_item.py` | la source |
| `game/` | ce qu'on importe dans Switch Toolbox : `ap_item.fbx`, 5 textures PNG, `ap_item.blend` | produit par `build_ap_item.py` |
| `wiiu/` | les exports : `AP_Item.sbfres`, `AP_Item.Tex1.sbfres`, `AP_Item.Tex2.sbfres` | c'est ce que le jeu utilise |

Les fichiers de l'ambre (`Model/Item_Ore_F.sbfres`, `.Tex1`, `.Tex2`, dans le jeu de base) ne sont pas fournis : ce
sont des fichiers du jeu. Pour refaire le modèle, en extraire des copies de votre propre jeu. La construction du pack
n'en a pas besoin : elle garde seulement leur empreinte (`MODEL_REFERENCE`, dans `botw_patch/shops.py`).

## Les trois règles

1. **Mètres, Y vers le haut, posé sur l'origine.** Blender écrit ses FBX en
   centimètres : exporté par défaut, le médaillon de 28 cm est devenu 28 m dans
   le jeu. `game/ap_item.fbx` est déjà juste (échelle 0,01, axes convertis dans
   les sommets, y de 0 à 0,025). À la main dans Blender : *Export → FBX*,
   « Selected Objects », **Scale 0.01**, **Apply Transform** coché, et le
   dessous de l'objet à z = 0.
2. **Textures aux dimensions de l'original.** Une texture de 512 px à la place
   d'une de 256 px a gardé la taille des mipmaps de l'originale : le jeu a
   affiché des données incohérentes (anneaux orange, taches grises) et Switch
   Toolbox plante en l'affichant. Tailles de l'ambre : `_Alb` 256,
   `_Bright_Alb` 128, `_Nrm` 128, `_Emm` 128, `_Spm` 64.
3. **Remplacer les 5 textures, dans Tex1 et dans Tex2.** Sinon le relief, les
   reflets et la lueur de l'ambre s'appliquent au médaillon. `game/` fournit
   des versions neutres (relief plat, sans reflet ni lueur).

## Refaire le modèle

1. Source : modifier `reference.webp`, puis reconstruire `game/` avec Blender en
   arrière-plan, sans fenêtre (le dossier de sortie doit contenir
   `reference.webp`) :

   ```
   blender --background --factory-startup --python assets\models\ap_item\build_ap_item.py -- assets\models\ap_item\game
   ```

2. **Switch Toolbox**, sur des **copies** des fichiers de l'ambre :
   - `Item_Ore_F.sbfres` : *Models → Item_Ore_F → Meshes*, clic droit sur le
     maillage → *Replace* → `game/ap_item.fbx` ; garder le matériau et le
     format d'origine, **échelle 1** dans la fenêtre d'import ;
   - `Item_Ore_F.Tex1.sbfres`, puis `Item_Ore_F.Tex2.sbfres` : *Textures*,
     clic droit → *Replace* pour chacune :
     `_Alb` ← `ap_item_albedo.png`, `_Bright_Alb` ← `ap_item_Bright_Alb.png`,
     `_Nrm` ← `ap_item_Nrm.png`, `_Emm` ← `ap_item_Emm.png`,
     `_Spm` ← `ap_item_Spm.png` ; format proposé, mipmaps générés ;
   - enregistrer dans `wiiu/` sous `AP_Item.sbfres`, `AP_Item.Tex1.sbfres`,
     `AP_Item.Tex2.sbfres`. Ne pas renommer les textures ni le modèle **à
     l'intérieur** : le matériau les cherche par ces noms.
3. **Vérifier sans lancer le jeu** : la construction des ressources contrôle le
   modèle (`botw_patch.shop_items.check_model`), par exemple avec
   `venv\Scripts\python -m unittest tests.test_resources_from_source`. Elle
   refuse, avec la raison : un format ou un nom de modèle différent de l'ambre,
   une texture dont la disposition (dimensions, mipmaps, tailles de données)
   n'est pas celle de l'original, Tex1 et Tex2 discordants, un modèle hors de
   10 cm – 1 m, ou qui descend sous son origine.
4. **Tester** dans une partie avec des boutiques ou des étals.

## Noms internes : renommés automatiquement

Un fichier BFRES porte son propre nom, celui de son modèle et ceux de ses
textures, indépendamment du nom du fichier. Laissés à `Item_Ore_F`, ils ont
fait afficher au jeu **les textures de l'ambre** sur le médaillon, alors que
Switch Toolbox montrait les bonnes. La construction les renomme donc en
`AP_Item_00` (même longueur : aucun décalage ne bouge) dans les trois fichiers,
puis vérifie que le jeu retrouve chaque nom dans ses tables de recherche. Les
fichiers du jeu deviennent `Model/AP_Item_00.*`. **Rien à faire dans Switch
Toolbox** : garder les noms de l'ambre et exporter en `wiiu/AP_Item*.sbfres`.

Détail des tables de recherche (vérifié sur l'ambre et TitleBG.pack) : arbre à
bits, références décroissantes depuis la racine, bit `ref & 7` (poids faible
d'abord) de l'octet `ref >> 3` compté depuis le début du nom ; une table à une
seule entrée teste le bit à 1 le plus élevé du nom. Renommer l'ambre en
`AP_Item_00` puis de nouveau en `Item_Ore_F` redonne l'original à l'octet près.

## Écarts connus de Switch Toolbox (acceptés)

Relevés sur les cinq textures après enregistrement par l'outil :

- `Tex2` enregistré avec une taille d'image de 0 : ce fichier ne porte que les
  mipmaps (l'image est dans `Tex1`, l'original le montre aussi par sa taille).
  Accepté par la vérification, noté `toolbox_tex2_image_size_zero` ;
- `Tex1` : paramètre de swizzle différent (`0x20000` → `0xf0000` pour `_Alb`) ;
  c'est un choix d'encodage de l'outil, cohérent avec ses données.

Sans effet visible en jeu.

## Historique

- Premier modèle : affiché en main et au sol, ramassable, mais 28 m de large
  (FBX en centimètres), sous son origine, texture 512 px avec les mipmaps de
  256 px. Ces trois défauts sont désormais refusés avant Cemu.
- Deuxième : bonne taille au sol, mais les textures de l'ambre, à cause des noms
  internes. Corrigé par le renommage automatique.
- Troisième : **validé**, bonne texture et bonne taille au sol. La position en
  main reste bancale, accepté : l'objet AP est retiré de la poche juste après
  l'achat, il n'est jamais tenu en jeu normal.
