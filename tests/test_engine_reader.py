from __future__ import annotations

import contextlib
import importlib.abc
import importlib.util
import io
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _clean.lines import TextLines
from _clean.ocr import INFERENCE_MANAGER, EngineReader, EngineReadings
from _vaults import TextPdf
from engine_guard import EngineUnresponsive
from surya_servers import EngineRun

KEEP_ALIVE = "SURYA_INFERENCE_KEEP_ALIVE"
KEEP_ALIVE_ON = "1"
SURYA_PACKAGE = "surya"
MARKER_PACKAGE = "marker"
MARKER_MODELS = "marker.models"
PROMPT_TYPE_BLOCK = "block"
ENGINE_OUTPUT = "<p>read by the engine</p>"
ENGINE_TEXT = "read by the engine"
PACKAGE_SEPARATOR = "."
RUN_FILE = "engine-run.json"
SILENCE_LIMIT_SECONDS = 600.0


class FakeInferenceManager:
    def generate(self, batch: list) -> list[types.SimpleNamespace]:
        return [types.SimpleNamespace(error=False, raw=ENGINE_OUTPUT) for _ in batch]


class FakeSurya(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self) -> None:
        self.keep_alive_at_first_import: str | None = None
        self._imported = False

    def find_spec(self, fullname: str, path, target=None):
        if fullname.split(PACKAGE_SEPARATOR)[0] != SURYA_PACKAGE:
            return None
        self._record_first_import()
        return importlib.util.spec_from_loader(fullname, self, is_package=True)

    def exec_module(self, module: types.ModuleType) -> None:
        module.PROMPT_TYPE_BLOCK = PROMPT_TYPE_BLOCK
        module.BatchInputItem = types.SimpleNamespace
        module.SuryaInferenceManager = FakeInferenceManager

    def _record_first_import(self) -> None:
        if not self._imported:
            self._imported = True
            self.keep_alive_at_first_import = os.environ.get(KEEP_ALIVE)


def fake_marker_modules() -> dict[str, types.ModuleType]:
    models = types.ModuleType(MARKER_MODELS)
    models.create_model_dict = lambda inference_manager: {INFERENCE_MANAGER: inference_manager}
    return {MARKER_PACKAGE: types.ModuleType(MARKER_PACKAGE), MARKER_MODELS: models}


class EngineModules:
    def __init__(self) -> None:
        self._held = {name: module for name, module in sys.modules.items() if self._is_engine(name)}

    def forget(self) -> None:
        self._drop_engine_entries()
        sys.modules.update(fake_marker_modules())

    def restore(self) -> None:
        self._drop_engine_entries()
        sys.modules.update(self._held)

    def _drop_engine_entries(self) -> None:
        for name in [name for name in sys.modules if self._is_engine(name)]:
            del sys.modules[name]

    @staticmethod
    def _is_engine(name: str) -> bool:
        return name.split(PACKAGE_SEPARATOR)[0] in (SURYA_PACKAGE, MARKER_PACKAGE)


PROBE_MODULE = "engine_reader_probe"


class TestEngineModulesIsolation(unittest.TestCase):
    def setUp(self) -> None:
        self.modules = EngineModules()
        self.modules.forget()
        self.addCleanup(sys.modules.pop, PROBE_MODULE, None)

    def test_restoring_keeps_a_module_imported_meanwhile_outside_the_engine(self) -> None:
        sys.modules[PROBE_MODULE] = types.ModuleType(PROBE_MODULE)
        self.modules.restore()
        self.assertIn(PROBE_MODULE, sys.modules)

    def test_restoring_drops_the_fake_engine_modules(self) -> None:
        fake = sys.modules[MARKER_MODELS]
        self.modules.restore()
        self.assertIsNot(fake, sys.modules.get(MARKER_MODELS))


class TestEngineReaderEnvironment(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.pdf_path = TextPdf(Path(directory.name) / "plain.pdf").write()
        self._isolate(mock.patch.dict(os.environ))
        os.environ.pop(KEEP_ALIVE, None)
        modules = EngineModules()
        modules.forget()
        self.addCleanup(modules.restore)
        self.surya = FakeSurya()
        sys.meta_path.insert(0, self.surya)
        self.addCleanup(sys.meta_path.remove, self.surya)

    def _isolate(self, patcher) -> None:
        patcher.start()
        self.addCleanup(patcher.stop)

    def _read(self) -> EngineReadings:
        run = EngineRun(self.pdf_path.with_name(RUN_FILE))
        return EngineReader(self.pdf_path, run=run).read(TextLines(self.pdf_path).collect()[:1])

    def test_the_servers_are_kept_alive_before_surya_reads_its_settings(self) -> None:
        self._read()
        self.assertEqual(KEEP_ALIVE_ON, self.surya.keep_alive_at_first_import)

    def test_the_engine_reading_is_returned_as_plain_text(self) -> None:
        self.assertEqual([ENGINE_TEXT], [text for _, text in self._read().readings])


class RunWatchingInferenceManager(FakeInferenceManager):
    def __init__(self, run: EngineRun) -> None:
        self._run = run
        self.run_in_progress_while_generating: bool | None = None

    def generate(self, batch: list) -> list[types.SimpleNamespace]:
        self.run_in_progress_while_generating = self._run.in_progress()
        return super().generate(batch)


class TestEngineReaderRecordsItsRun(TestEngineReaderEnvironment):
    def setUp(self) -> None:
        super().setUp()
        self.run = EngineRun(self.pdf_path.with_name(RUN_FILE))
        self.manager = RunWatchingInferenceManager(self.run)

    def _read_recording(self) -> None:
        reader = EngineReader(self.pdf_path, {INFERENCE_MANAGER: self.manager}, self.run)
        reader.read(TextLines(self.pdf_path).collect()[:1])

    def test_an_engine_run_is_recorded_while_the_engine_reads_so_the_idle_reaper_spares_its_servers(self) -> None:
        self._read_recording()
        self.assertTrue(self.manager.run_in_progress_while_generating)

    def test_the_engine_run_is_cleared_once_the_reading_ends(self) -> None:
        self._read_recording()
        self.assertFalse(self.run.in_progress())


class UnresponsiveInferenceManager:
    def generate(self, batch: list) -> list:
        raise EngineUnresponsive(SILENCE_LIMIT_SECONDS, len(batch))


class TestEngineReaderOverAnUnresponsiveEngine(TestEngineReaderEnvironment):
    def setUp(self) -> None:
        super().setUp()
        self.run = EngineRun(self.pdf_path.with_name(RUN_FILE))
        self.stderr = io.StringIO()

    def _read_unanswered(self) -> EngineReadings:
        reader = EngineReader(self.pdf_path, {INFERENCE_MANAGER: UnresponsiveInferenceManager()}, self.run)
        with contextlib.redirect_stderr(self.stderr):
            return reader.read(TextLines(self.pdf_path).collect()[:1])

    def test_a_line_sheet_the_engine_never_answered_is_a_failed_read_not_empty_text(self) -> None:
        self.assertEqual([None], [text for _, text in self._read_unanswered().readings])

    def test_a_line_sheet_the_engine_never_answered_counts_as_unread(self) -> None:
        self.assertEqual(1, self._read_unanswered().unread_sheets)

    def test_the_failed_read_names_the_unresponsive_engine(self) -> None:
        self._read_unanswered()
        self.assertIn(str(EngineUnresponsive(SILENCE_LIMIT_SECONDS, 1)), self.stderr.getvalue())

    def test_the_engine_run_is_cleared_after_an_unresponsive_engine(self) -> None:
        self._read_unanswered()
        self.assertFalse(self.run.in_progress())


class AnsweringInferenceManager:
    def __init__(self, error: bool, raw: str) -> None:
        self._error = error
        self._raw = raw

    def generate(self, batch: list) -> list[types.SimpleNamespace]:
        return [types.SimpleNamespace(error=self._error, raw=self._raw) for _ in batch]


class TestEngineReaderCountsUnreadSheets(TestEngineReaderEnvironment):
    def _read_with(self, manager: AnsweringInferenceManager) -> EngineReadings:
        run = EngineRun(self.pdf_path.with_name(RUN_FILE))
        reader = EngineReader(self.pdf_path, {INFERENCE_MANAGER: manager}, run)
        with contextlib.redirect_stderr(io.StringIO()):
            return reader.read(TextLines(self.pdf_path).collect()[:1])

    def test_a_line_sheet_the_engine_answered_with_an_error_counts_as_unread(self) -> None:
        self.assertEqual(1, self._read_with(AnsweringInferenceManager(True, ENGINE_OUTPUT)).unread_sheets)

    def test_a_line_sheet_the_engine_read_as_empty_is_read_not_unread(self) -> None:
        self.assertEqual(0, self._read_with(AnsweringInferenceManager(False, "")).unread_sheets)

    def test_a_line_sheet_the_engine_read_is_not_unread(self) -> None:
        self.assertEqual(0, self._read_with(AnsweringInferenceManager(False, ENGINE_OUTPUT)).unread_sheets)


if __name__ == "__main__":
    unittest.main()
