from __future__ import annotations

import sys
import threading
import time
import types
import unittest
from dataclasses import dataclass
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from engine_guard import EngineUnresponsive, GuardedEngineModels, GuardedInferenceManager, SilenceWatch

SILENCE_LIMIT_SECONDS = 0.2
POLL_SECONDS = 0.02
LONG_BATCH_SECONDS = 3 * SILENCE_LIMIT_SECONDS
BATCH = ["first line sheet", "second line sheet"]
ENGINE_FAILURE = "the engine refused the batch"
INFERENCE_MANAGER = "inference_manager"


@dataclass(frozen=True)
class Answer:
    raw: str
    error: bool = False


ANSWER = Answer("read by a fresh server")


class NeverWrittenLogs:
    def last_active(self) -> float | None:
        return None


class ContinuallyWrittenLogs:
    def last_active(self) -> float | None:
        return time.time()


class RecordingServers:
    def __init__(self) -> None:
        self.stopped = 0

    def stop_all(self) -> None:
        self.stopped += 1


class ServerThatNeverAnswers:
    def __init__(self, release: threading.Event) -> None:
        self._release = release

    def answer(self, batch: list) -> list:
        self._release.wait()
        return []


class ServerThatAnswers:
    def answer(self, batch: list) -> list:
        return [ANSWER for _ in batch]


class ServerThatAnswersSlowly:
    def answer(self, batch: list) -> list:
        time.sleep(LONG_BATCH_SECONDS)
        return [ANSWER for _ in batch]


class InferenceManagerOverServers:
    def __init__(self, servers: list) -> None:
        self._unstarted = list(servers)
        self._server = None
        self.starts = 0

    def generate(self, batch: list) -> list:
        if self._server is None:
            self.start()
        return self._server.answer(batch)

    def start(self) -> None:
        self._server = self._unstarted.pop(0)
        self.starts += 1

    def stop(self) -> None:
        self._server = None


class FailingInferenceManager:
    def generate(self, batch: list) -> list:
        raise ValueError(ENGINE_FAILURE)


class EngineGuardTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.release = threading.Event()
        self.addCleanup(self.release.set)
        self.servers = RecordingServers()

    def guarded(self, manager, logs=None) -> GuardedInferenceManager:
        watch = SilenceWatch(logs or NeverWrittenLogs(), SILENCE_LIMIT_SECONDS, POLL_SECONDS)
        return GuardedInferenceManager(manager, watch, self.servers)

    def unanswered_then_answered(self) -> InferenceManagerOverServers:
        return InferenceManagerOverServers([ServerThatNeverAnswers(self.release), ServerThatAnswers()])

    def raises_unresponsive(self, guarded: GuardedInferenceManager) -> None:
        with self.assertRaises(EngineUnresponsive):
            guarded.generate(BATCH)


class TestAnEngineRequestTheServerNeverAnswers(EngineGuardTestCase):
    def test_the_request_fails_with_a_named_error_once_the_servers_fall_silent(self) -> None:
        self.raises_unresponsive(self.guarded(self.unanswered_then_answered()))

    def test_the_request_fails_within_a_bounded_time(self) -> None:
        started = time.monotonic()
        self.raises_unresponsive(self.guarded(self.unanswered_then_answered()))
        self.assertLess(time.monotonic() - started, LONG_BATCH_SECONDS)

    def test_the_unresponsive_servers_are_stopped(self) -> None:
        self.raises_unresponsive(self.guarded(self.unanswered_then_answered()))
        self.assertEqual(1, self.servers.stopped)

    def test_the_next_request_is_answered_by_a_fresh_server(self) -> None:
        manager = self.unanswered_then_answered()
        guarded = self.guarded(manager)
        self.raises_unresponsive(guarded)
        self.assertEqual([ANSWER, ANSWER], guarded.generate(BATCH))
        self.assertEqual(2, manager.starts)


class TestALongEngineBatchWhoseServersKeepWriting(EngineGuardTestCase):
    def test_the_batch_is_not_cut_off_at_the_silence_limit(self) -> None:
        manager = InferenceManagerOverServers([ServerThatAnswersSlowly()])
        guarded = self.guarded(manager, ContinuallyWrittenLogs())
        self.assertEqual([ANSWER, ANSWER], guarded.generate(BATCH))
        self.assertEqual(0, self.servers.stopped)


class TestAnEngineFailure(EngineGuardTestCase):
    def test_a_failure_the_engine_raises_reaches_the_caller_unchanged(self) -> None:
        with self.assertRaisesRegex(ValueError, ENGINE_FAILURE):
            self.guarded(FailingInferenceManager()).generate(BATCH)


class TestTheEngineModelsShareTheGuardedManager(unittest.TestCase):
    def test_every_predictor_the_engine_builds_sends_its_requests_through_the_guard(self) -> None:
        with mock.patch.dict(sys.modules, self._fake_engine_modules()):
            models = GuardedEngineModels().created()
        self.assertIsInstance(models[INFERENCE_MANAGER], GuardedInferenceManager)

    @staticmethod
    def _fake_engine_modules() -> dict[str, types.ModuleType]:
        marker_models = types.ModuleType("marker.models")
        marker_models.create_model_dict = lambda inference_manager: {INFERENCE_MANAGER: inference_manager}
        surya_inference = types.ModuleType("surya.inference")
        surya_inference.SuryaInferenceManager = FailingInferenceManager
        return {"marker": types.ModuleType("marker"), "marker.models": marker_models,
                "surya": types.ModuleType("surya"), "surya.inference": surya_inference}


if __name__ == "__main__":
    unittest.main()
