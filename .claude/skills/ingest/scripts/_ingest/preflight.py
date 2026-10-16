from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Callable
from pathlib import Path

from _drive.script import SkillScript

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
        return self._conflict_copies(doctor) + self._better_bibtex()

    @staticmethod
    def _conflict_copies(doctor: dict) -> list[str]:
        copies = doctor.get("conflict_copies") or []
        return [f"iCloud left conflict copies; merge and delete each: {copies}"] if copies else []

    def _better_bibtex(self) -> list[str]:
        try:
            self._probe_better_bibtex()
        except Exception as failure:
            return [f"Better BibTeX does not answer, so the duplicate check cannot run: {failure}"]
        return []


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
