from __future__ import annotations

import unittest

import requests

from _support import LiveTree

LiveTree.activate()

import rag
from _rag.embedding import EMBED_BATCH_SIZE
from _rag_fakes import FakeEmbedder

MODEL_NOT_FOUND = {"error": "model 'bge-m3' not found, try pulling it first"}
HTTP_OK = 200
FIRST_ERROR_STATUS = 400


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = HTTP_OK, reason: str = "OK") -> None:
        self._payload = payload
        self.status_code = status_code
        self.reason = reason

    @property
    def ok(self) -> bool:
        return self.status_code < FIRST_ERROR_STATUS

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, refusal: FakeResponse | None = None) -> None:
        self._refusal = refusal
        self.posts: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict, timeout: float) -> FakeResponse:
        self.posts.append((url, json))
        return self._refusal or FakeResponse({"embeddings": [[1.0, 0.0] for _ in json["input"]]})


class RefusingSession:
    def post(self, url: str, json: dict, timeout: float) -> FakeResponse:
        raise requests.ConnectionError(f"connection to {url} refused")


class TestOllamaEmbedder(unittest.TestCase):
    def embedder(self, session: FakeSession) -> rag.OllamaEmbedder:
        return rag.OllamaEmbedder(rag.MachineSettings({"embedding_model": "bge-m3"}), session)

    def test_a_refusal_carries_the_servers_own_error_text(self) -> None:
        session = FakeSession(refusal=FakeResponse(MODEL_NOT_FOUND, status_code=404, reason="Not Found"))
        with self.assertRaises(rag.EmbeddingUnavailable) as raised:
            self.embedder(session).embed(["being"])
        self.assertIn("HTTP 404: model 'bge-m3' not found, try pulling it first", str(raised.exception))

    def test_texts_are_posted_in_batches_of_at_most_the_batch_size(self) -> None:
        session = FakeSession()
        self.embedder(session).embed([f"text {n}" for n in range(EMBED_BATCH_SIZE * 2 + 6)])
        batch_sizes = [len(payload["input"]) for _, payload in session.posts]
        self.assertEqual([EMBED_BATCH_SIZE, EMBED_BATCH_SIZE, 6], batch_sizes)

    def test_the_request_names_the_model_and_the_embed_endpoint(self) -> None:
        session = FakeSession()
        self.embedder(session).embed(["one"])
        [(url, payload)] = session.posts
        self.assertEqual(("http://localhost:11434/api/embed", "bge-m3"), (url, payload["model"]))

    def test_a_query_is_posted_with_the_instruction_prefix_and_a_document_without(self) -> None:
        session = FakeSession()
        embedder = self.embedder(session)
        embedder.embed_query("being")
        embedder.embed(["being"])
        [(_, query_payload), (_, document_payload)] = session.posts
        self.assertEqual((rag.QUERY_INSTRUCTION + "being", "being"),
                         (query_payload["input"][0], document_payload["input"][0]))

    def test_one_vector_comes_back_per_text(self) -> None:
        self.assertEqual(3, len(self.embedder(FakeSession()).embed(["a", "b", "c"])))

    def test_a_refused_connection_raises_embedding_unavailable(self) -> None:
        with self.assertRaises(rag.EmbeddingUnavailable):
            self.embedder(RefusingSession()).embed(["being"])

    def test_the_machine_url_and_model_default_to_ollama_and_the_4b_embedding(self) -> None:
        settings = rag.MachineSettings({})
        self.assertEqual(("http://localhost:11434", "qwen3-embedding:4b"),
                         (settings.ollama_url, settings.embedding_model))

    def test_the_keep_alive_defaults_to_five_minutes_and_is_sent_with_every_batch(self) -> None:
        session = FakeSession()
        rag.OllamaEmbedder(rag.MachineSettings({}), session).embed(["one"])
        [(_, payload)] = session.posts
        self.assertEqual("5m", payload["keep_alive"])

    def test_the_keep_alive_comes_from_machine_json_when_set(self) -> None:
        session = FakeSession()
        rag.OllamaEmbedder(rag.MachineSettings({"ollama_keep_alive": "1h"}), session).embed(["one"])
        self.assertEqual("1h", session.posts[0][1]["keep_alive"])


class TestEmbeddingCheck(unittest.TestCase):
    PAIRS = (rag.CheckPair("Das Sein", "Being", "German"), rag.CheckPair("Cogito", "I think", "Latin"))
    ADVISORY = (rag.CheckPair("τὸ ὄν", "Being is said in many ways", "Greek"),)
    UNRELATED = ("The train",)

    def vectors(self, german: list[float]) -> dict[str, list[float]]:
        return {"Das Sein": german, "Being": [1.0, 0.0, 0.0], "Cogito": [0.0, 1.0, 0.0],
                "I think": [0.1, 1.0, 0.0], "The train": [0.0, 0.0, 1.0]}

    def four_dimensional(self, greek: list[float]) -> dict[str, list[float]]:
        return {"Das Sein": [0.9, 0.1, 0.0, 0.0], "Being": [1.0, 0.0, 0.0, 0.0],
                "Cogito": [0.0, 1.0, 0.0, 0.0], "I think": [0.1, 1.0, 0.0, 0.0],
                "The train": [0.0, 0.0, 1.0, 0.0], "τὸ ὄν": greek,
                "Being is said in many ways": [0.0, 0.0, 0.0, 1.0]}

    def report(self, german: list[float]) -> dict:
        embedder = FakeEmbedder(vectors=self.vectors(german))
        return rag.EmbeddingCheck(embedder, rag.CheckPassages(self.PAIRS, (), self.UNRELATED)).report()

    def advisory_report(self, greek: list[float]) -> dict:
        embedder = FakeEmbedder(vectors=self.four_dimensional(greek))
        return rag.EmbeddingCheck(embedder, rag.CheckPassages(self.PAIRS, self.ADVISORY, self.UNRELATED)).report()

    def test_an_advisory_pair_that_fails_leaves_the_check_passing(self) -> None:
        report = self.advisory_report(greek=[0.0, 0.0, 1.0, 0.0])
        self.assertTrue(report["passes"])
        self.assertIn("τὸ ὄν", report["advisory_failures"])

    def test_an_advisory_pair_that_holds_is_reported_without_a_failure(self) -> None:
        report = self.advisory_report(greek=[0.0, 0.0, 0.0, 0.95])
        self.assertEqual((True, []), (report["passes"], report["advisory_failures"]))

    def test_the_advisory_languages_are_named_in_the_report(self) -> None:
        report = self.advisory_report(greek=[0.0, 0.0, 0.0, 0.95])
        self.assertEqual(["Greek"], report["advisory_languages"])

    def test_pairs_closer_to_each_other_than_to_anything_else_pass(self) -> None:
        self.assertTrue(self.report(german=[0.9, 0.1, 0.0])["passes"])

    def test_a_passage_closer_to_the_unrelated_passage_fails(self) -> None:
        report = self.report(german=[0.1, 0.0, 1.0])
        self.assertEqual((False, "The train"), (report["passes"], report["passages"][0]["closest_other"]))

    def test_every_passage_of_every_pair_is_judged(self) -> None:
        self.assertEqual(4, len(self.report(german=[0.9, 0.1, 0.0])["passages"]))

    def test_the_built_in_pairs_embed_all_nine_passages_once(self) -> None:
        embedder = FakeEmbedder()
        rag.EmbeddingCheck(embedder).report()
        self.assertEqual([9], [len(batch) for batch in embedder.batches])

    def test_greek_is_the_only_advisory_language(self) -> None:
        self.assertEqual(["Greek"], [pair.language for pair in rag.ADVISORY_PAIRS])


if __name__ == "__main__":
    unittest.main()
