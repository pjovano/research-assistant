from __future__ import annotations

import json
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from dataclasses import replace

import pikepdf
import pymupdf
from _font_fixtures import FIRST_PAGE_INDEX, NoPixelChecks, ScratchDirectory, SilentCommand, symbol_record
from _clean.fontcommands import FontCommands
from _clean.fonts import PdfFonts
from _clean.fontscan import FontScan, ScanInput
from _clean.glyphs import GlyphQuery, Identity, IdentityResolver, IdentityTable
from _clean.pixels import PixelResult
from _clean.identification import GlyphRenders, RenderRequest
from _clean.textlayer import Occurrences, TextLayerOccurrences
from _vaults import TempVault, TextPdf


class TestScanOfAPlainPdf(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)
        self.pdf_path = TextPdf(self.scratch.path / "plain.pdf").write()

    def test_no_code_is_flagged(self) -> None:
        occurrences = Occurrences(TextLayerOccurrences(self.pdf_path).collect())
        scan = FontScan(ScanInput(self.pdf_path, PdfFonts(self.pdf_path).records()), self.scratch.resolver({}))
        report = scan.report(occurrences)
        self.assertEqual((0, [], []), (report["codes_flagged"], report["codes"], report["fonts"]))


INVISIBLE_RENDER_MODE = 3
VISIBLE_RENDER_MODE = 0
TEXT_ORIGIN = (72, 72)
FULL_PAGE = 1.0
HALF_PAGE = 0.5
PIXMAP_SIDE = 10
WHITE = 255


class OcrLayerPdf:
    def __init__(self, path: Path, render_mode: int, image_share: float = 0.0) -> None:
        self._path = path
        self._render_mode = render_mode
        self._image_share = image_share

    def write(self) -> Path:
        with pymupdf.open() as doc:
            page = doc.new_page()
            if self._image_share:
                page.insert_image(self._image_rect(page.rect), pixmap=self._pixmap())
            page.insert_text(TEXT_ORIGIN, "Text a recognizer laid over a page image.", render_mode=self._render_mode)
            doc.save(self._path)
        return self._path

    def _image_rect(self, page_rect: pymupdf.Rect) -> pymupdf.Rect:
        return pymupdf.Rect(0, 0, page_rect.width, page_rect.height * self._image_share)

    @staticmethod
    def _pixmap() -> pymupdf.Pixmap:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, PIXMAP_SIDE, PIXMAP_SIDE), False)
        pixmap.clear_with(WHITE)
        return pixmap


class TestAFontOfAnOcrLayerIsNeverFlagged(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)

    def _ocr_layer(self, render_mode: int, image_share: float = 0.0) -> list[bool]:
        pdf_path = OcrLayerPdf(self.scratch.path / "layer.pdf", render_mode, image_share).write()
        return [record.ocr_layer for record in PdfFonts(pdf_path).records()]

    def test_a_font_drawn_only_invisibly_is_an_ocr_layer(self) -> None:
        self.assertEqual([True], self._ocr_layer(INVISIBLE_RENDER_MODE))

    def test_a_font_drawn_visibly_on_a_page_without_an_image_is_not(self) -> None:
        self.assertEqual([False], self._ocr_layer(VISIBLE_RENDER_MODE))

    def test_a_font_drawn_visibly_only_on_pages_an_image_covers_is_an_ocr_layer(self) -> None:
        self.assertEqual([True], self._ocr_layer(VISIBLE_RENDER_MODE, FULL_PAGE))

    def test_a_font_drawn_beside_an_image_covering_part_of_the_page_is_not(self) -> None:
        self.assertEqual([False], self._ocr_layer(VISIBLE_RENDER_MODE, HALF_PAGE))

    def test_no_code_of_an_ocr_layer_font_is_flagged(self) -> None:
        record = replace(symbol_record(1), ocr_layer=True)
        scan = FontScan(ScanInput(Path("nowhere") / "absent.pdf", [record]), self.scratch.resolver({}))
        self.assertEqual([], scan.flagged())


ACTUAL_TEXT_CONTROL = "\x07"
ACTUAL_TEXT_OPEN = b"/Span <</ActualText <FEFF0007>>> BDC\n"
ACTUAL_TEXT_CLOSE = b"\nEMC\n"


class ActualTextPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self) -> Path:
        with pymupdf.open() as doc:
            doc.new_page().insert_text(TEXT_ORIGIN, "A tab set as marked content.")
            doc.save(self._path)
        with pikepdf.open(self._path, allow_overwriting_input=True) as pdf:
            page = pdf.pages[0]
            page.contents_coalesce()
            wrapped = ACTUAL_TEXT_OPEN + page.Contents.read_bytes() + ACTUAL_TEXT_CLOSE
            page.Contents = pdf.make_stream(wrapped)
            pdf.save(self._path)
        return self._path


class TestACharacterOnlyActualTextSuppliesIsNotAnOccurrence(unittest.TestCase):
    def setUp(self) -> None:
        self.pdf_path = ActualTextPdf(ScratchDirectory(self).path / "actualtext.pdf").write()

    def test_the_text_layer_carries_the_replacement_text(self) -> None:
        with pymupdf.open(self.pdf_path) as doc:
            self.assertIn(ACTUAL_TEXT_CONTROL, doc[FIRST_PAGE_INDEX].get_text())

    def test_no_occurrence_is_reported_for_it(self) -> None:
        found = TextLayerOccurrences(self.pdf_path).collect()
        self.assertEqual([], [occurrence for occurrence in found if occurrence.char == ACTUAL_TEXT_CONTROL])


class TestGlyphRenders(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = ScratchDirectory(self)
        self.pdf_path = TextPdf(self.scratch.path / "plain.pdf").write()
        self.directory = self.scratch.path / "glyphs"
        self.request = RenderRequest(FIRST_PAGE_INDEX, (60.0, 80.0, 300.0, 110.0), "Symbol-01-1")

    def test_the_path_of_a_render_is_named_before_anything_is_saved(self) -> None:
        paths = GlyphRenders(self.pdf_path, self.directory).paths_for([self.request])
        self.assertEqual(([self.directory / "Symbol-01-1.png"], False), (paths, self.directory.exists()))

    def test_saving_writes_the_render_at_its_named_path(self) -> None:
        renders = GlyphRenders(self.pdf_path, self.directory)
        renders.save([self.request])
        self.assertTrue(renders.paths_for([self.request])[0].is_file())


class TestScanConstruction(unittest.TestCase):
    def test_a_scan_over_given_records_opens_no_file_until_queried(self) -> None:
        resolver = IdentityResolver(IdentityTable(ScratchDirectory(self).path / "absent.json"))
        scan = FontScan(ScanInput(Path("nowhere") / "absent.pdf", []), resolver)
        self.assertEqual([], scan.flagged())


class TestIdentityKeys(unittest.TestCase):
    def test_a_glyph_name_that_reads_as_hex_resolves_to_the_entry_learned_for_it(self) -> None:
        path = ScratchDirectory(self).path / "identities.json"
        table = IdentityTable(path)
        table.write(*table.entry_for("LCIRCLEW10", "a112", Identity("", "worker")))
        resolved = IdentityResolver(IdentityTable(path)).resolve(GlyphQuery("LCIRCLEW10", "a112", "02"))
        self.assertEqual("", resolved.unicode)


class TestScanOverTheWholeLibrary(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "VOLUMES_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.scratch = ScratchDirectory(self)
        TextPdf(self.vault.library / "filed.pdf").write()
        (self.vault.library / "filed 2.pdf").write_bytes(b"not a pdf")
        (self.vault.volumes / "volume.pdf").write_bytes(b"not a pdf")

    def test_a_numbered_copy_and_a_volume_are_neither_scanned_nor_reported_as_errors(self) -> None:
        commands = FontCommands(self.scratch.table({}).path, NoPixelChecks())
        printed = SilentCommand(commands.scan).run(all=True, pdf=None, table=None)
        self.assertEqual([], json.loads(printed))


class UnreadPixels:
    UNREAD_SHEETS = 2

    def result(self, pdf_path: Path, digest) -> PixelResult:
        return PixelResult(0, 0, [], self.UNREAD_SHEETS)


class TestScanReportsUnreadEngineSheets(unittest.TestCase):
    PDF_NAME = "work.pdf"

    def setUp(self) -> None:
        self.vault = TempVault("VOLUMES_DIR").activate()
        self.addCleanup(self.vault.discard)
        TextPdf(self.vault.volumes / self.PDF_NAME).write()

    def test_the_scan_reports_how_many_engine_sheets_the_pixel_check_left_unread(self) -> None:
        commands = FontCommands(self.vault.named("no-identities.json"), UnreadPixels())
        printed = json.loads(SilentCommand(commands.scan).run(pdf=self.PDF_NAME, all=False))
        self.assertEqual(UnreadPixels.UNREAD_SHEETS, printed["pixels"]["unread_sheets"])


if __name__ == "__main__":
    unittest.main()
