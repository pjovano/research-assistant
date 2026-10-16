from __future__ import annotations

import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import pikepdf
import pymupdf
from _font_fixtures import PIXEL_SAMPLES, SilentCommand
from _clean.cmap import STREAM_ENCODING, ToUnicodeCMap
from _clean.fontcommands import FontCommands
from _clean.fontrepair import RepairPlan
from _clean.fonts import SUBTYPE_KEY, CidFont, FontRecord, PdfFonts
from _clean.fontscan import FontScan, ScanInput
from _clean.glyphs import REPLACEMENT_CHARACTER, IdentityResolver, IdentityTable
from _clean.pixels import Disagreement, PixelResult
from _clean.textlayer import Occurrences, TextLayerOccurrences
from _vaults import TEXT_ORIGIN, TempVault

PDF_NAME = "unknown-unicode.pdf"
TEXT = "an expression is difficult"
BUILTIN_FONT = "helv"
EMBEDDED_FONT_NAME = "F0"
FONT_SIZE = 12
TYPE0_SUBTYPE = "/Type0"
TYPE0_BASEFONT = "Nimbus Sans Regular"
TEXT_LAYER_FONT = "NimbusSans-Regular"
LETTER_X = "x"
LETTER_S = "s"


def emitted_for(code: str) -> str:
    return chr(int(code, 16))


class UnknownUnicodePdf:
    def __init__(self, path: Path, unknown_letters: tuple[str, ...]) -> None:
        self._path = path
        self._unknown_letters = unknown_letters

    def write(self) -> dict[str, str]:
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_font(fontname=EMBEDDED_FONT_NAME, fontbuffer=pymupdf.Font(BUILTIN_FONT).buffer)
            page.insert_text(TEXT_ORIGIN, TEXT, fontname=EMBEDDED_FONT_NAME, fontsize=FONT_SIZE)
            doc.save(self._path)
        return self._forget_letters()

    def _forget_letters(self) -> dict[str, str]:
        with pikepdf.open(self._path, allow_overwriting_input=True) as pdf:
            font = next(obj for obj in pdf.objects if _is_type0_font(obj))
            cmap = ToUnicodeCMap.from_bytes(font.ToUnicode.read_bytes())
            codes = {letter: _first_code_of(cmap, letter) for letter in self._unknown_letters}
            overrides = {code: REPLACEMENT_CHARACTER for code in codes.values()}
            font.ToUnicode = pdf.make_stream(cmap.patched(overrides).encode(STREAM_ENCODING))
            pdf.save(self._path)
        return codes


def _first_code_of(cmap: ToUnicodeCMap, letter: str) -> str:
    return min(code for code, target in cmap.mappings().items() if target == letter)


def _is_type0_font(obj: object) -> bool:
    return isinstance(obj, pikepdf.Dictionary) and obj.get(SUBTYPE_KEY) == TYPE0_SUBTYPE


class DisagreeingPixels:
    def __init__(self, disagreements: list[Disagreement]) -> None:
        self._disagreements = disagreements

    def result(self, pdf_path: Path, digest) -> PixelResult:
        return PixelResult(len(self._disagreements), len(self._disagreements), self._disagreements)


class ScannedPdf:
    def __init__(self, case: unittest.TestCase) -> None:
        self._vault = TempVault("VOLUMES_DIR").activate()
        case.addCleanup(self._vault.discard)
        self.path = self._vault.volumes / PDF_NAME
        self.codes = UnknownUnicodePdf(self.path, (LETTER_X, LETTER_S)).write()

    def resolver(self, identities: dict[str, str]) -> IdentityResolver:
        entries = {f"{TYPE0_BASEFONT}|{code}": {"unicode": letter, "method": "user"}
                   for code, letter in identities.items()}
        table_path = self._vault.named("identities.json")
        table_path.write_text(json.dumps(entries), encoding="utf-8")
        return IdentityResolver(IdentityTable(table_path))

    def scan_report(self, pixels: DisagreeingPixels) -> dict:
        commands = FontCommands(self._vault.named("no-identities.json"), pixels)
        return json.loads(SilentCommand(commands.scan).run(pdf=PDF_NAME, all=False))

    def plan(self, identities: dict[str, str]) -> RepairPlan:
        occurrences = Occurrences(TextLayerOccurrences(self.path, self._stand_ins()).collect())
        records = PdfFonts(self.path).records()
        scan = FontScan(ScanInput(self.path, records, (), occurrences), self.resolver(identities))
        return RepairPlan(scan.used(occurrences))

    def _stand_ins(self) -> frozenset:
        return frozenset(glyph for record in _type0_records(self.path) for glyph in record.stand_in_glyphs())


def _type0_records(path: Path) -> list[FontRecord]:
    return [record for record in PdfFonts(path).records() if record.cid_font is not None]


class TestTheSyntheticPdf(unittest.TestCase):
    def test_the_text_layer_emits_each_forgotten_code_as_its_own_character(self) -> None:
        scanned = ScannedPdf(self)
        with pymupdf.open(scanned.path) as doc:
            text = doc[0].get_text()
        expected = TEXT.replace(LETTER_X, emitted_for(scanned.codes[LETTER_X]))
        self.assertIn(expected.replace(LETTER_S, emitted_for(scanned.codes[LETTER_S])), text)


class TestScanOfAnIdentityFontWithUnknownUnicode(unittest.TestCase):
    def setUp(self) -> None:
        self.scanned = ScannedPdf(self)
        self.code_x = self.scanned.codes[LETTER_X]
        self.code_s = self.scanned.codes[LETTER_S]
        disagreement = Disagreement(TEXT_LAYER_FONT, emitted_for(self.code_x), PIXEL_SAMPLES, 0, LETTER_X)
        self.report = self.scanned.scan_report(DisagreeingPixels([disagreement]))

    def _row(self, code: str) -> dict:
        return next(row for row in self.report["codes"] if row["code"] == code)

    def test_a_code_mapped_to_the_replacement_character_is_counted_by_the_character_it_emits(self) -> None:
        row = self._row(self.code_s)
        self.assertEqual((f"U+{self.code_s}", TEXT.count(LETTER_S)), (row["unicode"], row["count"]))

    def test_every_used_code_without_an_identity_is_unresolved(self) -> None:
        self.assertEqual((2, 0), (self.report["codes_unresolved"], self.report["codes_unused"]))

    def test_a_pixel_disagreement_on_the_emitted_character_carries_its_reading_to_the_code(self) -> None:
        self.assertEqual(LETTER_X, self._row(self.code_x)["reading"])

    def test_a_disagreement_passes_over_the_code_whose_tounicode_names_the_emitted_character(self) -> None:
        emitted_label = f"U+{self.code_x}"
        emitting = [row["code"] for row in self.report["codes"] if row["unicode"] == emitted_label]
        self.assertEqual([self.code_x], emitting)

    def test_no_emitted_character_is_reported_missing_from_the_tounicode(self) -> None:
        self.assertEqual([], self.report["fonts"])


class TestRepairPlanOfAnIdentityFontWithUnknownUnicode(unittest.TestCase):
    def setUp(self) -> None:
        self.scanned = ScannedPdf(self)
        self.code_x = self.scanned.codes[LETTER_X]
        self.code_s = self.scanned.codes[LETTER_S]

    def _patches(self, identities: dict[str, str]) -> dict[str, str]:
        plan = self.scanned.plan(identities)
        return plan.overrides_for(_type0_records(self.scanned.path)[0])

    def test_a_learned_identity_patches_the_code(self) -> None:
        identities = {self.code_x: LETTER_X, self.code_s: LETTER_S}
        self.assertEqual(identities, self._patches(identities))

    def test_a_code_whose_emitted_character_is_its_identity_is_not_patched(self) -> None:
        patches = self._patches({self.code_x: emitted_for(self.code_x), self.code_s: LETTER_S})
        self.assertEqual({self.code_s: LETTER_S}, patches)


class TestCidFontRecord(unittest.TestCase):
    def _record(self, cid_font: CidFont | None) -> FontRecord:
        cmap = ToUnicodeCMap.from_mappings({"00E4": REPLACEMENT_CHARACTER})
        return FontRecord(1, "Fd160141-Identity-H", frozenset({0}), {}, cmap, None, cid_font)

    def test_the_text_layer_names_a_cid_font_by_its_descendant(self) -> None:
        self.assertEqual("Fd160141", self._record(CidFont("Fd160141", True)).text_layer_name)

    def test_an_identity_encoded_code_without_unicode_is_flagged_as_the_character_it_emits(self) -> None:
        self.assertEqual([("00E4", "ä")], self._record(CidFont("Fd160141", True)).flagged_codes())

    def test_a_pixel_disagreement_on_the_emitted_character_finds_the_code(self) -> None:
        self.assertEqual(["00E4"], self._record(CidFont("Fd160141", True)).codes_for("ä"))

    def test_a_character_a_stand_in_emits_is_traced_to_the_stand_in_alone(self) -> None:
        cmap = ToUnicodeCMap.from_mappings({"00E4": REPLACEMENT_CHARACTER, "0010": "ä"})
        record = FontRecord(1, "Fd160141-Identity-H", frozenset({0}), {}, cmap, None, CidFont("Fd160141", True))
        self.assertEqual(["00E4"], record.codes_for("ä"))

    def test_a_code_under_another_encoding_keeps_the_replacement_character(self) -> None:
        self.assertEqual([("00E4", REPLACEMENT_CHARACTER)], self._record(CidFont("Fd160141", False)).flagged_codes())


if __name__ == "__main__":
    unittest.main()
