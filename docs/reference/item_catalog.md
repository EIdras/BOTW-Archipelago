# Catalogue des objets

Sources : [`botw_world/data/items.json`](../../botw_world/data/items.json) définit le pool, les identifiants et la
classification ; [`data/item_map.json`](../../data/item_map.json) définit l'effet dans le jeu (colonne `delivery`) et
ce qui l'a validé (colonne `evidence`). Le spoiler de chaque seed (`AP_*_Spoiler.txt` dans l'archive générée) donne les
placements.

## Taille du pool

111 objets déclarés, complétés par des `Rupee Bundle` jusqu'au nombre de locations : 152 locations sans les options de
boutique (41 bourses de rubis), jusqu'à 212 avec deux objets par boutique et par étal (101 bourses). `Defeat Calamity
Ganon` est la location de victoire, sans objet.

## Progression et équipement

| Objet AP | Nombre | Effet dans le jeu |
|---|---:|---|
| Paraglider | 1 | la paravoile (`PlayerStole2`) |
| Magnesis, Remote Bomb, Stasis, Cryonis | 1 chacun | le module, présenté par l'écran de téléchargement de la tablette ; sélectionné |
| Sheikah Sensor | 1 | les drapeaux du détecteur |
| Warm Doublet | 1 | le pourpoint |
| Snowquill, Flamebreaker, Desert Voe, Zora, Rubber Set | 1 chacun | les trois pièces de l'ensemble |
| Revali's Gale, Daruk's Protection, Urbosa's Fury, Mipha's Grace | 1 chacun | le pouvoir du prodige, par sa fenêtre d'obtention |
| Progressive Climbing Gear | 3 | torse, tête, jambes, dans cet ordre |
| Progressive Stealth Set | 3 | torse, tête, jambes, dans cet ordre |
| Heart Container | 17 | un cœur, par la fenêtre d'obtention du jeu |
| Stamina Vessel | 5 | un segment d'endurance, par la fenêtre d'obtention du jeu |
| Master Sword, Hylian Shield, Champion's Tunic | 1 chacun | l'équipement |
| Ancient Bridle, Ancient Saddle | 1 chacun | l'équipement de cheval |
| Barbarian, Ancient, Radiant Set | 1 chacun | les trois pièces de l'ensemble |

Les ensembles sont volontairement puissants : ce ne sont pas des objets de remplissage.

## Remplissage et pièges

| Objet AP | Nombre | Effet dans le jeu |
|---|---:|---|
| Spirit Orb | 20 | un emblème de triomphe |
| Ancient Core | 10 | un cœur antique |
| Star Fragment | 8 | un fragment d'étoile |
| Korok Seed | 15 | une noix Korogu |
| Fairy | 6 | une fée |
| Rupee Bundle | selon les locations | 20 rubis |
| Blood Moon, Weapon Shatter | 4 chacun | déclarés, **non générés** : pas encore d'effet automatique validé |

Un objet reçu est livré par le jeu lui-même : fenêtre d'obtention quand l'objet en a une, écran de téléchargement pour
un module, sinon directement dans l'inventaire. Rendu après le rechargement d'une sauvegarde plus ancienne, il revient
en silence, puis une fenêtre Archipelago résume les objets rendus (voir [messages AP](ap_messages.md)).
