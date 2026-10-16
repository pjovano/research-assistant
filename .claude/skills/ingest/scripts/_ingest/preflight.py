from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Callable
from pathlib import Path, PurePath

import vault
from _drive.script import SkillScript
from _ports.host import SyncedFolder
from synced_folder import SyncedFolderUnavailable

START_CLEAN = "clean"
START_EXTRACT = "extract"
VISION_MODULE = "ocrmac"
ENGINE_SETTINGS_MODULE = "surya.settings"
LOADED_CHECKPOINT_SETTINGS = ("FAST_LAYOUT_MODEL_CHECKPOINT", "FAST_ORDER_MODEL_CHECKPOINT", "OCR_ERROR_MODEL_CHECKPOINT",
                              "SURYA_GGUF_REPO")
S3_SCHEME = "s3://"
HF_SCHEME = "hf://"
REPOSITORY_PARTS = 2
PROBE_CITEKEY = "ingest-preflight-probe"
ZOTERO_OFFLINE = "Zotero is not running: start Zotero"
VISION_MISSING = "Apple Vision is not available on this machine: run the batch on a Mac"
PLACEHOLDERS_FOUND = ("iCloud keeps these files' bytes off the disk, so a stage reading one would fail: turn Optimize "
                      "Mac Storage off and wait until each is downloaded: {}")
EVERY_FILE: tuple[str, ...] = ()
BATCH_INBOX_FILES = (vault.PDF_SUFFIX, vault.NOTE_SUFFIX)


class ReadPlace:
    def __init__(self, directory: Path, kinds: tuple[str, ...] = EVERY_FILE) -> None:
        self._directory = directory
        self._kinds = kinds

    def files(self) -> list[Path]:
        if not self._directory.is_dir():
            return []
        return [path for path in sorted(self._directory.iterdir()) if not path.is_dir() and self._is_read(path)]

    def _is_read(self, path: Path) -> bool:
        if not self._kinds:
            return True
        suffixes = [suffix.lower() for suffix in PurePath(path.name).suffixes]
        return any(kind in suffixes for kind in self._kinds)


class ZoteroReadiness:
    def __init__(self, file_script: SkillScript, probe_better_bibtex: Callable[[], None]) -> None:
        self._file_script = file_script
        self._probe_better_bibtex = probe_better_bibtex

    def failures(self) -> list[str]:
        run = self._file_script.run("doctor")
        doctor = run.payload()
        if not isinstance(doctor, dict):
            return [f"`file.py doctor` failed: {run.tail}"]
        if not doctor.get("zotero_online"):
            return [ZOTERO_OFFLINE]
        return self._better_bibtex()

    def _better_bibtex(self) -> list[str]:
        try:
            self._probe_better_bibtex()
        except Exception as failure:
            return [f"Better BibTeX does not answer, so the duplicate check cannot run: {failure}"]
        return []


class SyncedFolderReadiness:
    def __init__(self, folder: Callable[[], SyncedFolder], conflict_directories: tuple[Path, ...],
                 read_places: tuple[ReadPlace, ...]) -> None:
        self._folder = folder
        self._conflict_directories = conflict_directories
        self._read_places = read_places

    @classmethod
    def for_start(cls, start: str, folder: Callable[[], SyncedFolder]) -> SyncedFolderReadiness:
        library = (ReadPlace(vault.LIBRARY_DIR), ReadPlace(vault.VOLUMES_DIR))
        if start == START_EXTRACT:
            return cls(folder, (), library)
        held_notes_and_library = (vault.CORPUS_DIR, vault.TRANSCRIPTS_DIR, vault.LIBRARY_DIR)
        return cls(folder, held_notes_and_library, (*library, ReadPlace(vault.INBOX_DIR, BATCH_INBOX_FILES)))

    def failures(self) -> list[str]:
        try:
            folder = self._folder()
        except SyncedFolderUnavailable as unavailable:
            return [str(unavailable)]
        return self._conflict_copies(folder) + self._placeholders(folder)

    def _conflict_copies(self, folder: SyncedFolder) -> list[str]:
        copies = sorted(path.name for directory in self._conflict_directories
                        for path in folder.conflict_copies(directory))
        return [f"iCloud left conflict copies; merge and delete each: {copies}"] if copies else []

    def _placeholders(self, folder: SyncedFolder) -> list[str]:
        placeholders = [str(path) for place in self._read_places for path in place.files()
                        if folder.not_downloaded(path)]
        return [PLACEHOLDERS_FOUND.format(placeholders)] if placeholders else []


class VisionReadiness:
    def __init__(self, module: str = VISION_MODULE) -> None:
        self._module = module

    def failures(self) -> list[str]:
        return [] if importlib.util.find_spec(self._module) is not None else [VISION_MISSING]


class EngineCheckpoint:
    def __init__(self, reference: str) -> None:
        self.reference = reference

    def is_cached(self, model_cache: Path, hub_cache: Path) -> bool:
        if self.reference.startswith(S3_SCHEME):
            return self._holds_a_file(model_cache / self.reference.removeprefix(S3_SCHEME))
        return self._holds_a_file(hub_cache / self._hub_folder() / "snapshots")

    def _hub_folder(self) -> str:
        repository = self.reference.removeprefix(HF_SCHEME).split("/")[:REPOSITORY_PARTS]
        return "--".join(["models", *repository])

    @staticmethod
    def _holds_a_file(directory: Path) -> bool:
        return directory.is_dir() and any(path.is_file() for path in directory.rglob("*"))


class EngineModels:
    def __init__(self, checkpoints: list[str], model_cache: Path, hub_cache: Path) -> None:
        self._checkpoints = [EngineCheckpoint(reference) for reference in checkpoints]
        self._model_cache = model_cache
        self._hub_cache = hub_cache

    def missing(self) -> list[str]:
        return [checkpoint.reference for checkpoint in self._checkpoints
                if not checkpoint.is_cached(self._model_cache, self._hub_cache)]


class EngineReadiness:
    def __init__(self, models: Callable[[], EngineModels]) -> None:
        self._models = models

    def failures(self) -> list[str]:
        try:
            missing = self._models().missing()
        except Exception as failure:
            return [f"the engine's settings cannot be read: {type(failure).__name__}: {failure}"]
        if not missing:
            return []
        return [f"the engine's models are not in the cache ({', '.join(missing)}): run the model step the README "
                "states"]


class InstalledEngine:
    @staticmethod
    def models() -> EngineModels:
        settings = importlib.import_module(ENGINE_SETTINGS_MODULE).settings
        hub_cache = Path(importlib.import_module("huggingface_hub.constants").HF_HUB_CACHE)
        checkpoints = [getattr(settings, name) for name in LOADED_CHECKPOINT_SETTINGS]
        return EngineModels([str(checkpoint) for checkpoint in checkpoints], Path(settings.MODEL_CACHE_DIR),
                            hub_cache)


class Preflight:
    def __init__(self, checks: list) -> None:
        self._checks = checks

    def outcome(self) -> dict:
        failures = [failure for check in self._checks for failure in check.failures()]
        if failures:
            return {"state": "halt", "question": " | ".join(failures)}
        return {"state": "ready"}
