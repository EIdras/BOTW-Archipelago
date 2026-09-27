import unittest

from botw_client.pause_menu import (
    INVENTORY_LOADER, INVENTORY_SCREEN, LOADER_READY, LOADER_STATE, MAP_IDLE_BYTES, MAP_LOADER,
    MAP_SCREEN, UI_MANAGER, pause_menu_ready)


class Memory:
    def __init__(self):
        self.bytes = {}

    def u32(self, address, value):
        for i, b in enumerate(value.to_bytes(4, "big")):
            self.bytes[address + i] = b

    def u8(self, address, value):
        self.bytes[address] = value & 0xFF

    def read(self, address, size):
        return bytes(self.bytes.get(address + i, 0) for i in range(size))


MANAGER, TABLE, MAP, INVENTORY = 0x20000000, 0x20001000, 0x20002000, 0x20100000
MAP_LOAD, INVENTORY_LOAD = 0x20200000, 0x20300000


def loaded_ui(**overrides):
    memory = Memory()
    memory.u32(UI_MANAGER, MANAGER)
    memory.u32(MANAGER + 0x14, 0x63)
    memory.u32(MANAGER + 0x18, TABLE)
    memory.u32(TABLE + 4 * MAP_SCREEN, MAP)
    memory.u32(TABLE + 4 * INVENTORY_SCREEN, INVENTORY)
    memory.u32(MAP + MAP_LOADER, MAP_LOAD)
    memory.u32(INVENTORY + INVENTORY_LOADER, INVENTORY_LOAD)
    for loader in (MAP_LOAD, INVENTORY_LOAD):
        memory.u32(loader + LOADER_STATE + 0xFC + 0x28, LOADER_READY)
    for address, value in overrides.items():
        memory.u32(int(address, 16), value)
    return memory


class PauseMenuReadyTests(unittest.TestCase):
    def test_map_and_inventory_loaded_and_idle(self):
        self.assertEqual(pause_menu_ready(loaded_ui().read), (True, ""))

    def test_map_still_loading(self):
        memory = loaded_ui(**{hex(MAP_LOAD + LOADER_STATE + 0xFC + 0x28): 3})
        self.assertEqual(pause_menu_ready(memory.read), (False, "carte pas encore chargée"))
        memory = loaded_ui(**{hex(MAP_LOAD + LOADER_STATE + 0x100): 1})
        self.assertFalse(pause_menu_ready(memory.read)[0])

    def test_inventory_still_loading(self):
        memory = loaded_ui(**{hex(INVENTORY_LOAD + LOADER_STATE + 0xFC + 0x28): 0})
        self.assertEqual(pause_menu_ready(memory.read), (False, "inventaire pas encore chargé"))

    def test_map_in_use_matters_only_at_rest(self):
        # In play the map is never at rest (state 2 with the HUD): the client
        # checks loading only, the event waits for the rest.
        memory = loaded_ui()
        memory.u8(MAP + MAP_IDLE_BYTES + 1, 2)
        self.assertEqual(pause_menu_ready(memory.read), (True, ""))
        self.assertEqual(pause_menu_ready(memory.read, at_rest=True),
                         (False, "carte en cours d'utilisation"))
        memory = loaded_ui()
        memory.u8(MAP + MAP_IDLE_BYTES, 1)
        self.assertFalse(pause_menu_ready(memory.read, at_rest=True)[0])
        memory.u8(MAP + MAP_IDLE_BYTES, 0xFF)   # negative: idle, as the game reads it
        self.assertTrue(pause_menu_ready(memory.read, at_rest=True)[0])

    def test_screens_without_loader_count_as_ready_and_no_ui_is_not(self):
        memory = loaded_ui(**{hex(MAP + MAP_LOADER): 0, hex(INVENTORY + INVENTORY_LOADER): 0})
        self.assertTrue(pause_menu_ready(memory.read)[0])
        self.assertEqual(pause_menu_ready(Memory().read), (False, "interface du jeu illisible"))


if __name__ == "__main__":
    unittest.main()
