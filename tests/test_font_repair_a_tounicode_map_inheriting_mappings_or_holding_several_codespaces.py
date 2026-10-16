from __future__ import annotations

import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _font_fixtures import MisreadFont, MisreadFontPdf, ScratchDirectory
import pikepdf
from _clean.cmap import ToUnicodeCMap
from _clean.fontrepair import FontRepair, KeptMappingsCheck, RepairPlan, VerificationFailed
from _clean.fonts import PdfFonts
from _clean.fontscan import FontScan, ScanInput

PARENT_MAP_LINE = "/Adobe-Japan1-UCS2 usecmap"
LOW_CODESPACE = "1 begincodespacerange <00> <7F> endcodespacerange"
HIGH_CODESPACE = "1 begincodespacerange <80> <FF> endcodespacerange"
DINGBAT_OF_A51 = "✸"
FONT = MisreadFont("ABCDEF+LASY9", ("a51", "b"), (DINGBAT_OF_A51, "b"))
IDENTITIES = {"LASY9|a51": {"unicode": "α", "method": "user"}}
PATCH = {"01": "α"}


def tounicode(rows: str, inherited: str = f"{PARENT_MAP_LINE}\n{LOW_CODESPACE}\n{HIGH_CODESPACE}\n") -> str:
    return f"{inherited}2 beginbfchar\n{rows}endbfchar\n"


ORIGINAL_ROWS = "<01> <2738>\n<02> <0062>\n"


class InheritingMapTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)
        self.pdf = MisreadFontPdf((FONT,)).write(self.scratch.path / "inheriting.pdf")
        self.write_tounicode(self.pdf, tounicode(ORIGINAL_ROWS))
        self.records = PdfFonts(self.pdf).records()
        scan = FontScan(ScanInput(self.pdf, self.records), self.scratch.resolver(IDENTITIES))
        self.plan = RepairPlan(scan.flagged())

    @staticmethod
    def write_tounicode(path: Path, text: str) -> None:
        with pikepdf.open(path, allow_overwriting_input=True) as pdf:
            pdf.pages[0].Resources.Font.S.ToUnicode = pdf.make_stream(text.encode("ascii"))
            pdf.save(path)

    @staticmethod
    def stored_tounicode(path: Path) -> str:
        with pikepdf.open(path) as pdf:
            return pdf.pages[0].Resources.Font.S.ToUnicode.read_bytes().decode("ascii")


class TestARepairedMapKeepsWhatItInherits(InheritingMapTestCase):
    def setUp(self) -> None:
        super().setUp()
        FontRepair(self.pdf, self.plan, self.records).run()
        self.repaired = self.stored_tounicode(self.pdf)

    def test_the_usecmap_line_is_kept(self) -> None:
        self.assertIn(PARENT_MAP_LINE, self.repaired)

    def test_every_codespace_block_is_kept(self) -> None:
        self.assertEqual((True, True), (LOW_CODESPACE in self.repaired, HIGH_CODESPACE in self.repaired))


class TestTheCheckRefusesARepairThatChangedAnUnpatchedCode(unittest.TestCase):
    def check(self, repaired_tounicode: str) -> None:
        KeptMappingsCheck(ToUnicodeCMap(tounicode(ORIGINAL_ROWS)), PATCH).run(ToUnicodeCMap(repaired_tounicode))

    def test_an_unpatched_code_mapped_to_another_character_fails(self) -> None:
        with self.assertRaises(VerificationFailed):
            self.check(tounicode("<01> <03B1>\n<02> <0063>\n"))

    def test_a_dropped_usecmap_line_fails(self) -> None:
        with self.assertRaises(VerificationFailed):
            self.check(tounicode("<01> <03B1>\n<02> <0062>\n", f"{LOW_CODESPACE}\n{HIGH_CODESPACE}\n"))

    def test_a_dropped_codespace_block_fails(self) -> None:
        with self.assertRaises(VerificationFailed):
            self.check(tounicode("<01> <03B1>\n<02> <0062>\n", f"{PARENT_MAP_LINE}\n{LOW_CODESPACE}\n"))

    def test_a_repair_changing_only_the_patched_code_passes(self) -> None:
        self.check(tounicode("<01> <03B1>\n<02> <0062>\n"))


if __name__ == "__main__":
    unittest.main()
