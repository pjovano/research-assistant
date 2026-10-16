from __future__ import annotations

import contextlib
import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _font_fixtures import LASY9, MisreadFont, MisreadFontPdf, NoPixelChecks, ScratchDirectory, SilentCommand
import pikepdf
import pymupdf
from _clean import fontrepair
from _clean.fontcommands import FontCommands
from _clean.fontrepair import (
    FONT_TEMPORARY_SUFFIX,
    RECORD_KEY,
    STATUS_REPAIRED,
    STATUS_UNRESOLVED,
    FontRepair,
    RepairCheck,
    RepairPlan,
    RepairRecord,
    VerificationFailed,
)
from _clean.fonts import PdfFonts
from _clean.fontscan import FontScan, ScanInput
from _clean.glyphs import METHOD_TABLE
from _clean.identification import FontIdentification, GlyphRenders
from _clean.textlayer import Occurrences, TextLayerOccurrences
from _vaults import TempVault

MISREAD_WORK = "Roe - 2008 - A Logic Set in Dingbats.pdf"
DINGBAT_OF_A50 = "✷"
DINGBAT_OF_A51 = "✸"
DINGBAT_OF_A60 = "❁"
DINGBAT_OF_A61 = "❂"
PRIVATE_USE_READING = ""
LASY9_FAULTY = frozenset({DINGBAT_OF_A50, DINGBAT_OF_A51, DINGBAT_OF_A60, DINGBAT_OF_A61})
LASY9_TEST_IDENTITIES = {f"LASY9|{glyph}": {"unicode": letter, "method": "user"}
                         for glyph, letter in (("a51", "α"), ("a50", "β"), ("a61", "γ"), ("a60", "δ"))}
LASY9_WITH_A61_AT_CODE_01 = MisreadFont("GHIJKL+LASY9", ("a61", "a60"), (DINGBAT_OF_A61, DINGBAT_OF_A60))
LASY9_WITH_A51_AT_CODE_01 = MisreadFont("ABCDEF+LASY9", ("a51", "a50", "a61"),
                                        (DINGBAT_OF_A51, DINGBAT_OF_A50, DINGBAT_OF_A61))
UNIDENTIFIED_FONT = MisreadFont("MNOPQR+MSBM10", (), (PRIVATE_USE_READING,))
MISREAD_FONTS = (LASY9_WITH_A61_AT_CODE_01, LASY9_WITH_A51_AT_CODE_01, UNIDENTIFIED_FONT)
FLAGGED_FONTS = len(MISREAD_FONTS)
FLAGGED_CODES = sum(len(font.targets) for font in MISREAD_FONTS)
LASY9_PAGE_WITH_A51 = MISREAD_FONTS.index(LASY9_WITH_A51_AT_CODE_01)
LASY9_PAGE_WITH_A61_AT_CODE_01 = MISREAD_FONTS.index(LASY9_WITH_A61_AT_CODE_01)


class RejectingRepairCheck:
    def __init__(self, src_path: Path, dest_path: Path, retired: set) -> None:
        self._dest = dest_path

    def run(self) -> None:
        raise VerificationFailed(f"Refusing to keep {self._dest.name}: the faulty characters remain.")


class MisreadFontTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vault = TempVault("INBOX_DIR", "LIBRARY_DIR", "VOLUMES_DIR").activate()
        cls.scratch = ScratchDirectory()
        cls.copy = MisreadFontPdf(MISREAD_FONTS).write(cls.vault.library / MISREAD_WORK)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.scratch.discard()
        cls.vault.discard()


class TestMisreadFontPlan(MisreadFontTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.scan = FontScan(ScanInput(cls.copy, PdfFonts(cls.copy).records()), cls.scratch.resolver({}))
        cls.occurrences = Occurrences(TextLayerOccurrences(cls.copy).collect())

    def test_the_copy_carries_no_repair_record(self) -> None:
        with pikepdf.open(self.copy) as pdf:
            self.assertEqual([], RepairRecord(pdf).entries())

    def test_the_summary_counts_the_flagged_fonts_and_codes(self) -> None:
        summary = self.scan.summary()
        self.assertEqual((FLAGGED_FONTS, FLAGGED_CODES, FLAGGED_CODES),
                         (summary["fonts_flagged"], summary["codes_flagged"], summary["codes_unresolved"]))

    def test_the_plan_is_partial_while_lasy9_is_unresolved(self) -> None:
        self.assertTrue(RepairPlan(self.scan.used(self.occurrences)).is_partial())

    def test_every_flagged_code_is_emitted_by_the_text_layer(self) -> None:
        self.assertEqual(0, self.scan.report(self.occurrences)["codes_unused"])

    def test_a_code_the_text_layer_never_emits_stays_out_of_the_plan(self) -> None:
        self.assertTrue(RepairPlan(self.scan.used(Occurrences([]))).is_empty())

    def test_lasy9_code_01_carries_its_glyph_name(self) -> None:
        rows = self.scan.report(self.occurrences)["codes"]
        row = next(row for row in rows if row["font"] == LASY9 and row["unicode"] == "U+2738")
        self.assertEqual("a51", row["glyph_name"])

    def _identified(self) -> list[dict]:
        directory = self.scratch.path / "glyphs"
        codes = self.scan.used(self.occurrences)
        return FontIdentification(codes, self.occurrences, GlyphRenders(self.copy, directory)).report()

    def test_identify_renders_a_sample_for_each_unresolved_code(self) -> None:
        entries = self._identified()
        self.assertTrue(all(Path(sample["render"]).is_file() for entry in entries for sample in entry["samples"]))

    def test_identify_marks_the_suspect_character_in_its_context(self) -> None:
        entry = next(entry for entry in self._identified() if entry["font"] == LASY9 and entry["unicode"] == "U+2738")
        self.assertIn("⟨U+2738⟩", entry["samples"][0]["context"])

    def test_identify_joins_the_font_objects_that_share_a_glyph(self) -> None:
        entry = next(entry for entry in self._identified() if entry["font"] == LASY9 and entry["unicode"] == "U+2742")
        self.assertEqual(2, len(entry["xrefs"]))


class TestMisreadFontRepaired(MisreadFontTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        commands = FontCommands(cls.scratch.table(LASY9_TEST_IDENTITIES).path, NoPixelChecks())
        cls.result = json.loads(SilentCommand(commands.repair).run(pdf=str(cls.copy), apply=True, partial=True))

    def test_the_repair_reports_repaired(self) -> None:
        self.assertEqual(STATUS_REPAIRED, self.result["status"])

    def test_no_faulty_lasy9_character_remains_in_the_text_layer(self) -> None:
        remaining = [found for found in TextLayerOccurrences(self.copy).collect()
                     if found.font == LASY9 and found.char in LASY9_FAULTY]
        self.assertEqual([], remaining)

    def test_the_learned_character_replaces_the_faulty_one(self) -> None:
        with pymupdf.open(self.copy) as doc:
            self.assertIn("α", doc[LASY9_PAGE_WITH_A51].get_text())

    def test_a_second_lasy9_object_takes_the_character_of_its_own_glyph_at_the_shared_code(self) -> None:
        with pymupdf.open(self.copy) as doc:
            text = doc[LASY9_PAGE_WITH_A61_AT_CODE_01].get_text()
        self.assertEqual((True, False), ("γ" in text, "α" in text))

    def test_the_record_is_written_into_the_document_information(self) -> None:
        with pikepdf.open(self.copy) as pdf:
            record = json.loads(str(pdf.docinfo[RECORD_KEY]))
        self.assertIn({"font": LASY9, "code": "01", "old": "U+2738", "new": "α", "method": METHOD_TABLE}, record)

    def test_no_temporary_file_survives(self) -> None:
        self.assertFalse(self.copy.with_suffix(FONT_TEMPORARY_SUFFIX).exists())


class TestMisreadFontRepairRefused(MisreadFontTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.before = cls.copy.read_bytes()
        commands = FontCommands(cls.scratch.table(LASY9_TEST_IDENTITIES).path, NoPixelChecks())
        cls.result = json.loads(SilentCommand(commands.repair).run(pdf=str(cls.copy), apply=True, partial=False))

    def test_apply_without_partial_reports_the_unresolved_codes(self) -> None:
        self.assertEqual(STATUS_UNRESOLVED, self.result["status"])

    def test_the_refused_copy_stays_byte_identical(self) -> None:
        self.assertEqual(self.before, self.copy.read_bytes())


class TestMisreadFontFailedVerification(MisreadFontTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.before = cls.copy.read_bytes()
        fontrepair.RepairCheck = RejectingRepairCheck
        records = PdfFonts(cls.copy).records()
        scan = FontScan(ScanInput(cls.copy, records), cls.scratch.resolver(LASY9_TEST_IDENTITIES))
        plan = RepairPlan(scan.flagged())
        with contextlib.suppress(VerificationFailed):
            FontRepair(cls.copy, plan, records).run()

    @classmethod
    def tearDownClass(cls) -> None:
        fontrepair.RepairCheck = RepairCheck
        super().tearDownClass()

    def test_the_copy_stays_byte_identical(self) -> None:
        self.assertEqual(self.before, self.copy.read_bytes())

    def test_no_temporary_file_is_left_behind(self) -> None:
        self.assertFalse(self.copy.with_suffix(FONT_TEMPORARY_SUFFIX).exists())


if __name__ == "__main__":
    unittest.main()
