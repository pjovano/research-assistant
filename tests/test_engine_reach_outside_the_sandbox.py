from __future__ import annotations

import unittest
from types import SimpleNamespace

from _support import LiveTree

LiveTree.activate()

from engine_reach import MACOS, EngineReach, EngineUnreachable, MetalAccess, ServerReach

LINUX = "linux"
SERVER_URL = "http://127.0.0.1:8765"
SPAWN_FAILURE = "llama-server exited before it answered"


class ServerManager:
    def __init__(self, starts: bool = True) -> None:
        self._starts = starts
        self.backend = SimpleNamespace(handle=SimpleNamespace(base_url=f"{SERVER_URL}/v1"))

    def start(self) -> None:
        if not self._starts:
            raise RuntimeError(SPAWN_FAILURE)


class RecordedCheck:
    def __init__(self, failure: str | None, checked: list) -> None:
        self._failure = failure
        self._checked = checked

    def failure(self) -> str | None:
        self._checked.append(self._failure)
        return self._failure


class TestMetalAccess(unittest.TestCase):
    def test_a_mac_process_without_metal_is_refused_naming_the_sandbox(self) -> None:
        self.assertIn("sandbox", MetalAccess(MACOS, lambda: False).failure())

    def test_a_mac_process_with_metal_passes(self) -> None:
        self.assertIsNone(MetalAccess(MACOS, lambda: True).failure())

    def test_a_machine_that_is_no_mac_needs_no_metal(self) -> None:
        self.assertIsNone(MetalAccess(LINUX, lambda: False).failure())


class TestServerReach(unittest.TestCase):
    def test_a_server_that_does_not_start_is_refused_naming_the_failure(self) -> None:
        reach = ServerReach(lambda: ServerManager(starts=False), lambda url: True)
        self.assertIn(SPAWN_FAILURE, reach.failure())

    def test_a_started_server_that_does_not_answer_is_refused_naming_its_address(self) -> None:
        self.assertIn(SERVER_URL, ServerReach(ServerManager, lambda url: False).failure())

    def test_a_started_server_is_asked_for_its_health_at_its_own_address(self) -> None:
        asked = []
        ServerReach(ServerManager, lambda url: asked.append(url) or True).failure()
        self.assertEqual([SERVER_URL], asked)


class TestEngineReach(unittest.TestCase):
    def test_the_first_failed_check_refuses_the_engine(self) -> None:
        with self.assertRaisesRegex(EngineUnreachable, "no Metal"):
            EngineReach((RecordedCheck("no Metal", []), RecordedCheck(None, []))).require()

    def test_no_later_check_runs_once_one_failed(self) -> None:
        checked: list = []
        with self.assertRaises(EngineUnreachable):
            EngineReach((RecordedCheck("no Metal", checked), RecordedCheck(None, checked))).require()
        self.assertEqual(["no Metal"], checked)

    def test_an_engine_passing_every_check_is_ready(self) -> None:
        EngineReach((RecordedCheck(None, []), RecordedCheck(None, []))).require()


if __name__ == "__main__":
    unittest.main()
