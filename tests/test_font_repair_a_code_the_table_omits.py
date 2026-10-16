from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import pymupdf
from _layer_pdfs import RemappedTextPdf, StandIn

from _clean.cmap import ToUnicodeCMap
from _clean.fontrepair import FontRepair, RepairPlan
from _clean.fonts import FontRecord, PdfFonts
from _clean.fontscan import FlaggedCode
from _clean.glyphs import METHOD_TABLE, Identity
from _clean.lines import Glyph

TILDE_CODE = "7E"
EQUALS_CODE = "3D"
FORMULA_LINE = "B = 0 and ~p"
TILDE_READ_AS_EQUALS = {"~": StandIn("=")}
TABLE_NAMING_ONLY_THE_TILDE = (
    "1 begincodespacerange <00> <FF> endcodespacerange\n"
    "1 beginbfchar\n<7E> <003D>\nendbfchar\n"
)


class TestARepairWhoseOldCharacterAnOmittedCodeStillDraws(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.pdf_path = RemappedTextPdf(Path(directory.name) / "omitted.pdf", [FORMULA_LINE],
                                        TILDE_READ_AS_EQUALS).write()
        self.records = PdfFonts(self.pdf_path).records()
        self.plan = RepairPlan([FlaggedCode(self.records[0], TILDE_CODE, "=", Identity("~", METHOD_TABLE))])

    def test_the_font_record_counts_the_omitted_code_as_drawn(self) -> None:
        self.assertIn(EQUALS_CODE, self.records[0].drawn_codes)

    def test_the_character_the_omitted_code_draws_is_not_retired(self) -> None:
        self.assertEqual(set(), self.plan.retired_characters(self.records))

    def test_the_repair_passes_verification_and_restores_the_tilde(self) -> None:
        FontRepair(self.pdf_path, self.plan, self.records).run()
        with pymupdf.open(self.pdf_path) as document:
            self.assertIn(FORMULA_LINE, document[0].get_text())


class TestARepairWhoseOldCharacterNoDrawnCodeEmits(unittest.TestCase):
    def test_the_old_character_is_retired(self) -> None:
        record = FontRecord(1, "ABCDEF+Helvetica", frozenset({0}), {}, ToUnicodeCMap(TABLE_NAMING_ONLY_THE_TILDE),
                            None, None, "WinAnsiEncoding", drawn_codes=frozenset({TILDE_CODE}))
        plan = RepairPlan([FlaggedCode(record, TILDE_CODE, "=", Identity("~", METHOD_TABLE))])
        self.assertEqual({Glyph("Helvetica", "=")}, plan.retired_characters([record]))


if __name__ == "__main__":
    unittest.main()
