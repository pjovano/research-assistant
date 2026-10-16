from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _health.settings import HealthSettings
from _ingest.progress import UPDATE_MINUTES_KEY, UpdateInterval
from _rag import settings as rag_settings
from _references.parsing import CITATION_PARSER_MODEL_KEY, ParserSettings
from _transcribe import settings as talk_settings
from _vault.machine import MachineConfig
from _vault.paths import OBSIDIAN_VAULT_NAME, VAULT_DIR_KEY, ConfiguredVault
from engine_slots import ENGINE_SLOTS_KEY, EngineSlots
from surya_servers import SURYA_CACHE_DIR_KEY, surya_cache_dir

ADDITIVE_KEYS = {
    "profile": "mac-local",
    "providers": {
        "embedder": {"adapter": "openai-compatible", "url": "https://embeddings.invalid/v1", "model": "placeholder",
                     "key_env": "EMBEDDING_API_KEY"},
        "layout_engine": {"adapter": "datalab-api", "key_env": "DATALAB_API_KEY", "concurrency": 4},
    },
}
TODAY = {
    rag_settings.OLLAMA_URL_KEY: "http://localhost:11500",
    rag_settings.OLLAMA_KEEP_ALIVE_KEY: "10m",
    rag_settings.EMBEDDING_MODEL_KEY: "placeholder-embedding:1b",
    rag_settings.RERANKER_MODEL_KEY: "~/models/reranker.gguf",
    rag_settings.RERANKER_POOLING_KEY: "mean",
    rag_settings.LLAMA_SERVER_KEY: "~/bin/llama-server",
    talk_settings.WHISPER_CLI_KEY: "~/bin/whisper-cli",
    talk_settings.WHISPER_MODEL_KEY: "~/models/whisper.bin",
    talk_settings.DIARIZATION_MODEL_KEY: "placeholder/diarization",
    talk_settings.YT_DLP_KEY: "~/bin/yt-dlp",
    talk_settings.TALKS_PLAYLIST_KEY: "https://playlist.invalid/list",
    "health": {"alert_cooldown_minutes": 30, "retention_days": 7, "other_processes_kept": 3},
    ENGINE_SLOTS_KEY: 4,
    CITATION_PARSER_MODEL_KEY: "placeholder/parser",
    UPDATE_MINUTES_KEY: 15,
    SURYA_CACHE_DIR_KEY: "~/surya-cache",
}


class TodaysReaders:
    def __init__(self, machine: dict) -> None:
        self._machine = machine

    def values(self) -> dict[str, tuple]:
        return {"rag": self._rag(), "talks": self._talks(), "health": self._health(),
                "engine slots": self._engine_slots(), "citation parser": (ParserSettings(self._machine).model,),
                "batch update": (UpdateInterval(self._machine).minutes,),
                "surya cache": (surya_cache_dir(self._machine),)}

    def _rag(self) -> tuple:
        settings = rag_settings.MachineSettings(self._machine)
        return (settings.ollama_url, settings.ollama_keep_alive, settings.embedding_model, settings.reranker_model,
                settings.reranker_pooling, settings.llama_server)

    def _talks(self) -> tuple:
        settings = talk_settings.TalkSettings(self._machine)
        return (settings.whisper_cli, settings.whisper_model, settings.diarization_model, settings.yt_dlp,
                settings.playlist)

    def _health(self) -> tuple:
        settings = HealthSettings(self._machine)
        return settings.alert_cooldown_seconds, settings.retention_seconds, settings.other_processes_kept

    def _engine_slots(self) -> tuple:
        slots = EngineSlots(self._machine)
        return slots.configured(), slots.wanted()


class TestTodaysReaderAcceptsTheAdditiveKeys(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)

    def written(self, machine: dict) -> Path:
        path = self.base / "machine.json"
        path.write_text(json.dumps(machine), encoding="utf-8")
        return path

    def test_the_loaded_configuration_carries_every_key_unchanged(self) -> None:
        machine = {**TODAY, **ADDITIVE_KEYS}
        self.assertEqual(machine, MachineConfig(self.written(machine)).loaded())

    def test_every_settings_reader_gives_the_same_values_with_the_additive_keys(self) -> None:
        without = TodaysReaders(TODAY).values()
        with_keys = TodaysReaders({**TODAY, **ADDITIVE_KEYS}).values()
        for reader, values in without.items():
            with self.subTest(reader=reader):
                self.assertEqual(values, with_keys[reader])

    def test_every_settings_reader_gives_its_defaults_beside_the_additive_keys_alone(self) -> None:
        self.assertEqual(TodaysReaders({}).values(), TodaysReaders(ADDITIVE_KEYS).values())

    def test_the_vault_root_is_the_one_vault_dir_names_beside_the_additive_keys(self) -> None:
        (self.base / OBSIDIAN_VAULT_NAME).mkdir()
        machine = {VAULT_DIR_KEY: str(self.base), **ADDITIVE_KEYS}
        self.assertEqual(self.base, ConfiguredVault(machine).resolved())


if __name__ == "__main__":
    unittest.main()
