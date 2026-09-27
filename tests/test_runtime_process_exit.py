import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from botw_client.runtime import BotwClientRuntime, FatalClientError


class RuntimeExitTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, error, alive):
        with tempfile.TemporaryDirectory() as directory:
            logs=[]
            game=SimpleNamespace(cave=True, close=Mock())
            runtime=BotwClientRuntime('unused', 'unused', log=logs.append,
                state_path=Path(directory)/'state.json', game_factory=lambda: game,
                game_process_alive=lambda: alive)
            runtime.ap=SimpleNamespace(connected=True, close=AsyncMock())
            runtime._active_loop=AsyncMock(side_effect=error)
            await runtime.run()
            self.assertTrue(runtime.stop_event.is_set())
            self.assertEqual(runtime._active_loop.await_count,1)
            runtime.ap.close.assert_awaited_once()
            game.close.assert_called_once()
            self.assertFalse(any('interrompue' in line for line in logs))

    async def test_confirmed_exit_during_memory_read_is_clean_shutdown(self):
        await self.exercise(TypeError("cannot convert 'NoneType' object to bytes"),False)

    async def test_confirmed_exit_wrapped_by_presentation_is_clean_shutdown(self):
        error=FatalClientError('file de presentation arretee')
        error.__cause__=RuntimeError('Cemu process exited')
        await self.exercise(error,False)

    async def test_fatal_error_is_preserved_while_process_is_alive(self):
        error=FatalClientError('file de presentation arretee')
        error.__cause__=RuntimeError('Cemu process exited')
        with self.assertRaises(FatalClientError):
            await self.exercise(error,True)

    async def test_disk_failure_is_not_hidden_by_simultaneous_exit(self):
        error=FatalClientError('projection presentation non enregistree')
        error.__cause__=OSError('disk full')
        with self.assertRaises(FatalClientError):
            await self.exercise(error,False)
