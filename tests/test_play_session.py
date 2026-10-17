import json
import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]

from tools import cemu_profile
from tools.cemu_profile import play_account_dat
from tools.play_session import enabled_packs, tree_hashes

SOURCE_ACCOUNT = ("AccountInstance_20120705\nPersistentId=80000001\n"
               "TransferableIdBase=200000402a7c36e\n"
               "Uuid=223026b4f405dcfd54d32a0702a7c36e\nMiiName=0064\n")


class AccountTests(unittest.TestCase):
    def test_the_play_account_differs_only_by_its_identifiers(self):
        out = play_account_dat(SOURCE_ACCOUNT).splitlines()
        self.assertEqual(out[1], "PersistentId=80000003")
        self.assertEqual(out[2], "TransferableIdBase=200000402000003")
        self.assertEqual(out[3], "Uuid=223026b4f405dcfd54d32a0702000003")
        self.assertEqual([out[0], out[4]], [SOURCE_ACCOUNT.splitlines()[0],
                                            SOURCE_ACCOUNT.splitlines()[4]])

    def test_only_the_copied_account_is_used_as_a_model(self):
        with self.assertRaises(ValueError):
            play_account_dat(SOURCE_ACCOUNT.replace("80000001", "80000002"))

    def test_every_launch_names_its_account(self):
        import inspect
        source = inspect.getsource(cemu_profile.prepare_play)
        self.assertIn("persistent.text = str(PLAY_ACCOUNT)", source)
        self.assertEqual((cemu_profile.SOURCE_ACCOUNT, cemu_profile.PLAY_ACCOUNT),
                         (0x80000001, 0x80000003))


class LauncherTests(unittest.TestCase):
    def test_the_launcher_exists(self):
        text = (ROOT / "Play.cmd").read_bytes()
        self.assertIn(rb"tools\play_session.py", text)
        self.assertIn(b"\r\n", text)


class ProfileTests(unittest.TestCase):
    """Other graphic packs may sit in the profile: only the seed's is enabled."""

    def make_profile(self, root: Path) -> Path:
        packs = root / "graphicPacks"
        for name in ("OtherPack", "AP_Ledger_796aa895aad1ffff"):
            (packs / name).mkdir(parents=True)
            (packs / name / "rules.txt").write_text("[Definition]\n", encoding="utf-8")
        (root / "settings.xml").write_text(
            '<?xml version="1.0"?><content><GraphicPack>'
            '<Entry filename="graphicPacks/AP_Ledger_796aa895aad1ffff/rules.txt"/>'
            "</GraphicPack></content>", encoding="utf-8")
        return root

    def test_only_the_seed_pack_is_enabled(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_profile(Path(folder))
            self.assertEqual(enabled_packs(root),
                             ["graphicPacks/AP_Ledger_796aa895aad1ffff/rules.txt"])

    def test_the_copies_of_other_seed_packs_are_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_profile(Path(folder))
            packs = root / "graphicPacks"
            for name in ("AP_Ledger_0000000000000001", "AP_Ledger_0000000000000002"):
                (packs / name).mkdir()
                (packs / name / "rules.txt").write_bytes(b"[Definition]")
            removed = cemu_profile.prune_packs(packs, "AP_Ledger_0000000000000002")
            self.assertEqual(removed, ["AP_Ledger_0000000000000001", "AP_Ledger_796aa895aad1ffff"])
            self.assertEqual(sorted(p.name for p in packs.iterdir()),
                             ["AP_Ledger_0000000000000002", "OtherPack"])
        import inspect
        self.assertIn("prune_packs(destination.parent, destination.name)",
                      inspect.getsource(cemu_profile.prepare_play))

    def test_the_session_refuses_a_profile_with_another_pack(self):
        import inspect
        from tools import play_session
        source = inspect.getsource(play_session.run)
        self.assertIn("the play profile loads something else", source)

class CrashReportTests(unittest.TestCase):
    """A console crash must leave a trace: otherwise session.json stays
    'running'."""

    def test_the_session_captures_native_and_python_crashes(self):
        import inspect
        from tools import play_session
        source = inspect.getsource(play_session.run)
        self.assertIn("faulthandler.enable(sys.stderr)", source)
        self.assertIn("threading.excepthook", source)
        self.assertIn('Stream(sys.stderr, session / "stderr.log")', source)

class HashTests(unittest.TestCase):
    def test_missing_folder_has_no_hashes(self):
        self.assertEqual(tree_hashes(ROOT / "does-not-exist"), {})


class ConsoleRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_input_returning_after_console_shutdown_is_discarded(self):
        from tools.play_session import console
        started, release = threading.Event(), threading.Event()
        errors, threads = [], []
        original_thread = threading.Thread
        def input_later():
            started.set()
            if not release.wait(3): raise TimeoutError('test input not released')
            return '/send Player Rupee Bundle'
        def thread(*, target, **kwargs):
            def captured():
                try: target()
                except BaseException as exc: errors.append(exc)
            worker = original_thread(target=captured, **kwargs)
            threads.append(worker)
            return worker
        runtime, context = Mock(), Mock()
        runtime.stop_event.is_set.return_value = False
        with patch('builtins.input', side_effect=input_later), \
                patch('tools.play_session.threading.Thread', side_effect=thread):
            task = asyncio.create_task(console(runtime, context, Mock(), "Player"))
            try:
                for _ in range(100):
                    if started.is_set(): break
                    await asyncio.sleep(.01)
                self.assertTrue(started.is_set())
                task.cancel()
                with self.assertRaises(asyncio.CancelledError): await task
            finally:
                release.set()
                for worker in threads: worker.join(1)
        self.assertTrue(all(not worker.is_alive() for worker in threads))
        self.assertEqual(errors, [])
        context.commandprocessor.assert_not_called()
        runtime.handle_local_command.assert_not_called()

    async def dispatch(self, line, local=False, remote=False, online=True):
        from tools.play_session import console
        runtime = Mock()
        runtime.stop_event.is_set.side_effect = [False, True]
        runtime.handle_local_command.return_value = local
        runtime.ap.say = AsyncMock()
        runtime.ap.connected = online
        context = None if remote else Mock()
        def thread(*, target, **kwargs):
            return Mock(start=target)
        with patch('builtins.input', side_effect=[line, EOFError]), \
                patch('tools.play_session.threading.Thread', side_effect=thread):
            await console(runtime, context, Mock(), "Player")
        return runtime, context

    async def test_recovery_command_stays_local(self):
        runtime, context = await self.dispatch('/ap-replay received/7', local=True)
        runtime.handle_local_command.assert_called_once_with('/ap-replay received/7')
        context.commandprocessor.assert_not_called()
        runtime.ap.say.assert_not_awaited()

    async def test_server_command_keeps_archipelago_slash_marker(self):
        runtime, context = await self.dispatch('/send Player Rupee Bundle')
        context.commandprocessor.assert_called_once_with('/send Player Rupee Bundle')
        runtime.ap.say.assert_not_awaited()

    async def test_ordinary_message_goes_to_chat(self):
        runtime, context = await self.dispatch('hello')
        runtime.ap.say.assert_awaited_once_with('hello')
        context.commandprocessor.assert_not_called()

    async def test_a_remote_room_gets_commands_as_players_type_them(self):
        runtime, _ = await self.dispatch('/hint Paraglider', remote=True)
        runtime.ap.say.assert_awaited_once_with('!hint Paraglider')
        runtime, _ = await self.dispatch('/hint Paraglider', remote=True, online=False)
        runtime.ap.say.assert_not_awaited()
        runtime, _ = await self.dispatch('/ap-deathlink', local=True, remote=True)
        runtime.ap.say.assert_not_awaited()


class ShutdownTests(unittest.IsolatedAsyncioTestCase):
    """Exercise play() without starting Cemu, a socket, or an AP save thread."""

    def setUp(self):
        from botw_client.protocol import ArchipelagoClient, NetworkItem
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.ap = ArchipelagoClient("localhost:38281", "Player")
        self.ap.item_name_by_id = {100: "Paraglider", 101: "Remote Bomb"}
        # AP indices, not item ids; insertion order need not be index order.
        self.ap.received_items = {1: NetworkItem(101, 202, 1, 1),
                                  0: NetworkItem(100, 201, 1, 1)}
        self.ap.checked_locations = {202, 201}
        self.runtime = SimpleNamespace(ap=self.ap, _native_session_bound=True,
                                       run=AsyncMock(), stop=Mock())
        self.events = []
        self.context = Mock(save_filename=str(self.folder / "server.apsave"))

        def save():
            self.events.append("save")
            # Independent of display-name formatting in the session report.
            Path(self.context.save_filename).write_text(json.dumps({
                "received_indices": sorted(self.ap.received_items),
                "checked_locations": sorted(self.ap.checked_locations),
            }), encoding="utf-8")
            return True

        self.context._save.side_effect = save
        self.server = AsyncMock()
        self.server.__aexit__.return_value = False

    async def run_play(self):
        from tools.play_session import play
        modules = {
            "MultiServer": SimpleNamespace(Context=Mock(return_value=self.context),
                                           server=Mock()),
            "worlds": SimpleNamespace(network_data_package={"games": {}}),
            # Archipelago's, not one of the player's packages (absent from a release and the CI).
            "websockets": SimpleNamespace(serve=Mock(return_value=self.server)),
            "botw_client.runtime": SimpleNamespace(
                BotwClientRuntime=Mock(return_value=self.runtime)),
        }
        with patch.dict("sys.modules", modules), \
                patch("tools.play_session.console", new_callable=AsyncMock):
            return await play(self.folder, {"archive": "unused.zip",
                                            "audit": {"slots": {"1": "Player"}}},
                              self.folder, self.folder, Mock(poll=Mock(return_value=0)), Mock(),
                              journal=False)

    async def test_a_remote_room_needs_no_local_server(self):
        from tools.play_session import play
        factory = Mock(return_value=self.runtime)
        context = Mock(side_effect=AssertionError("no local server"))
        modules = {"MultiServer": SimpleNamespace(Context=context, server=Mock()),
                   "websockets": SimpleNamespace(serve=Mock(side_effect=AssertionError("no socket"))),
                   "botw_client.runtime": SimpleNamespace(BotwClientRuntime=factory)}
        with patch.dict("sys.modules", modules), \
                patch("tools.play_session.console", new_callable=AsyncMock) as console:
            summary = await play(self.folder, {"archive": "slot.apbotw.json", "botw_slot": 3,
                                               "audit": {"slots": {"3": "Zelda"}}},
                                 self.folder, self.folder, Mock(poll=Mock(return_value=0)), Mock(),
                                 journal=False, connect="archipelago.gg:38281", password="secret")
        self.assertEqual(factory.call_args.args, ("archipelago.gg:38281", "Zelda", "secret"))
        self.assertIsNone(console.call_args.args[1])       # commands go to the room as chat
        self.assertEqual(summary["server"], "archipelago.gg:38281")
        self.assertEqual(summary["received_items"], ["Paraglider", "Remote Bomb"])
        self.context._save.assert_not_called()

    def assert_saved(self):
        self.context._save.assert_called_once_with()
        data = json.loads(Path(self.context.save_filename).read_text(encoding="utf-8"))
        self.assertEqual(data["received_indices"], sorted(self.ap.received_items))
        self.assertEqual(data["checked_locations"], [201, 202])

    async def test_received_items_are_reported_in_ap_index_order(self):
        async def close(*args):
            self.events.append("server_closed")
            return False
        self.server.__aexit__.side_effect = close
        summary = await self.run_play()
        self.assertEqual(summary["received_items"], ["Paraglider", "Remote Bomb"])
        self.assertEqual(summary["checked_locations"], [201, 202])
        self.assertTrue(summary["native_session_bound"])
        self.assertEqual(self.events, ["server_closed", "save"])
        self.assert_saved()

    async def test_session_without_received_items_saves(self):
        self.ap.received_items.clear()
        self.assertEqual((await self.run_play())["received_items"], [])
        self.assert_saved()

    async def test_report_failure_does_not_prevent_save(self):
        self.ap.item_name = Mock(side_effect=ValueError("broken report"))
        with self.assertRaisesRegex(ValueError, "broken report"):
            await self.run_play()
        self.assert_saved()

    async def test_runtime_failure_does_not_prevent_save(self):
        self.runtime.run.side_effect = RuntimeError("client failed")
        with self.assertRaisesRegex(RuntimeError, "client failed"):
            await self.run_play()
        self.assert_saved()

    async def test_cancellation_does_not_prevent_save(self):
        self.runtime.run.side_effect = asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await self.run_play()
        self.assert_saved()

    async def test_server_start_failure_does_not_prevent_save(self):
        self.server.__aenter__.side_effect = OSError("port busy")
        with self.assertRaisesRegex(OSError, "port busy"):
            await self.run_play()
        self.assert_saved()

    async def test_server_close_failure_does_not_prevent_save(self):
        self.server.__aexit__.side_effect = RuntimeError("close failed")
        with self.assertRaisesRegex(RuntimeError, "close failed"):
            await self.run_play()
        self.assert_saved()

    async def test_false_save_result_is_not_reported_as_success(self):
        self.context._save.side_effect = None
        self.context._save.return_value = False
        with self.assertRaisesRegex(OSError, "final save"):
            await self.run_play()
        self.context._save.assert_called_once_with()

if __name__ == "__main__":
    unittest.main()
