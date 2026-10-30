import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from botw_client.runtime import BotwClientRuntime


class TowerRepairTests(unittest.IsolatedAsyncioTestCase):
    def runtime(self, directory, states):
        self.logs = []
        game = SimpleNamespace(tower_states=lambda: dict(states), mark_tower_activated=Mock())
        runtime = BotwClientRuntime('unused', 'unused', log=self.logs.append,
                                    state_path=Path(directory) / 'state.json', game_factory=lambda: game)
        return runtime, game

    async def tick(self, runtime):
        runtime._tower_retry_after = min(runtime._tower_retry_after, 0.0)
        await runtime._tower_repair_tick()

    async def test_a_tower_activated_before_the_fix_is_given_its_flag_again(self):
        with tempfile.TemporaryDirectory() as directory:
            states = {'MapTower_03': (True, False), 'MapTower_08': (False, False),
                      'MapTower_12': (True, True)}
            runtime, game = self.runtime(directory, states)
            await self.tick(runtime)
            game.mark_tower_activated.assert_called_once_with('MapTower_03')
            # Activated now: its terminal's flag comes before its event's APTower_NN.
            states['MapTower_08'] = (True, False)
            await self.tick(runtime)
            # A reload lost the live write: given again, logged once.
            await self.tick(runtime)
            self.assertEqual([call.args[0] for call in game.mark_tower_activated.call_args_list],
                             ['MapTower_03'] * 3)
            self.assertEqual(sum('APTower_03' in line for line in self.logs), 1)

    async def test_a_pack_without_tower_flags_is_read_once(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime, game = self.runtime(directory, {})
            await self.tick(runtime)
            self.assertEqual(runtime._tower_retry_after, float('inf'))
            game.mark_tower_activated.assert_not_called()


if __name__ == '__main__':
    unittest.main()
