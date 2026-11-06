# Breath of the Wild dans Archipelago : démarrage rapide

Ce guide court permet de jouer à Breath of the Wild dans une partie Archipelago, sous Windows, dans l'émulateur Cemu.
Le reste de la documentation est en anglais : chaque section renvoie à sa page.

## Ce qu'il faut

- Windows 10 ou 11 et [Cemu](https://cemu.info/) 2.x.
- Breath of the Wild **Wii U**, version européenne, américaine ou japonaise, depuis votre propre console, avec sa
  **mise à jour v208** et le **DLC** installés dans Cemu (Fichier > Installer un titre, une mise à jour ou un DLC).
  Lancez le jeu une fois dans Cemu. La version Switch n'est pas prise en charge.
- Environ 5 Go d'espace disque libre, et 140 Mo de plus par seed.
- Votre **fichier de slot** (`.apbotw`) : sur la page de la salle, « Download Patch File... » à côté de votre nom.

## Installer

1. Télécharger `BOTW-Archipelago-<version>-Windows.zip` dans les
   [releases](https://github.com/EIdras/BOTW-Archipelago/releases), parmi les **Assets** (pas « Source code »).
2. Clic droit sur le zip > Propriétés, cocher **Débloquer**, OK.
3. Le décompresser où vous voulez, dans vos Documents par exemple (pas dans Program Files). Rien d'autre à
   installer : la release apporte son propre Python.

## Jouer

Lancer `BOTW Archipelago.cmd`, ou déposer dessus votre fichier de slot. Si Windows dit avoir protégé votre
ordinateur, choisir « Informations complémentaires », puis « Exécuter quand même ».

1. **Cemu** : la première fois, une fenêtre demande où est `Cemu.exe`. Le lanceur copie Cemu et vos sauvegardes dans
   un profil à lui (environ 5 Go). Votre installation de Cemu n'est jamais modifiée.
2. **La seed** : choisir votre fichier de slot. Son pack de jeu se construit en une minute environ.
3. **La salle** : son adresse (`archipelago.gg:38281`) est déjà remplie quand le fichier de slot vient de sa page :
   Entrée, puis le mot de passe de la salle, ou Entrée s'il n'y en a pas.

Cemu démarre, et le client Archipelago tourne dans la fenêtre du lanceur. **Commencez une nouvelle partie** pour une
nouvelle seed : une sauvegarde reste liée à sa seed. Fermer Cemu termine la session ; laissez la fenêtre du lanceur
ouverte jusque-là.

Le guide complet, en anglais : [Setup guide](setup_en.md).

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
