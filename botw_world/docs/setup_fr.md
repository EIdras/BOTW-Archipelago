# Guide de configuration multiworld de Breath of the Wild

Ce guide installe les outils du projet BOTW Archipelago sous Windows : générer une seed, construire le pack de jeu de
cette seed, et la jouer dans Cemu avec le client Archipelago, seul ou avec d'autres joueurs, dans une salle
d'archipelago.gg ou sur votre propre serveur. Les commandes se lancent depuis le dossier du projet.

## Prérequis

- Windows 10 ou 11.
- [Cemu](https://cemu.info/) 2.x, avec **The Legend of Zelda: Breath of the Wild, Wii U, version européenne (EUR)**,
  depuis votre propre console : le jeu dans la liste des jeux de Cemu, la mise à jour **v208** (1.5.0) et le DLC
  installés dans Cemu (Fichier > Installer un titre, une mise à jour ou un DLC). Lancez le jeu une fois dans Cemu.
- Python 3.12.
- Une copie des sources d'[Archipelago](https://github.com/ArchipelagoMW/Archipelago) **0.6.7**.

Les autres versions du jeu (US, JP, Switch) ne sont pas prises en charge : le code natif de l'intégration est construit
pour cet exécutable précis.

## Installation

```bat
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python tools\prepare_ap_runtime.py --source <sources d'Archipelago 0.6.7>
venv\Scripts\python tools\cemu_profile.py --cemu <chemin de Cemu.exe>
```

- `prepare_ap_runtime.py` copie le cœur d'Archipelago et ce monde dans `.build\ap-runtime`, qui sert à la génération
  et au serveur local.
- `cemu_profile.py` trouve le jeu, la mise à jour et le DLC dans votre installation de Cemu et vérifie leurs versions,
  puis copie Cemu, la mise à jour, le DLC et les sauvegardes du jeu dans un profil isolé, `.build\cemu-validation`
  (environ 5 Go). Votre installation de Cemu n'est jamais modifiée. Si elle n'est pas trouvée, nommer son dossier
  utilisateur, celui qui contient `settings.xml`, avec `--user-data`. `tools\cemu_install.py` affiche ce qui est
  trouvé, sans rien copier.

## Générer une seed

**Seul** : modifier `players\BOTW.yaml` (nom du joueur, objectif, options de boutiques, DeathLink, pièges), puis :

```bat
venv\Scripts\python tools\generate_native.py
```

La seed est écrite dans `.build\native-seeds\AP_<seed>.zip`.

**Avec d'autres joueurs** : la personne qui génère a besoin des fichiers YAML de tous les joueurs et des mondes de
leurs jeux. Pour Breath of the Wild, c'est `botw.apworld` (`venv\Scripts\python tools\package_native.py` l'écrit dans
`dist\`), à installer dans le dossier `custom_worlds` d'Archipelago. Elle génère avec Archipelago comme d'habitude ;
le zip de la seed contient, pour chaque joueur de Breath of the Wild, un fichier de slot
`AP_<seed>_P<n>_<nom>.apbotw.json`. Pour héberger la partie sur [archipelago.gg](https://archipelago.gg), téléverser
ce zip sur sa page « Host Game » : elle donne ensuite l'adresse de la salle, `archipelago.gg:<port>`.

## Construire le pack de jeu

```bat
venv\Scripts\python tools\play_seed.py <fichier de la seed>
```

- Le fichier de la seed est son zip, ou votre propre fichier de slot (`.apbotw.json`, tiré du zip), qui suffit pour
  jouer dans une salle hébergée ailleurs. Quand le zip contient plusieurs joueurs de Breath of the Wild, désigner le
  vôtre avec `--slot <nom>`.
- Le pack est construit à partir de la mise à jour copiée dans le profil isolé.

L'outil vérifie la seed, en garde une copie dans `.build\play-seeds\<seed>\`, construit le pack lié à votre slot de
cette seed et le sélectionne.

## Jouer

Dans une salle hébergée ailleurs, archipelago.gg par exemple :

```bat
Play.cmd --seed <seed> --connect archipelago.gg:<port>
```

Ajouter `--password <mot de passe>` si la salle en a un. Sur votre propre serveur, à partir du zip de la seed :

```bat
Play.cmd --seed <seed>
```

Cela démarre le serveur Archipelago sur cet ordinateur, port 38281 ; il garde son état à côté de la seed, et la
progression se conserve d'une session à l'autre. Avec `--host`, le serveur écoute aussi le réseau : les autres joueurs
se connectent à l'adresse de votre ordinateur, port 38281 (par Internet, ce port doit être redirigé vers votre
ordinateur).

Dans tous les cas, Cemu démarre sur son profil isolé avec le seul pack de la seed, puis le client. Pour une nouvelle
seed, commencer une **nouvelle partie** : une sauvegarde reste liée à la seed avec laquelle elle a été commencée.
Jouer normalement ; fermer Cemu termine la session. Le client et les textes ajoutés au jeu sont en anglais.

Les lignes tapées dans la console partent au serveur comme commandes (`/hint`, `/players`, `/status`... ; envoyées à
une salle distante sous la forme `!hint`, `!players`...) ou comme chat. Le client ajoute ses propres commandes :

| Commande                | Effet                                                         |
|-------------------------|---------------------------------------------------------------|
| `/ap-tip <texte>`       | afficher une ligne dans le journal Archipelago du jeu (test)  |
| `/ap-disconnect [s]`    | simuler une coupure du serveur pendant `s` secondes           |
| `/ap-evt [n\|reset]`     | lister les dernières requêtes d'événement du jeu (diagnostic) |
| `/ap-deathlink [cause]` | tuer Link comme un DeathLink reçu (test, envoyé à personne)   |

## En cas de problème

Chaque session écrit ses journaux dans `.build\play-seeds\<seed>\sessions\<date>\` : le journal du client, celui de
Cemu et un résumé. Joindre ce dossier pour signaler un problème.
