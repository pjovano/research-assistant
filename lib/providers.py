from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from _vault.machine import MACHINE_CONFIG_PATH, MachineConfig, MachineConfigError, ProviderChoices
from core_path import VendoredCore

ADAPTER_FIELD = "adapter"
KEY_ENV_FIELD = "key_env"
UNCONFIGURED_FIELD = "unconfigured"
SKILLS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "skills"
SCRIPTS_FOLDER = "scripts"
CORE_HOST_ADAPTERS = "agent_core._adapters.host"

SCHEDULER = "scheduler"
NOTIFIER = "notifier"
SYSTEM_READINGS = "system_readings"
ACCELERATOR = "accelerator"
TRASH = "trash"
SYNC = "sync"
LOCATIONS = "locations"
EMBEDDER = "embedder"
EMBEDDING_STORE = "embedding_store"
FULLTEXT_STORE = "fulltext_store"
RERANKER = "reranker"
LAYOUT_ENGINE = "layout_engine"
LINE_RECOGNIZER = "line_recognizer"
TRANSCRIBER = "transcriber"
DIARIZER = "diarizer"
CITATION_PARSER = "citation_parser"
HOST_PORTS = (SCHEDULER, NOTIFIER, SYSTEM_READINGS, ACCELERATOR, TRASH, SYNC, LOCATIONS)
COMPUTE_PORTS = (EMBEDDER, EMBEDDING_STORE, FULLTEXT_STORE, RERANKER, LAYOUT_ENGINE, LINE_RECOGNIZER, TRANSCRIBER,
                 DIARIZER, CITATION_PARSER)
PORTS = HOST_PORTS + COMPUTE_PORTS


VendoredCore.join_module_path()


class ProviderNotConfigured(LookupError):
    pass


class ApiKey:
    def __init__(self, variable: str, value: str) -> None:
        self._variable = variable
        self._value = value

    @property
    def variable(self) -> str:
        return self._variable

    @property
    def value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"ApiKey(from {self._variable})"

    __str__ = __repr__


class AdapterClass:
    def __init__(self, module: str, name: str, skill: str | None = None) -> None:
        self._module = module
        self._name = name
        self._skill = skill

    def load(self) -> type:
        if self._skill is not None:
            self._make_skill_scripts_importable()
        return getattr(importlib.import_module(self._module), self._name)

    def _make_skill_scripts_importable(self) -> None:
        scripts = str(SKILLS_DIR / self._skill / SCRIPTS_FOLDER)
        if scripts not in sys.path:
            sys.path.insert(0, scripts)


class AdapterClasses:
    def __init__(self, *members: AdapterClass) -> None:
        self._members = members

    def load(self) -> tuple[type, ...]:
        return tuple(member.load() for member in self._members)


ADAPTERS = {
    SCHEDULER: {"launchd": AdapterClass(f"{CORE_HOST_ADAPTERS}.launchd", "LaunchdScheduler")},
    NOTIFIER: {"macos": AdapterClasses(AdapterClass(f"{CORE_HOST_ADAPTERS}.macos_notifiers", "DesktopNotifier"),
                                       AdapterClass(f"{CORE_HOST_ADAPTERS}.macos_notifiers", "RemindersNotifier"))},
    SYSTEM_READINGS: {"macos": AdapterClass(f"{CORE_HOST_ADAPTERS}.macos_readings", "MacosReadings")},
    ACCELERATOR: {"metal": AdapterClass("engine_reach", "MetalAccess")},
    TRASH: {"trash-command": AdapterClass("_writing.conversion", "Trash")},
    SYNC: {},
    LOCATIONS: {},
    EMBEDDER: {"ollama": AdapterClass("_rag.embedding", "OllamaEmbedder")},
    EMBEDDING_STORE: {"chroma": AdapterClass("_rag.chroma", "EmbeddingStore")},
    FULLTEXT_STORE: {"sqlite": AdapterClass("_rag.fulltext", "FullTextStore")},
    RERANKER: {"llama-server": AdapterClass("_rag.reranking", "LlamaReranker")},
    LAYOUT_ENGINE: {"marker-local": AdapterClass("_extract.engine", "MarkerEngine", "extract-corpus")},
    LINE_RECOGNIZER: {"apple-vision": AdapterClass("_clean.ocr", "VisionReader", "clean-pdfs")},
    TRANSCRIBER: {"whisper-cpp": AdapterClass("_transcribe.whispering", "WhisperRun", "transcribe-talks")},
    DIARIZER: {"pyannote": AdapterClass("_transcribe.diarizing", "PyannotePipeline", "transcribe-talks")},
    CITATION_PARSER: {"hf-local": AdapterClass("_references.parsing", "CitationParser")},
}


class Providers:
    def __init__(self, entries: Mapping[str, Mapping], environ: Mapping[str, str], adapters: dict = ADAPTERS,
                 source: Path = MACHINE_CONFIG_PATH) -> None:
        self._entries = entries
        self._environ = environ
        self._adapters = adapters
        self._source = source
        self._loaded: dict[str, object] = {}

    @classmethod
    def from_machine(cls, machine: dict, environ: Mapping[str, str], source: Path = MACHINE_CONFIG_PATH) -> Providers:
        return cls(ProviderChoices(machine, source).entries(), environ, source=source)

    def scheduler(self) -> type:
        return self.adapter(SCHEDULER)

    def notifier(self) -> tuple[type, ...]:
        return self.adapter(NOTIFIER)

    def system_readings(self) -> type:
        return self.adapter(SYSTEM_READINGS)

    def accelerator(self) -> type:
        return self.adapter(ACCELERATOR)

    def trash(self) -> type:
        return self.adapter(TRASH)

    def sync(self) -> type:
        return self.adapter(SYNC)

    def locations(self) -> type:
        return self.adapter(LOCATIONS)

    def embedder(self) -> type:
        return self.adapter(EMBEDDER)

    def embedding_store(self) -> type:
        return self.adapter(EMBEDDING_STORE)

    def fulltext_store(self) -> type:
        return self.adapter(FULLTEXT_STORE)

    def reranker(self) -> type:
        return self.adapter(RERANKER)

    def layout_engine(self) -> type:
        return self.adapter(LAYOUT_ENGINE)

    def line_recognizer(self) -> type:
        return self.adapter(LINE_RECOGNIZER)

    def transcriber(self) -> type:
        return self.adapter(TRANSCRIBER)

    def diarizer(self) -> type:
        return self.adapter(DIARIZER)

    def citation_parser(self) -> type:
        return self.adapter(CITATION_PARSER)

    def adapter(self, port: str):
        if port not in self._loaded:
            self._loaded[port] = self._chosen(port).load()
        return self._loaded[port]

    def api_key(self, port: str) -> ApiKey:
        variable = self._field(port, KEY_ENV_FIELD)
        if variable not in self._environ:
            raise ProviderNotConfigured(f"the environment variable {variable}, which providers.{port}.{KEY_ENV_FIELD} "
                                        f"names, is not set")
        return ApiKey(variable, self._environ[variable])

    def _chosen(self, port: str) -> AdapterClass | AdapterClasses:
        name = self._field(port, ADAPTER_FIELD)
        provided = self._adapters.get(port, {})
        if name not in provided:
            raise ProviderNotConfigured(f"providers.{port}.{ADAPTER_FIELD} names {name!r}, which this version does "
                                        f"not provide; it provides {sorted(provided) or 'none yet'}")
        return provided[name]

    def _field(self, port: str, field: str) -> str:
        value = self._entry(port).get(field)
        if not value:
            raise ProviderNotConfigured(f"providers.{port}.{field} is not set: name it under providers.{port} in "
                                        f"{self._source}, or choose a profile that sets it")
        return str(value)

    def _entry(self, port: str) -> Mapping:
        entry = self._entries.get(port) or {}
        if not isinstance(entry, Mapping):
            raise ProviderNotConfigured(f"providers.{port} in {self._source} must be an object, "
                                        f"not {type(entry).__name__}")
        return entry


class ProviderReport:
    def __init__(self, providers: Providers, profile: str) -> None:
        self._providers = providers
        self._profile = profile

    @classmethod
    def of_machine_file(cls, path: Path, environ: Mapping[str, str]) -> ProviderReport:
        machine = MachineConfig(path).loaded()
        return cls(Providers.from_machine(machine, environ, path), ProviderChoices(machine, path).profile)

    def as_dict(self) -> dict:
        return {"profile": self._profile, "ports": {port: self._resolved(port) for port in PORTS}}

    def _resolved(self, port: str) -> str | list[str] | dict:
        try:
            adapter = self._providers.adapter(port)
        except ProviderNotConfigured as unconfigured:
            return {UNCONFIGURED_FIELD: str(unconfigured)}
        if isinstance(adapter, tuple):
            return [self._named(member) for member in adapter]
        return self._named(adapter)

    @staticmethod
    def _named(adapter: type) -> str:
        return f"{adapter.__module__}.{adapter.__qualname__}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="providers.py")
    parser.add_argument("--machine", type=Path, default=MACHINE_CONFIG_PATH)
    try:
        report = ProviderReport.of_machine_file(parser.parse_args(argv).machine, os.environ)
    except MachineConfigError as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
