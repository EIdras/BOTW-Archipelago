# Guide de configuration multiworld de Breath of the Wild

Ce guide permet de jouer à The Legend of Zelda: Breath of the Wild dans un multiworld Archipelago, sous Windows, dans
l'émulateur Cemu : l'installation, rejoindre une salle et, pour la personne qui l'héberge, générer la seed.

## Ce qu'il faut

- Windows 10 ou 11.
- [Cemu](https://cemu.info/) 2.x, avec **Breath of the Wild, Wii U, version européenne (EUR)**, depuis votre propre
  console :
  - le jeu dans la liste des jeux de Cemu ;
  - sa mise à jour **v208** (1.5.0) et le **DLC** installés dans Cemu (Fichier > Installer un titre, une mise à jour
    ou un DLC).

  Lancez le jeu une fois dans Cemu. Les autres versions du jeu (US, JP, Switch) ne sont pas prises en charge :
  l'intégration est construite pour cet exécutable précis.
- Environ 5 Go d'espace disque libre, et 140 Mo de plus par seed.
- La salle qui héberge la partie : sa page sur archipelago.gg propose votre **fichier de slot** (`.apbotw`,
  « Download Patch File... » à côté de votre nom) et affiche l'**adresse de la salle**.

## Installation

1. Télécharger `BOTW-Archipelago-<version>-Windows.zip` dans les
   [releases](https://github.com/EIdras/BOTW-Archipelago/releases) du projet, parmi les Assets de la release (pas
   « Source code », qu'ajoute GitHub et qui n'a pas de Python).
2. Clic droit sur le zip > Propriétés, cocher **Débloquer**, OK. Sinon Windows demande de confirmer chaque programme
   la première fois qu'il se lance.
3. Le décompresser où vous voulez, dans vos Documents par exemple (pas dans Program Files). Rien d'autre à installer :
   il apporte son propre Python.

## Jouer

Lancer `BOTW Archipelago.cmd` (ou déposer dessus votre fichier de slot). Si Windows dit avoir protégé votre
ordinateur, choisir « Informations complémentaires », puis « Exécuter quand même ».

1. **La première fois**, une fenêtre demande où est `Cemu.exe`. Le lanceur trouve Breath of the Wild, sa mise à jour et
   le DLC dans cette installation et les vérifie, puis copie Cemu, la mise à jour, le DLC et vos sauvegardes dans un
   profil à lui (environ 5 Go). Votre installation de Cemu n'est jamais modifiée.
2. **La seed** : choisir votre fichier de slot. Son pack de jeu se construit, en une minute environ. Les fois suivantes,
   le lanceur liste les seeds déjà préparées, la dernière jouée en tête.
3. **La salle** : son adresse, comme sa page l'affiche (`archipelago.gg:38281`), est déjà remplie quand votre fichier
   de slot vient de cette page : Entrée, puis le mot de passe de la salle, ou Entrée si elle n'en a pas. L'adresse est
   retenue pour la seed.

Cemu démarre avec le pack de jeu de la seed, puis le client Archipelago, dans la fenêtre du lanceur. **Commencer une
nouvelle partie** pour une nouvelle seed : une sauvegarde reste liée à la seed avec laquelle elle a été commencée.
Jouer normalement : vos objets arrivent dans le jeu, le journal Archipelago (en haut à droite de l'écran) montre ce qui
est envoyé et reçu, et le logo Archipelago du HUD est en couleur tant que vous êtes connecté. Fermer Cemu termine la
session ; laisser la fenêtre du lanceur ouverte jusque-là. Le client et les textes ajoutés au jeu sont en anglais.

Archipelago nomme les lieux et les objets en anglais, et le jeu en français les nomme souvent autrement (Tah Muhl
Shrine est le sanctuaire de Ta'Mur) : la [table des noms en français](names_fr.md) donne la correspondance, pour
chaque lieu et chaque objet.

**Tracker avec carte** : si [PopTracker](https://github.com/black-sliver/PopTracker) est installé (lancé une
fois, pour que son dossier `PopTracker/packs` existe), le lanceur installe le pack « Breath of the Wild
Archipelago » avant la session. Dans PopTracker, charger le pack, cliquer sur « AP » et saisir l'adresse de la
salle, votre nom de slot et le mot de passe : la carte montre chaque lieu, coloré selon ce que vos objets
permettent, et les coche au fil de la partie. La carte et une partie des icônes viennent de votre propre jeu ;
pour les autres (armures, runes...), vous pouvez déposer les icônes du jeu, en PNG nommés comme les objets, dans
`%LOCALAPPDATA%\BOTW Archipelago\poptracker\icons` : elles servent dès la session suivante.

Les lignes tapées dans la fenêtre du lanceur partent à la salle comme chat, ou comme commandes : `/hint <objet>`,
`/players`, `/status`... (envoyées à la salle sous la forme `!hint`, `!players`...). Le client en ajoute quelques-unes,
pour les tests et les signalements de bugs :

| Commande                | Effet                                                         |
|-------------------------|---------------------------------------------------------------|
| `/ap-tip <texte>`       | afficher une ligne dans le journal Archipelago du jeu         |
| `/ap-disconnect [s]`    | simuler une coupure du serveur pendant `s` secondes           |
| `/ap-evt [n\|reset]`     | lister les dernières requêtes d'événement du jeu              |
| `/ap-deathlink [cause]` | tuer Link comme un DeathLink reçu (envoyé à personne)         |

## Générer et héberger une seed

La personne qui héberge la partie génère la seed avec
[Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) **0.6.7**, comme pour n'importe quel jeu :

1. Mettre `botw.apworld`, tiré des mêmes [releases](https://github.com/EIdras/BOTW-Archipelago/releases), dans le
   dossier `custom_worlds` d'Archipelago.
2. Mettre le fichier YAML de chaque joueur dans le dossier `Players` d'Archipelago. Pour Breath of the Wild, partir de
   `players\BOTW.yaml` de la release (nom du joueur, objectif, options de boutiques, DeathLink, pièges), ou du modèle
   qu'écrit le Launcher d'Archipelago (« Generate Template Options »).
3. Lancer « Generate » dans le Launcher d'Archipelago. Le zip de la seed, dans le dossier `output` d'Archipelago,
   contient un fichier de slot `AP_<seed>_P<n>_<nom>.apbotw` pour chaque joueur de Breath of the Wild.

Pour héberger la seed sur [archipelago.gg](https://archipelago.gg), téléverser ce zip sur sa page « Host Game » : la
page de la salle donne son adresse, `archipelago.gg:<port>`, et le fichier de slot de chaque joueur à télécharger. Pour
l'héberger sur votre ordinateur, ouvrir le zip avec « Archipelago Server » dans le Launcher d'Archipelago ; vous vous
connectez à `localhost:38281`, les autres joueurs à l'adresse de votre ordinateur, port 38281 (par Internet, ce port
doit être redirigé vers votre ordinateur).

Jouer seul se fait de la même façon : générer une seed avec votre seul YAML, l'héberger, et la rejoindre.

## Mettre à jour

Télécharger la nouvelle release et la décompresser, à la place de l'ancienne ou ailleurs. Votre profil, vos seeds et
leurs sauvegardes sont gardés dans `%LOCALAPPDATA%\BOTW Archipelago`, quel que soit le dossier de la release. La
première fois que vous jouez une seed avec la nouvelle version, le lanceur reconstruit son pack de jeu.

Une release joue les seeds des versions précédentes. Si une seed demande une version plus récente, le lanceur dit
laquelle : la télécharger, et donner à la personne qui héberge le `botw.apworld` correspondant pour les seeds suivantes.

## Désinstaller

Supprimer le dossier de la release, et `%LOCALAPPDATA%\BOTW Archipelago` : le profil, avec les sauvegardes de vos
parties Archipelago, et les seeds. Votre installation de Cemu n'a jamais été modifiée.

## En cas de problème

- **Le lanceur refuse votre Cemu** : son message dit ce qui manque (une autre version du jeu, la mise à jour ou le DLC
  non installés, un jeu listé par Cemu qui a été déplacé...). Corriger dans Cemu, y lancer le jeu une fois, et relancer.
- **« Close Cemu before preparing a session »** : le lanceur démarre Cemu lui-même ; fermer le vôtre d'abord.
- **Le jeu ne réagit pas à votre manette** : le profil n'a copié aucun réglage de manette de votre Cemu. Dans la
  fenêtre du jeu, ouvrir Options > Paramètres d'entrée de Cemu et choisir votre manette pour le joueur 1 ; le profil
  la garde.
- **Chaque session écrit ses journaux** dans `%LOCALAPPDATA%\BOTW Archipelago\play-seeds\<seed>\sessions\<date>\` : le
  journal du client, celui de Cemu et un résumé. Joindre ce dossier pour
  [signaler un problème](https://github.com/EIdras/BOTW-Archipelago/issues).

Pour jouer depuis le code source plutôt qu'une release : voir
[le développement](https://github.com/EIdras/BOTW-Archipelago/blob/master/docs/development.md#running-from-source).
