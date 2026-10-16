from __future__ import annotations

from pathlib import Path

import vault as vault_lib

OLLAMA_URL_KEY = "ollama_url"
OLLAMA_KEEP_ALIVE_KEY = "ollama_keep_alive"
EMBEDDING_MODEL_KEY = "embedding_model"
RERANKER_MODEL_KEY = "reranker_model"
RERANKER_POOLING_KEY = "reranker_pooling"
LLAMA_SERVER_KEY = "llama_server"

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_KEEP_ALIVE = "5m"
DEFAULT_EMBEDDING_MODEL = "qwen3-embedding:4b"
DEFAULT_RERANKER_POOLING = "rank"
DEFAULT_LLAMA_SERVER = "llama-server"


class MachineSettings:
    def __init__(self, values: dict | None = None) -> None:
        self._values = vault_lib.MACHINE if values is None else values

    @property
    def ollama_url(self) -> str:
        return self._text(OLLAMA_URL_KEY, DEFAULT_OLLAMA_URL)

    @property
    def ollama_keep_alive(self) -> str:
        return self._text(OLLAMA_KEEP_ALIVE_KEY, DEFAULT_OLLAMA_KEEP_ALIVE)

    @property
    def embedding_model(self) -> str:
        return self._text(EMBEDDING_MODEL_KEY, DEFAULT_EMBEDDING_MODEL)

    @property
    def reranker_model(self) -> Path | None:
        value = self._values.get(RERANKER_MODEL_KEY)
        return Path(str(value)).expanduser() if value else None

    @property
    def reranker_pooling(self) -> str:
        return self._text(RERANKER_POOLING_KEY, DEFAULT_RERANKER_POOLING)

    @property
    def llama_server(self) -> str:
        return self._text(LLAMA_SERVER_KEY, DEFAULT_LLAMA_SERVER)

    def _text(self, key: str, default: str) -> str:
        return str(self._values.get(key) or default)
