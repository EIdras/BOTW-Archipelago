# Hosting a Breath of the Wild seed

[Setup](setup_en.md) · [In the game](ingame_en.md) · [Options](en_Breath%20of%20the%20Wild.md) · **Hosting** ·
[Trackers](poptracker_en.md) · [Mods](mods_en.md) · [Troubleshooting](troubleshooting_en.md)

The person who hosts the game generates the seed with [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases)
**0.6.7**, as for any game, then hosts it. Playing alone is the same: generate a seed with your YAML alone, host it,
and join it.

> [!NOTE]
> archipelago.gg's website cannot generate a Breath of the Wild seed: generate it on your computer, then host it
> anywhere, archipelago.gg included.

## 1. Install the world

Put `botw.apworld`, from the [releases](https://github.com/EIdras/BOTW-Archipelago/releases), in Archipelago's
`custom_worlds` folder. Take it from the same release as the players' launcher.

## 2. Gather the YAML files

Put every player's YAML file in Archipelago's `Players` folder. For Breath of the Wild, start from
`players\BOTW.yaml` in the release, or from the template the Archipelago Launcher writes ("Generate Template
Options"). Each option is explained on the [game page](en_Breath%20of%20the%20Wild.md#options).

## 3. Generate

Run "Generate" in the Archipelago Launcher. The seed's zip, in Archipelago's `output` folder, holds a slot file
`AP_<seed>_P<n>_<name>.apbotw` for each Breath of the Wild player.

## 4. Host

| Where | How |
|---|---|
| [archipelago.gg](https://archipelago.gg) | Upload the seed's zip on its "Host Game" page. The room's page gives its address, `archipelago.gg:<port>`, and each player's slot file to download. |
| Your own computer | Open the zip with "Archipelago Server" in the Archipelago Launcher. You connect to `localhost:38281`, the other players to your computer's address, port 38281 (over the Internet, that port must be forwarded to your computer). |

Each Breath of the Wild player then follows the [setup guide](setup_en.md) with their slot file.

---

Next: [Trackers](poptracker_en.md).
