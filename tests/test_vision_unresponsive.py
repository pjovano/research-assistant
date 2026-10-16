from __future__ import annotations

import threading
import time
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

import vault

from _clean.cli import Cli
from _clean.ocr import VisionReader, VisionUnresponsive
from _clean.lines import TextLines
from _clean.pixels import LineReaders, PixelCache, PixelCheck, PixelChecks
from _vaults import TempVault, TextPdf

LIMIT_SECONDS = 0.2
GRACE_SECONDS = 2.0
PDF_NAME = "work.pdf"


class RecognizerThatNeverAnswers:
    def __init__(self) -> None:
        self.release = threading.Event()

    def found(self, image) -> list:
        self.release.wait()
        return []


class EngineWithNothingToRead:
    def read(self, lines: list):
        raise AssertionError("a plain PDF sends no line to the engine")


class TestAPixelCheckWhoseVisionReadNeverReturns(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault().activate()
        self.addCleanup(self.vault.discard)
        self.pdf_path = TextPdf(self.vault.named(PDF_NAME)).write()
        self.recognizer = RecognizerThatNeverAnswers()
        self.addCleanup(self.recognizer.release.set)
        self.addCleanup(setattr, vault, "SCRATCH_DIR", vault.SCRATCH_DIR)
        vault.SCRATCH_DIR = self.vault.named("scratch")

    def _check(self) -> PixelCheck:
        reader = VisionReader(self.pdf_path, self.recognizer, LIMIT_SECONDS)
        return PixelCheck(self.pdf_path, LineReaders(reader, EngineWithNothingToRead()), PixelCache(self.pdf_path))

    def test_the_check_fails_within_the_limit_naming_vision(self) -> None:
        started = time.monotonic()
        with self.assertRaisesRegex(VisionUnresponsive, "Apple Vision returned no reading"):
            self._check().result()
        self.assertLess(time.monotonic() - started, LIMIT_SECONDS + GRACE_SECONDS)

    def test_the_failed_check_caches_nothing(self) -> None:
        with self.assertRaises(VisionUnresponsive):
            self._check().result()
        self.assertIsNone(PixelCache(self.pdf_path).load())


class TestTheFontsCommandsReportAnUnresponsiveVisionAsAFailure(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("VOLUMES_DIR").activate()
        self.addCleanup(self.vault.discard)
        TextPdf(self.vault.volumes / PDF_NAME).write()

    def test_scan_exits_with_the_vision_error_instead_of_a_traceback(self) -> None:
        argv = ["clean.py", "fonts", "--table", str(self.vault.named("identities.json")), "scan", PDF_NAME]
        unresponsive = VisionUnresponsive(LIMIT_SECONDS)
        with mock.patch("sys.argv", argv), mock.patch.object(PixelChecks, "result", side_effect=unresponsive), \
                self.assertRaises(SystemExit) as exit_status:
            Cli().run()
        self.assertEqual(str(unresponsive), str(exit_status.exception.code))


class TestAVisionReadThatReturnsWithinTheLimit(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault().activate()
        self.addCleanup(self.vault.discard)
        self.pdf_path = TextPdf(self.vault.named(PDF_NAME)).write()

    def test_its_reading_is_kept(self) -> None:
        first_line = TextLines(self.pdf_path).collect()[:1]
        reader = VisionReader(self.pdf_path, PromptRecognizer(), LIMIT_SECONDS)
        self.assertEqual([(first_line[0], PromptRecognizer.TEXT)], reader.read(first_line))


class PromptRecognizer:
    TEXT = "read at once"

    def found(self, image) -> list:
        return [(self.TEXT, 1.0, (0, 0, 1, 1))]


if __name__ == "__main__":
    unittest.main()
