from __future__ import annotations

import http.server
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from engine_environment import EngineEnvironment
from engine_slots import (
    ENGINE_DEFAULT_SLOTS,
    ENGINE_SLOTS_KEY,
    PARALLEL_VARIABLE,
    VLM_SENTINEL_NAME,
    EngineSlots,
    EngineSlotsInvalid,
    RunningSlots,
    SlotsAgreement,
)
from surya.inference.backends.llamacpp import LlamaCppBackend

OVERNIGHT_SLOTS = 16


class FixedRunning(RunningSlots):
    def __init__(self, count: int | None) -> None:
        self._fixed = count

    def count(self) -> int | None:
        return self._fixed


class StopCounter:
    def __init__(self) -> None:
        self.stops = 0

    def __call__(self) -> None:
        self.stops += 1


def stops_for(machine: dict, running: int | None) -> int:
    counter = StopCounter()
    SlotsAgreement(EngineSlots(machine), FixedRunning(running), counter).settle()
    return counter.stops


class TestEngineSlotsFromTheMachine(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(PARALLEL_VARIABLE, None)

    def test_the_default_matches_the_engines_own(self) -> None:
        self.assertEqual(LlamaCppBackend.DEFAULT_PARALLEL, ENGINE_DEFAULT_SLOTS)

    def test_a_configured_count_reaches_the_engines_environment(self) -> None:
        EngineEnvironment({ENGINE_SLOTS_KEY: OVERNIGHT_SLOTS}).apply()
        self.assertEqual(str(OVERNIGHT_SLOTS), os.environ.get(PARALLEL_VARIABLE))

    def test_without_the_key_the_engine_keeps_its_own_count(self) -> None:
        EngineEnvironment({}).apply()
        self.assertNotIn(PARALLEL_VARIABLE, os.environ)

    def test_a_count_that_is_not_a_positive_whole_number_is_refused(self) -> None:
        for value in (0, -4, "16", 12.5, True):
            with self.subTest(value=value), self.assertRaises(EngineSlotsInvalid):
                EngineSlots({ENGINE_SLOTS_KEY: value}).configured()


class TestServersRestartedOnAnotherCount(unittest.TestCase):
    def test_servers_holding_another_count_are_stopped(self) -> None:
        self.assertEqual(1, stops_for({ENGINE_SLOTS_KEY: OVERNIGHT_SLOTS}, ENGINE_DEFAULT_SLOTS))

    def test_servers_holding_the_wanted_count_are_kept(self) -> None:
        self.assertEqual(0, stops_for({ENGINE_SLOTS_KEY: OVERNIGHT_SLOTS}, OVERNIGHT_SLOTS))

    def test_servers_started_with_a_count_since_removed_go_back_to_the_default(self) -> None:
        self.assertEqual(1, stops_for({}, OVERNIGHT_SLOTS))

    def test_no_running_server_stops_nothing(self) -> None:
        self.assertEqual(0, stops_for({ENGINE_SLOTS_KEY: OVERNIGHT_SLOTS}, None))


class PropsHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps({"total_slots": OVERNIGHT_SLOTS}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_arguments) -> None:
        return


class TestRunningSlotsReadFromTheServer(unittest.TestCase):
    def setUp(self) -> None:
        self.server = http.server.HTTPServer(("127.0.0.1", 0), PropsHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.sentinels = Path(directory.name)

    def test_the_count_is_read_from_the_server_its_sentinel_names(self) -> None:
        (self.sentinels / VLM_SENTINEL_NAME).write_text(json.dumps({"port": self.server.server_port}))
        self.assertEqual(OVERNIGHT_SLOTS, RunningSlots(self.sentinels).count())

    def test_no_sentinel_means_no_running_server(self) -> None:
        self.assertIsNone(RunningSlots(self.sentinels).count())


if __name__ == "__main__":
    unittest.main()
