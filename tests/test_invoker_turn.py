"""The client's turn of the cave's invoker (botw_client/invoker_turn.py)."""
from contextlib import contextmanager
import threading
import time
import unittest

from botw_client import invoker_turn


@contextmanager
def free_mutex(_pid):
    yield


class TurnTests(unittest.TestCase):
    def test_another_thread_waits_for_the_turn_instead_of_failing(self):
        order = []
        holding = threading.Event()

        def swarm():
            with invoker_turn.publisher_turn(1, os_lock=free_mutex):
                holding.set()
                time.sleep(0.2)
                order.append("swarm")

        thread = threading.Thread(target=swarm)
        thread.start()
        holding.wait(2.0)
        with invoker_turn.publisher_turn(1, os_lock=free_mutex):
            order.append("loop")
        thread.join()
        self.assertEqual(order, ["swarm", "loop"])

    def test_the_turn_is_reentrant(self):
        with invoker_turn.publisher_turn(1, os_lock=free_mutex):
            with invoker_turn.publisher_turn(1, os_lock=free_mutex):
                pass

    def test_a_turn_held_too_long_is_an_error(self):
        holding, release = threading.Event(), threading.Event()

        def holder():
            with invoker_turn.client_turn():
                holding.set()
                release.wait(2.0)

        thread = threading.Thread(target=holder)
        thread.start()
        holding.wait(2.0)
        try:
            with self.assertRaises(RuntimeError):
                with invoker_turn.publisher_turn(1, os_lock=free_mutex, wait=0.05):
                    pass
        finally:
            release.set()
            thread.join()

    def test_the_mutex_refused_releases_the_turn(self):
        @contextmanager
        def busy(_pid):
            raise RuntimeError("Another presentation publisher is active")
            yield

        with self.assertRaises(RuntimeError):
            with invoker_turn.publisher_turn(1, os_lock=busy):
                pass
        result = []
        thread = threading.Thread(target=lambda: result.append(
            invoker_turn._TURN.acquire(timeout=0.5) and invoker_turn._TURN.release() is None))
        thread.start()
        thread.join()
        self.assertEqual(result, [True])


if __name__ == "__main__":
    unittest.main()
