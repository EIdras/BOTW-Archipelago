# Mods and graphic packs

[Setup](setup_en.md) · [In the game](ingame_en.md) · [Options](en_Breath%20of%20the%20Wild.md) · [Hosting](hosting_en.md) ·
[Trackers](poptracker_en.md) · **Mods** · [Troubleshooting](troubleshooting_en.md)

The Archipelago game runs the Breath of the Wild graphic packs your Cemu runs: community packs (FPS++, graphics...)
and mods alike, whatever installed them (UKMM, BCML, a folder unzipped by hand).

## How it works

- **Your Cemu decides.** The packs ticked in Cemu's Options > Graphic packs, with the presets chosen there, are the
  ones the Archipelago game runs. To play without one, untick it in your Cemu before launching. Change presets there
  too: the Archipelago game takes yours at each session.
- **Your Cemu is only read.** Each session copies the packs into the launcher's profile, and lists in the launcher's
  window those the Archipelago game runs.
- **The seed's pack is built over your mods.** When a mod replaces a file the seed's pack changes too (Linkle's title
  screen, a text mod's messages, the files UKMM merges), the pack starts from the mod's version and adds its own
  changes. When your mods change, the next session builds the seed's pack again, in about a minute.

## Extended Memory

Mods that add to the game take memory, and Archipelago adds its own: the game could lack it and never finish
loading, without any error. With mods that replace game files, the Archipelago game enables **Extended Memory**, one
of Cemu's community packs, and says so.

> [!TIP]
> If your Cemu does not have Extended Memory, the launcher says so: in Cemu, Options > Graphic packs > Download
> latest community graphic packs, then launch again.

## What is left out

The launcher names each pack it leaves out, and why. The Archipelago game then runs without it:

- a pack that replaces the game's executable;
- a pack that patches the code the Archipelago pack needs;
- a mod that changes an event the Archipelago pack changes too.

> [!NOTE]
> UKMM gathers its mods into one pack: one of them left out leaves them all out, and the launcher says so. Turn that
> mod off in UKMM, and deploy again, to keep the others.

## Tested

FPS++ (60 frames a second), the community graphics and enhancement packs, and six mods deployed by UKMM, Linkle among
them. Mods that change the HUD, and BCML, have not been tried yet: if one does not work,
[report it](https://github.com/EIdras/BOTW-Archipelago/issues) with the session's folder
([where it is](troubleshooting_en.md#logs)).

---

Next: [Troubleshooting](troubleshooting_en.md).
