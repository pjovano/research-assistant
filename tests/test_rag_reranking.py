from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import rag
from _rag.reranking import PROBE_QUERY, LlamaServerProcess, PerQueryLifetime, ProbeLedger, ProcessLifetime

RESPONSE = {"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}]}
SANE_PROBE = {"results": [{"index": 0, "relevance_score": 0.98}, {"index": 1, "relevance_score": 0.01}]}
REVERSED_PROBE = {"results": [{"index": 0, "relevance_score": 0.01}, {"index": 1, "relevance_score": 0.98}]}
DEGENERATE_PROBE = {"results": [{"index": 0, "relevance_score": 1.1e-28}, {"index": 1, "relevance_score": 1.0e-28}]}
FLAT_PROBE = {"results": [{"index": 0, "relevance_score": 0.5}, {"index": 1, "relevance_score": 0.5}]}


@dataclass(frozen=True)
class Health:
    now: bool = True
    after_launch: bool = True


class FakeTransport:
    def __init__(self, response: dict = RESPONSE, probe: dict | None = SANE_PROBE, health: Health = Health()) -> None:
        self._response = response
        self._probe = probe
        self._health = health
        self.launched = False
        self.requests: list[tuple[str, dict]] = []

    def healthy(self, _url: str) -> bool:
        return self._health.now or (self.launched and self._health.after_launch)

    def rerank(self, url: str, payload: dict) -> dict:
        self.requests.append((url, payload))
        if payload["query"] != PROBE_QUERY:
            return self._response
        if self._probe is None:
            raise rag.RerankerUnavailable("connection refused")
        return self._probe

    def queries(self) -> list[str]:
        return [payload["query"] for _, payload in self.requests]


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.returncode: int | None = None
        self.stderr = None

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float) -> None:
        pass


class FakeControl:
    def __init__(self, transport: FakeTransport) -> None:
        self._transport = transport
        self._clock = 0.0
        self.commands: list[list[str]] = []
        self.process = FakeProcess()

    def launch(self, command: list[str]) -> FakeProcess:
        self.commands.append(command)
        self._transport.launched = True
        return self.process

    def sleep(self, seconds: float) -> None:
        self._clock += seconds

    def now(self) -> float:
        return self._clock


def settings(model: Path | str, pooling: str | None = None) -> rag.MachineSettings:
    values = {"reranker_model": str(model), "llama_server": "/opt/bin/llama-server"}
    if pooling is not None:
        values["reranker_pooling"] = pooling
    return rag.MachineSettings(values)


class RerankerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.gguf = Path(directory.name) / "bge-reranker-v2-m3-Q8_0.gguf"
        self.gguf.write_bytes(b"GGUF")
        self.ledger = ProbeLedger()

    def reranker(self, transport: FakeTransport, model: Path | None = None) -> rag.LlamaReranker:
        server = LlamaServerProcess(settings(model or self.gguf), transport, FakeControl(transport))
        return rag.LlamaReranker(server, self.ledger)

    def without_model(self) -> rag.LlamaReranker:
        transport = FakeTransport()
        return rag.LlamaReranker(LlamaServerProcess(rag.MachineSettings({}), transport, FakeControl(transport)))


class TestLlamaReranker(RerankerTestCase):
    def test_scores_are_returned_in_passage_order(self) -> None:
        scores = self.reranker(FakeTransport()).scores("q", ["first", "second"])
        self.assertEqual([0.2, 0.9], scores)

    def test_the_request_carries_the_query_and_the_documents(self) -> None:
        transport = FakeTransport()
        self.reranker(transport).scores("being", ["first", "second"])
        (_, payload) = transport.requests[-1]
        self.assertEqual(("being", ["first", "second"]), (payload["query"], payload["documents"]))

    def test_a_missing_key_reports_the_reranker_unavailable(self) -> None:
        self.assertIn("reranker_model", self.without_model().unavailable_cause())

    def test_a_missing_file_reports_the_reranker_unavailable(self) -> None:
        cause = self.reranker(FakeTransport(), model=self.gguf.with_name("absent.gguf")).unavailable_cause()
        self.assertIn("not a file", cause)

    def test_a_present_file_reports_no_cause(self) -> None:
        self.assertIsNone(self.reranker(FakeTransport()).unavailable_cause())

    def test_scoring_without_a_model_raises(self) -> None:
        with self.assertRaises(rag.RerankerUnavailable):
            self.without_model().scores("q", ["p"])

    def test_a_malformed_response_raises(self) -> None:
        with self.assertRaises(rag.RerankerUnavailable):
            self.reranker(FakeTransport(response={"results": [{"index": 5}]})).scores("q", ["p"])


class TestStartupProbe(RerankerTestCase):
    def test_the_probe_is_sent_before_the_first_real_query(self) -> None:
        transport = FakeTransport()
        self.reranker(transport).scores("being", ["first", "second"])
        self.assertEqual([PROBE_QUERY, "being"], transport.queries())

    def test_the_probe_is_sent_once_per_session_and_model(self) -> None:
        transport = FakeTransport()
        self.reranker(transport).scores("being", ["first", "second"])
        self.reranker(transport).scores("essence", ["first", "second"])
        self.assertEqual([PROBE_QUERY, "being", "essence"], transport.queries())

    def test_a_sane_probe_lets_the_real_scores_through(self) -> None:
        self.assertEqual([0.2, 0.9], self.reranker(FakeTransport(probe=SANE_PROBE)).scores("q", ["a", "b"]))

    def test_a_probe_in_the_wrong_order_raises_naming_the_order(self) -> None:
        with self.assertRaisesRegex(rag.RerankerUnavailable, "wrong order"):
            self.reranker(FakeTransport(probe=REVERSED_PROBE)).scores("q", ["a", "b"])

    def test_a_probe_with_degenerate_scores_raises_naming_the_scores(self) -> None:
        with self.assertRaisesRegex(rag.RerankerUnavailable, "degenerate scores .*1.1e-28"):
            self.reranker(FakeTransport(probe=DEGENERATE_PROBE)).scores("q", ["a", "b"])

    def test_a_probe_with_identical_scores_is_degenerate(self) -> None:
        with self.assertRaisesRegex(rag.RerankerUnavailable, "degenerate"):
            self.reranker(FakeTransport(probe=FLAT_PROBE)).scores("q", ["a", "b"])

    def test_a_failed_probe_is_not_retried_within_the_session(self) -> None:
        transport = FakeTransport(probe=REVERSED_PROBE)
        for _ in range(2):
            with self.assertRaises(rag.RerankerUnavailable):
                self.reranker(transport).scores("q", ["a"])
        self.assertEqual([PROBE_QUERY], transport.queries())

    def test_a_probe_the_transport_cannot_send_is_recorded_and_not_retried(self) -> None:
        transport = FakeTransport(probe=None)
        for _ in range(2):
            with self.assertRaisesRegex(rag.RerankerUnavailable, "probe failed: connection refused"):
                self.reranker(transport).scores("q", ["a", "b"])
        self.assertEqual([PROBE_QUERY], transport.queries())

    def test_a_failed_probe_becomes_the_unavailable_cause(self) -> None:
        transport = FakeTransport(probe=REVERSED_PROBE)
        with self.assertRaises(rag.RerankerUnavailable):
            self.reranker(transport).scores("q", ["a", "b"])
        self.assertIn("wrong order", self.reranker(transport).unavailable_cause())

    def test_a_failed_probe_sends_no_real_query(self) -> None:
        transport = FakeTransport(probe=DEGENERATE_PROBE)
        with self.assertRaises(rag.RerankerUnavailable):
            self.reranker(transport).scores("q", ["a"])
        self.assertNotIn("q", transport.queries())


class TestLlamaServerProcess(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = FakeTransport(health=Health(now=False))
        self.control = FakeControl(self.transport)
        self.server = LlamaServerProcess(settings("model.gguf"), self.transport, self.control)

    def test_the_server_built_for_this_machine_names_the_machines_reranker_model(self) -> None:
        self.assertEqual(rag.MachineSettings().reranker_model, LlamaServerProcess.on_this_machine().model)

    def test_a_rerank_request_goes_to_the_servers_own_url(self) -> None:
        self.server.rerank({"query": "being", "documents": []})
        [(url, _)] = self.transport.requests
        self.assertEqual(self.server.url, url)

    def test_the_server_is_started_with_reranking_and_rank_pooling_when_nothing_answers(self) -> None:
        self.server.start()
        [command] = self.control.commands
        self.assertEqual(["/opt/bin/llama-server", "--reranking", "-m", "model.gguf", "--pooling", "rank"], command[:6])

    def test_the_pooling_comes_from_machine_json_when_set(self) -> None:
        server = LlamaServerProcess(settings("model.gguf", pooling="none"), self.transport, self.control)
        self.assertIn("none", server.command()[server.command().index("--pooling") + 1])

    def test_a_started_server_is_launched_once_however_often_start_is_called(self) -> None:
        self.server.start()
        self.server.start()
        self.assertEqual(1, len(self.control.commands))

    def test_stop_terminates_the_server_it_started(self) -> None:
        self.server.start()
        self.assertFalse(self.control.process.terminated)
        self.server.stop()
        self.assertTrue(self.control.process.terminated)

    def test_a_healthy_server_is_neither_started_nor_stopped(self) -> None:
        transport = FakeTransport(health=Health(now=True))
        control = FakeControl(transport)
        server = LlamaServerProcess(settings("model.gguf"), transport, control)
        server.start()
        server.stop()
        self.assertEqual(([], False), (control.commands, control.process.terminated))

    def never_answering(self) -> tuple[LlamaServerProcess, FakeControl]:
        transport = FakeTransport(health=Health(now=False, after_launch=False))
        control = FakeControl(transport)
        return LlamaServerProcess(settings("model.gguf"), transport, control), control

    def test_a_server_that_never_answers_raises_after_the_timeout(self) -> None:
        server, _control = self.never_answering()
        with self.assertRaises(rag.RerankerUnavailable):
            server.start()

    def test_a_server_that_never_answers_is_terminated(self) -> None:
        server, control = self.never_answering()
        with self.assertRaises(rag.RerankerUnavailable):
            server.start()
        self.assertTrue(control.process.terminated)


class TestServerLifetimes(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = FakeTransport(health=Health(now=False))
        self.control = FakeControl(self.transport)
        self.server = LlamaServerProcess(settings("model.gguf"), self.transport, self.control)

    def test_a_per_query_lifetime_stops_the_server_it_started(self) -> None:
        with PerQueryLifetime().serving(self.server):
            self.assertFalse(self.control.process.terminated)
        self.assertTrue(self.control.process.terminated)

    def test_a_process_lifetime_leaves_the_server_running(self) -> None:
        with ProcessLifetime().serving(self.server):
            pass
        self.assertFalse(self.control.process.terminated)

    def test_a_process_lifetime_launches_one_server_for_many_queries(self) -> None:
        for _ in range(3):
            with ProcessLifetime().serving(self.server):
                pass
        self.assertEqual(1, len(self.control.commands))


class TestRerankerLifetime(RerankerTestCase):
    def held(self, transport: FakeTransport, control: FakeControl) -> rag.LlamaReranker:
        return rag.LlamaReranker(LlamaServerProcess(settings(self.gguf), transport, control), self.ledger,
                                 lifetime=ProcessLifetime())

    def test_a_reranker_holding_its_server_launches_it_once(self) -> None:
        transport = FakeTransport(health=Health(now=False))
        control = FakeControl(transport)
        reranker = self.held(transport, control)
        reranker.scores("being", ["first", "second"])
        reranker.scores("essence", ["first", "second"])
        self.assertEqual((1, False), (len(control.commands), control.process.terminated))

    def test_stopping_the_reranker_terminates_its_server(self) -> None:
        transport = FakeTransport(health=Health(now=False))
        control = FakeControl(transport)
        reranker = self.held(transport, control)
        reranker.scores("being", ["first", "second"])
        reranker.stop()
        self.assertTrue(control.process.terminated)

    def test_stopping_a_reranker_that_never_served_terminates_nothing(self) -> None:
        control = FakeControl(FakeTransport())
        self.held(FakeTransport(), control).stop()
        self.assertFalse(control.process.terminated)


if __name__ == "__main__":
    unittest.main()
