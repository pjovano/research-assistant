from __future__ import annotations

import requests

from .settings import MachineSettings

EMBED_PATH = "/api/embed"
EMBED_BATCH_SIZE = 32
EMBED_TIMEOUT_SECONDS = 300
_OLLAMA_ERROR_FIELD = "error"
QUERY_INSTRUCTION = ("Instruct: Given a research question, retrieve the passages of philosophical works that bear on it"
                     "\nQuery: ")


class EmbeddingUnavailable(RuntimeError):
    pass


class OllamaEmbedder:
    def __init__(self, settings: MachineSettings | None = None, session: requests.Session | None = None) -> None:
        self._settings = settings or MachineSettings()
        self._session = session or requests.Session()

    @property
    def model(self) -> str:
        return self._settings.embedding_model

    def embed_query(self, query: str) -> list[float]:
        [vector] = self.embed([QUERY_INSTRUCTION + query])
        return vector

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            vectors.extend(self._embedded_batch(texts[start:start + EMBED_BATCH_SIZE]))
        return vectors

    def _embedded_batch(self, batch: list[str]) -> list[list[float]]:
        try:
            vectors = self._posted(batch)["embeddings"]
        except (requests.RequestException, KeyError, TypeError, ValueError) as error:
            raise EmbeddingUnavailable(self._cause(f"{type(error).__name__}: {error}")) from error
        if len(vectors) != len(batch):
            raise EmbeddingUnavailable(self._cause(f"{len(vectors)} embeddings returned for {len(batch)} texts"))
        return vectors

    def _posted(self, batch: list[str]) -> dict:
        payload = {"model": self.model, "input": batch,
                   "keep_alive": self._settings.ollama_keep_alive}
        response = self._session.post(self._url, json=payload, timeout=EMBED_TIMEOUT_SECONDS)
        if not response.ok:
            raise EmbeddingUnavailable(self._cause(_refusal(response)))
        return response.json()

    @property
    def _url(self) -> str:
        return self._settings.ollama_url.rstrip("/") + EMBED_PATH

    def _cause(self, detail: str) -> str:
        return f"embedding with {self.model} through {self._url} failed: {detail}"


def _refusal(response: requests.Response) -> str:
    return f"HTTP {response.status_code}: {_error_detail(response) or response.reason}"


def _error_detail(response: requests.Response) -> str | None:
    try:
        return response.json().get(_OLLAMA_ERROR_FIELD)
    except (ValueError, AttributeError):
        return None
