"""The melee weapons Link can hold, by actor name, for the Weapon Shatter trap.

Every weapon actor the game names in its texts (ActorType/WeaponSmallSword,
WeaponLargeSword and WeaponSpear.msbt), except the Master Sword, which never
breaks (Weapon_Sword_070, 080 and 081). Bows and shields are not here: the trap
breaks the weapon in Link's hand. The numbers are the actor packs of the Wii U
update (Actor/Pack/Weapon_<family>_<number>.sbactorpack); tests/test_traps.py
compares them with the player's own game files.
"""
from __future__ import annotations

MASTER_SWORD = ("Weapon_Sword_070", "Weapon_Sword_080", "Weapon_Sword_081")

NUMBERS = {
    "Sword": (1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 27,
              29, 30, 31, 33, 34, 35, 40, 41, 43, 44, 47, 48, 49, 50, 51, 52, 53, 57, 58, 59, 60,
              61, 62, 73, 502),
    "Lsword": (1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 23, 24, 27, 29, 30,
               31, 32, 33, 34, 35, 36, 37, 38, 41, 45, 47, 51, 54, 55, 56, 57, 59, 60, 74),
    "Spear": (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25,
              27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 47, 49, 50),
}

MELEE_WEAPONS = tuple(f"Weapon_{family}_{number:03d}"
                      for family, numbers in NUMBERS.items() for number in numbers)
