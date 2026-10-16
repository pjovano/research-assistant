from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from _support import LiveTree

LiveTree.activate()

import vault
from _adapters.host.icloud import ICloudFolder
from _drive.script import ScriptRun, SkillScript
from _ingest.preflight import (
    START_CLEAN,
    START_EXTRACT,
    EngineModels,
    EngineReadiness,
    InstalledEngine,
    Preflight,
    SyncedFolderReadiness,
    VisionReadiness,
    ZoteroReadiness,
)
from _port_fakes import FakeSyncedFolder
from synced_folder import ConfiguredSyncedFolder

ONLINE = {"zotero_online": True, "conflict_copies": []}
S3_CHECKPOINT = "s3://text_detection/2025_05_07"
HUB_CHECKPOINT = "hf://datalab-to/surya_layout2/order"
BARE_HUB_CHECKPOINT = "datalab-to/surya-ocr-2"
LAYOUT_CHECKPOINT = "hf://datalab-to/surya_layout2"
OCR_ERROR_CHECKPOINT = "s3://ocr_error_detection/2025_02_18"
GGUF_REPOSITORY = "datalab-to/surya-ocr-2-gguf"
WORK = "Doe - 2001 - Logic"
SYNCED_PLACES = {"LIBRARY_DIR": "library", "VOLUMES_DIR": "library/volumes", "INBOX_DIR": "inbox",
                 "CORPUS_DIR": "corpus", "TRANSCRIPTS_DIR": "corpus/talk transcripts"}


class DoctorScript(SkillScript):
    def __init__(self, doctor: dict) -> None:
        super().__init__(Path("file.py"))
        self._doctor = doctor

    def run(self, *args: str) -> ScriptRun:
        return ScriptRun(0, json.dumps(self._doctor))


def answering() -> None:
    return None


def failing() -> None:
    raise RuntimeError("Better BibTeX item.search failed: 500")


def zotero(doctor: dict, probe=answering) -> ZoteroReadiness:
    return ZoteroReadiness(DoctorScript(doctor), probe)


class TestZoteroReadiness(unittest.TestCase):
    def test_an_answering_zotero_raises_nothing(self) -> None:
        self.assertEqual([], zotero(ONLINE).failures())

    def test_zotero_offline_is_a_failure(self) -> None:
        self.assertEqual(["Zotero is not running: start Zotero"],
                         zotero({"zotero_online": False, "conflict_copies": []}).failures())

    def test_the_doctors_conflict_copies_are_left_to_the_synced_folder_check(self) -> None:
        self.assertEqual([], zotero({"zotero_online": True, "conflict_copies": ["Doe 2.md"]}).failures())

    def test_better_bibtex_failing_its_probe_is_a_failure(self) -> None:
        self.assertIn("Better BibTeX", zotero(ONLINE, failing).failures()[0])


class SyncedFolderCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for constant, folder in SYNCED_PLACES.items():
            (self.root / folder).mkdir(parents=True, exist_ok=True)
            self.enterContext(patch.object(vault, constant, self.root / folder))

    def held(self, folder: str, name: str) -> Path:
        path = self.root / folder / name
        path.write_text("text\n", encoding="utf-8")
        return path

    @staticmethod
    def outcome(start: str, folder) -> dict:
        return Preflight([SyncedFolderReadiness.for_start(start, lambda: folder)]).outcome()

    def placeholder_outcome(self, start: str, folder: str) -> tuple[dict, Path]:
        pdf = self.held(folder, f"{WORK}.pdf")
        return self.outcome(start, FakeSyncedFolder(frozenset({pdf}))), pdf

    def assert_halts_naming(self, outcome: dict, named: object) -> None:
        self.assertEqual(("halt", True), (outcome["state"], str(named) in outcome.get("question", "")))


class TestPreflightHaltsOnAPlaceholder(SyncedFolderCase):
    def test_a_placeholder_in_the_library_halts_naming_it(self) -> None:
        self.assert_halts_naming(*self.placeholder_outcome(START_CLEAN, "library"))

    def test_a_placeholder_among_the_volumes_halts_naming_it(self) -> None:
        self.assert_halts_naming(*self.placeholder_outcome(START_CLEAN, "library/volumes"))

    def test_a_placeholder_in_the_inbox_halts_naming_it(self) -> None:
        self.assert_halts_naming(*self.placeholder_outcome(START_CLEAN, "inbox"))

    def test_a_backfill_halts_on_a_placeholder_in_the_library(self) -> None:
        self.assert_halts_naming(*self.placeholder_outcome(START_EXTRACT, "library"))

    def test_a_backfill_leaves_the_inbox_it_never_reads_unchecked(self) -> None:
        outcome, _ = self.placeholder_outcome(START_EXTRACT, "inbox")
        self.assertEqual({"state": "ready"}, outcome)

    def test_an_icloud_stub_in_the_inbox_halts_naming_it(self) -> None:
        stub = self.held("inbox", f".{WORK}.pdf.icloud")
        self.assert_halts_naming(self.outcome(START_CLEAN, ICloudFolder()), stub)


class TestPreflightHaltsOnAConflictCopy(SyncedFolderCase):
    def test_a_conflict_copy_halts_naming_it(self) -> None:
        self.held("corpus", f"{WORK}.md")
        copy = self.held("corpus", f"{WORK} 2.md")
        self.assert_halts_naming(self.outcome(START_CLEAN, FakeSyncedFolder()), copy.name)

    def test_a_conflict_copy_in_the_library_halts_naming_it(self) -> None:
        self.held("library", f"{WORK}.pdf")
        copy = self.held("library", f"{WORK} 2.pdf")
        self.assert_halts_naming(self.outcome(START_CLEAN, FakeSyncedFolder()), copy.name)

    def test_a_backfill_leaves_conflict_copies_to_the_batchs_tail(self) -> None:
        self.held("corpus", f"{WORK}.md")
        self.held("corpus", f"{WORK} 2.md")
        self.assertEqual({"state": "ready"}, self.outcome(START_EXTRACT, FakeSyncedFolder()))


class TestPreflightReadyOnASettledFolder(SyncedFolderCase):
    def test_no_placeholder_and_no_conflict_copy_is_ready(self) -> None:
        self.held("library", f"{WORK}.pdf")
        self.held("inbox", f"{WORK}.pdf")
        self.held("corpus", f"{WORK}.md")
        self.assertEqual({"state": "ready"}, self.outcome(START_CLEAN, FakeSyncedFolder()))

    def test_an_absent_inbox_is_ready(self) -> None:
        (self.root / "inbox").rmdir()
        self.assertEqual({"state": "ready"}, self.outcome(START_CLEAN, FakeSyncedFolder()))


class TestPreflightHaltsOnAnUnconfiguredSyncPort(SyncedFolderCase):
    def unconfigured_outcome(self, profile: str) -> dict:
        folder = ConfiguredSyncedFolder({"profile": profile}, {}).built
        return Preflight([SyncedFolderReadiness.for_start(START_CLEAN, folder)]).outcome()

    def test_a_profile_without_a_sync_adapter_halts_naming_providers_sync(self) -> None:
        self.assert_halts_naming(self.unconfigured_outcome("api-light"), "providers.sync.adapter is not set")

    def test_a_sync_adapter_not_built_yet_halts_naming_it(self) -> None:
        self.assert_halts_naming(self.unconfigured_outcome("linux-local"), "providers.sync.adapter names 'syncthing'")


class TestVisionReadiness(unittest.TestCase):
    def test_an_installed_module_is_ready(self) -> None:
        self.assertEqual([], VisionReadiness("json").failures())

    def test_a_missing_module_is_a_failure(self) -> None:
        self.assertEqual(1, len(VisionReadiness("no_such_vision_module").failures()))


class EngineCase(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.model_cache = root / "models"
        self.hub_cache = root / "hub"

    def models(self, *checkpoints: str) -> EngineModels:
        return EngineModels(list(checkpoints), self.model_cache, self.hub_cache)

    def cache_s3(self) -> None:
        self.put(self.model_cache / "text_detection" / "2025_05_07" / "model.safetensors")

    def cache_hub(self, folder: str) -> None:
        self.put(self.hub_cache / folder / "snapshots" / "abc" / "model.gguf")

    @staticmethod
    def put(path: Path) -> None:
        path.parent.mkdir(parents=True)
        path.write_bytes(b"weights")


class TestEngineModels(EngineCase):
    def test_cached_checkpoints_are_none_missing(self) -> None:
        self.cache_s3()
        self.cache_hub("models--datalab-to--surya_layout2")
        self.cache_hub("models--datalab-to--surya-ocr-2")
        self.assertEqual([], self.models(S3_CHECKPOINT, HUB_CHECKPOINT, BARE_HUB_CHECKPOINT).missing())

    def test_an_empty_download_directory_is_missing(self) -> None:
        (self.model_cache / "text_detection" / "2025_05_07").mkdir(parents=True)
        self.assertEqual([S3_CHECKPOINT], self.models(S3_CHECKPOINT).missing())

    def test_an_uncached_hub_repository_is_missing(self) -> None:
        self.assertEqual([BARE_HUB_CHECKPOINT], self.models(BARE_HUB_CHECKPOINT).missing())

    def test_missing_models_are_a_failure_naming_them(self) -> None:
        failures = EngineReadiness(lambda: self.models(HUB_CHECKPOINT)).failures()
        self.assertIn(HUB_CHECKPOINT, failures[0])

    def test_unreadable_engine_settings_are_a_failure(self) -> None:
        def unreadable() -> EngineModels:
            raise ModuleNotFoundError("No module named 'torch'")
        self.assertIn("torch", EngineReadiness(unreadable).failures()[0])


class TestInstalledEngine(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        self.put(self.model_cache / "ocr_error_detection" / "2025_02_18" / "model.safetensors")
        self.cache_hub("models--datalab-to--surya_layout2")

    def installed_missing(self) -> list[str]:
        settings = SimpleNamespace(
            DETECTOR_MODEL_CHECKPOINT=S3_CHECKPOINT, SURYA_MODEL_CHECKPOINT=BARE_HUB_CHECKPOINT,
            FAST_LAYOUT_MODEL_CHECKPOINT=LAYOUT_CHECKPOINT, FAST_ORDER_MODEL_CHECKPOINT=HUB_CHECKPOINT,
            OCR_ERROR_MODEL_CHECKPOINT=OCR_ERROR_CHECKPOINT, SURYA_GGUF_REPO=GGUF_REPOSITORY,
            MODEL_CACHE_DIR=str(self.model_cache))
        modules = {"surya.settings": SimpleNamespace(settings=settings),
                   "huggingface_hub.constants": SimpleNamespace(HF_HUB_CACHE=str(self.hub_cache))}
        with patch.dict(sys.modules, modules):
            return InstalledEngine.models().missing()

    def test_a_checkpoint_the_settings_name_but_the_converter_never_loads_is_never_missing(self) -> None:
        self.cache_hub("models--datalab-to--surya-ocr-2-gguf")
        self.assertEqual([], self.installed_missing())

    def test_an_uncached_gguf_repository_the_converter_loads_is_missing(self) -> None:
        self.assertEqual([GGUF_REPOSITORY], self.installed_missing())


class FailingCheck:
    def __init__(self, *failures: str) -> None:
        self._failures = list(failures)

    def failures(self) -> list[str]:
        return self._failures


class TestPreflight(unittest.TestCase):
    def test_no_failure_is_ready(self) -> None:
        self.assertEqual({"state": "ready"}, Preflight([FailingCheck()]).outcome())

    def test_every_failure_goes_into_one_halt_question(self) -> None:
        outcome = Preflight([FailingCheck("Zotero is not running"), FailingCheck("no Vision")]).outcome()
        self.assertEqual(("halt", "Zotero is not running | no Vision"), (outcome["state"], outcome["question"]))


if __name__ == "__main__":
    unittest.main()
