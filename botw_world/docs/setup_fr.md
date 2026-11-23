# Breath of the Wild dans Archipelago : démarrage rapide

Ce guide court permet de jouer à Breath of the Wild dans une partie Archipelago, sous Windows, dans l'émulateur Cemu.
Le reste de la documentation est en anglais : chaque section renvoie à sa page.

## Ce qu'il faut

- Windows 10 ou 11 et [Cemu](https://cemu.info/) 2.x.
- Breath of the Wild **Wii U**, version européenne, américaine ou japonaise, depuis votre propre console, avec sa
  **mise à jour v208** et le **DLC** installés dans Cemu (Fichier > Installer un titre, une mise à jour ou un DLC).
  Lancez le jeu une fois dans Cemu. La version Switch n'est pas prise en charge.
- Environ 5 Go d'espace disque libre, et 140 Mo de plus par seed. Avec `shrine_chest_items`, environ 1 Go de plus,
  une seule fois pour toutes les seeds, et le jeu de base installé en dossier (pas en fichier `.wua` ou `.wud`).
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 ou plus récent.
- Le lien de la page de la salle, ou votre **fichier de slot** (`.apbotw`) : sur la page de la salle,
  « Download Patch File... » à côté de votre nom.

## Installer

1. Installer [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 ou plus récent, si ce
   n'est pas déjà fait : le programme `Setup` de sa dernière release.
2. Télécharger `botw.apworld` dans les [releases](https://github.com/EIdras/BOTW-Archipelago/releases), parmi les
   **Assets**.
3. Ouvrir l'**Archipelago Launcher**, cliquer sur **Install APWorld** et choisir `botw.apworld`. Fermer le Launcher
   et le rouvrir.

BOTW Archipelago tourne dans Archipelago : rien d'autre à installer. L'hôte génère la seed avec le même
`botw.apworld`.

## Jouer

Dans l'Archipelago Launcher, cliquer sur **BOTW Archipelago**. La première fois, il télécharge les bibliothèques
dont il a besoin (environ 14 Mo, depuis internet), puis sa fenêtre s'ouvre.

1. **Cemu** : la première fois, **Choose Cemu...** demande où est `Cemu.exe`, puis **Create the profile** copie
   Cemu et vos sauvegardes dans un profil à lui (environ 5 Go). Votre installation de Cemu n'est jamais modifiée.
2. **La seed** : **Add from a room link...**, puis coller le lien de la page de la salle
   (`https://archipelago.gg/room/...`) : le lanceur y télécharge votre fichier de slot. Ou bien **Add a seed...**
   (Ctrl+O) et choisir le fichier de slot, ou l'ouvrir avec **Open Patch** dans l'Archipelago Launcher. Son pack
   de jeu se construit en une minute environ.
3. **La salle** : son adresse (`archipelago.gg:38281`) est déjà remplie quand le fichier de slot vient de sa page.
   Taper le mot de passe de la salle s'il y en a un, puis **Play**.

Cemu démarre, et la fenêtre suit la session : les objets envoyés et reçus, en couleurs comme dans le client
d'Archipelago, le chat de la salle et ses commandes (`/hint <objet>`). La page **Hints** liste les indices de la
salle et en demande pendant une session. **Commencez une nouvelle partie** pour une nouvelle seed : une sauvegarde
reste liée à sa seed. Fermer Cemu termine la session ; **Play again** la relance.

Le lanceur propose lui-même les nouvelles versions : **Install** remplace votre `botw.apworld`, puis il faut
fermer et rouvrir Archipelago. Une seed d'avant la version 0.4.0 s'ouvre avec **Play with version X**, qui
télécharge sa version. En venant de la version 0.3 ou plus ancienne, le lanceur retrouve votre profil, vos seeds et
vos sauvegardes : le dossier de l'ancienne release peut être supprimé. Le guide complet, en anglais :
[Setup guide](setup_en.md). Les guides sont aussi dans le lanceur : **Help**, en bas de sa barre latérale.

## Pour aller plus loin

| Je veux… | Page (en anglais) |
|---|---|
| Voir ce qu'Archipelago change dans le jeu | [In the game](ingame_en.md) |
| Comprendre les lieux, les objets, la logique et les options | [Options](en_Breath%20of%20the%20Wild.md) |
| Héberger une seed | [Hosting](hosting_en.md) |
| Suivre ma partie sur une carte | [Trackers](poptracker_en.md) |
| Jouer avec mes mods et packs graphiques | [Mods](mods_en.md) |
| Résoudre un problème, signaler un bug | [Troubleshooting](troubleshooting_en.md) |

## Noms en français

Archipelago et les textes ajoutés au jeu sont en anglais, et le jeu en français nomme souvent autrement les lieux et
les objets (Tah Muhl Shrine est le sanctuaire de Ta'Mur) : la [table des noms en français](names_fr.md) donne la
correspondance.
