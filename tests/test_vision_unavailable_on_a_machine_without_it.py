from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _clean.cli import Cli
from _clean.lines import TextLines
from _clean.ocr import VisionReader, VisionUnavailable
from _clean.pixels import PixelChecks
from _vaults import TempVault, TextPdf

PDF_NAME = "work.pdf"
WITHOUT_OCRMAC = {"ocrmac": None}


class TestAVisionReadOnAMachineWithoutAppleVision(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault().activate()
        self.addCleanup(self.vault.discard)
        self.pdf_path = TextPdf(self.vault.named(PDF_NAME)).write()

    def test_the_read_fails_naming_apple_vision_as_unavailable(self) -> None:
        first_line = TextLines(self.pdf_path).collect()[:1]
        with mock.patch.dict("sys.modules", WITHOUT_OCRMAC), \
                self.assertRaisesRegex(VisionUnavailable, "Apple Vision is not available"):
            VisionReader(self.pdf_path).read(first_line)


class TestTheFontsCommandsReportAnUnavailableVisionAsJson(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("VOLUMES_DIR").activate()
        self.addCleanup(self.vault.discard)
        TextPdf(self.vault.volumes / PDF_NAME).write()
        argv = ["clean.py", "fonts", "--table", str(self.vault.named("identities.json")), "scan", PDF_NAME]
        printed = io.StringIO()
        with mock.patch("sys.argv", argv), mock.patch.object(PixelChecks, "result", side_effect=VisionUnavailable()), \
                contextlib.redirect_stdout(printed), self.assertRaises(SystemExit) as exit_status:
            Cli().run()
        self.exit_code = exit_status.exception.code
        self.report = json.loads(printed.getvalue())

    def test_the_command_exits_with_status_one(self) -> None:
        self.assertEqual(1, self.exit_code)

    def test_the_report_names_the_status(self) -> None:
        self.assertEqual("vision-unavailable", self.report["status"])

    def test_the_report_names_apple_vision(self) -> None:
        self.assertIn("Apple Vision", self.report["error"])


if __name__ == "__main__":
    unittest.main()
