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
from _clean.glyphs import METHOD_GLYPH_NAME
from _clean.pixels import Disagreement, PixelResult
from _vaults import PATCHED_DIRS, TEXT_ORIGIN, TempVault

PDF_NAME = "self-named-glyphs.pdf"
BUILTIN_FONT = "helv"
TEXT_LAYER_FONT = "Helvetica"
FONT_SIZE = 12
FIRST_CODE = ord("A")
KAPPA_CODE, ARROW_CODE, SQUARE_CODE, MISNAMED_CODE = "41", "42", "43", "44"
GLYPHS = {
    KAPPA_CODE: ("kappa", "κ"),
    ARROW_CODE: ("arrowsouthwest", "↙"),
    SQUARE_CODE: ("square", "□"),
    MISNAMED_CODE: ("lambda", "μ"),
}
SELF_NAMED_CODES = (KAPPA_CODE, ARROW_CODE, SQUARE_CODE)
MISREAD_AS = "x"
NO_AGREEMENT = 0


class SymbolFontPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> None:
        with pymupdf.open() as doc:
            doc.new_page().insert_text(TEXT_ORIGIN, "ABCD ABCD", fontname=BUILTIN_FONT, fontsize=FONT_SIZE)
            doc.save(self._path)
        self._name_the_glyphs()

    def _name_the_glyphs(self) -> None:
        with pikepdf.open(self._path, allow_overwriting_input=True) as pdf:
            font = next(obj for obj in pdf.objects if _is_the_font(obj))
            names = [pikepdf.Name(f"/{name}") for name, _ in GLYPHS.values()]
            font.Encoding = pikepdf.Dictionary(Differences=pikepdf.Array([FIRST_CODE, *names]))
            font.ToUnicode = pdf.make_stream(self._cmap().encode(STREAM_ENCODING))
            pdf.save(self._path)

    @staticmethod
    def _cmap() -> str:
        return ToUnicodeCMap.from_mappings({code: char for code, (_, char) in GLYPHS.items()}).patched({})


def _is_the_font(obj: object) -> bool:
    return isinstance(obj, pikepdf.Dictionary) and obj.get("/BaseFont") == f"/{TEXT_LAYER_FONT}"


class DisagreeingPixels:
    def result(self, pdf_path: Path, digest) -> PixelResult:
        disagreements = [Disagreement(TEXT_LAYER_FONT, char, PIXEL_SAMPLES, NO_AGREEMENT, MISREAD_AS)
                         for _, char in GLYPHS.values()]
        return PixelResult(len(disagreements), len(disagreements), disagreements)


class TestAPixelFlaggedGlyphWhoseNameNamesTheCharacterItEmits(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*PATCHED_DIRS).activate()
        self.addCleanup(self.vault.discard)
        SymbolFontPdf(self.vault.inbox / PDF_NAME).write()
        self.commands = FontCommands(self.vault.named("identities.json"), DisagreeingPixels())

    def _run(self, command, **arguments) -> dict:
        return json.loads(SilentCommand(command).run(pdf=PDF_NAME, **arguments))

    def _scan_rows(self) -> dict[str, dict]:
        return {row["code"]: row for row in self._run(self.commands.scan, all=False)["codes"]}

    def test_only_the_glyph_whose_name_names_another_character_is_unresolved(self) -> None:
        self.assertEqual(1, self._run(self.commands.scan, all=False)["codes_unresolved"])

    def test_the_scan_settles_it_by_its_glyph_name_as_the_character_it_emits(self) -> None:
        rows = self._scan_rows()
        settled = {code: (rows[code]["identity"], rows[code]["method"]) for code in SELF_NAMED_CODES}
        self.assertEqual({code: (GLYPHS[code][1], METHOD_GLYPH_NAME) for code in SELF_NAMED_CODES}, settled)

    def test_the_scan_keeps_the_pixel_disagreement_on_record(self) -> None:
        rows = self._scan_rows()
        self.assertEqual({("pixels", MISREAD_AS)}, {(rows[code]["source"], rows[code]["reading"])
                                                    for code in SELF_NAMED_CODES})

    def test_a_glyph_whose_name_names_another_character_has_no_identity(self) -> None:
        self.assertIsNone(self._scan_rows()[MISNAMED_CODE]["identity"])

    def test_identify_sends_the_reader_only_the_glyph_whose_name_names_another_character(self) -> None:
        codes = self._run(self.commands.identify)["codes"]
        self.assertEqual([MISNAMED_CODE], [entry["code"] for entry in codes])

    def test_repair_lists_only_the_glyph_whose_name_names_another_character_as_unresolved(self) -> None:
        report = self._run(self.commands.repair, apply=False, partial=False)
        self.assertEqual([MISNAMED_CODE], [row["code"] for row in report["unresolved"]])


if __name__ == "__main__":
    unittest.main()
