# Guide de configuration multiworld de Breath of the Wild

Ce guide installe les outils du projet BOTW Archipelago sous Windows : générer une seed, construire le pack de jeu de
cette seed, et la jouer dans Cemu avec le client Archipelago. Les commandes se lancent depuis le dossier du projet.

## Prérequis

- Windows 10 ou 11.
- [Cemu](https://cemu.info/) 2.x, avec **The Legend of Zelda: Breath of the Wild, Wii U, version européenne (EUR)**,
  la mise à jour **v208** (1.5.0) et le DLC installés, depuis votre propre console.
- Le fichier `code/U-King.rpx` du jeu dans cette version, extrait de votre propre console. Le constructeur de pack
  vérifie son SHA-256.
- Python 3.12.
- Une copie des sources d'[Archipelago](https://github.com/ArchipelagoMW/Archipelago) **0.6.7**.

Les autres versions du jeu (US, JP, Switch) ne sont pas prises en charge : le code natif de l'intégration est construit
pour cet exécutable précis.

## Installation

```bat
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python tools\prepare_ap_runtime.py --source <sources d'Archipelago 0.6.7>
venv\Scripts\python tools\cemu_profile.py --cemu <chemin de Cemu.exe> --user-data <dossier utilisateur de Cemu>
copy botw_client.example.json botw_client.json
```

- `prepare_ap_runtime.py` copie le cœur d'Archipelago et ce monde dans `.build\ap-runtime`, qui sert à la génération
  et au serveur local.
- `cemu_profile.py` copie Cemu, la mise à jour, le DLC et les sauvegardes du jeu dans un profil isolé,
  `.build\cemu-validation`. Votre installation de Cemu n'est jamais modifiée. Le dossier utilisateur de Cemu est
  celui qui contient `settings.xml` et `mlc01`.
- Dans `botw_client.json`, renseigner `game` avec le chemin du `U-King.rpx` du jeu.

## Générer une seed

Modifier `players\BOTW.yaml` (nom du joueur, objectif, options de boutiques), puis :

```bat
venv\Scripts\python tools\generate_native.py
```

L'archive de la multiworld est écrite dans `.build\native-seeds\AP_<seed>.zip`. Seules les seeds à un seul joueur de
Breath of the Wild sont prises en charge pour l'instant.

## Construire le pack de jeu

```bat
venv\Scripts\python tools\play_seed.py .build\native-seeds\AP_<seed>.zip --content <dossier content de la mise à jour> --rpx <U-King.rpx>
```

Le dossier `content` de la mise à jour installée est en général
`%APPDATA%\Cemu\mlc01\usr\title\0005000e\101c9500\content`. L'outil vérifie l'archive, en garde une copie dans
`.build\play-seeds\<seed>\`, lit l'identité de session auprès d'un serveur local, construit le pack lié à cette seed et
le sélectionne.

## Jouer

```bat
Play.cmd --seed <seed>
```

Cela démarre le serveur Archipelago sur `127.0.0.1:38281`, Cemu sur son profil isolé avec le seul pack de la seed, et
le client. Pour une nouvelle seed, commencer une **nouvelle partie** : une sauvegarde reste liée à la seed avec laquelle
elle a été commencée. Jouer normalement ; fermer Cemu termine la session. Le serveur garde son état à côté de la seed :
la progression se conserve d'une session à l'autre. Le client et les textes ajoutés au jeu sont en anglais.

Les lignes tapées dans la console partent au serveur comme commandes (`/hint`, `/players`, `/status`...) ou comme
chat. Le client ajoute ses propres commandes :

| Commande                | Effet                                                         |
|-------------------------|---------------------------------------------------------------|
| `/ap-tip <texte>`       | afficher une ligne dans le journal Archipelago du jeu (test)  |
| `/ap-disconnect [s]`    | simuler une coupure du serveur pendant `s` secondes           |
| `/ap-evt [n\|reset]`     | lister les dernières requêtes d'événement du jeu (diagnostic) |

## En cas de problème

Chaque session écrit ses journaux dans `.build\play-seeds\<seed>\sessions\<date>\` : le journal du client, celui de
Cemu et un résumé. Joindre ce dossier pour signaler un problème.
