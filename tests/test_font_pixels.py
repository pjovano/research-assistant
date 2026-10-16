from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import vault

from _clean.lines import Glyph, TextLine, TextLines
from _clean.ocr import EngineReadings, LineSheet, OcrText
from _clean.pixels import (
    Disagreement,
    GlyphVerdicts,
    LineComparison,
    LineReaders,
    LineSample,
    PixelCache,
    PixelCheck,
    PixelResult,
)
from _clean.sampling import spread
from _clean.textkey import TextLayerCacheEntry, TextLayerDigest, TextLayerKey
from _font_fixtures import LASY9, NO_BBOX
from _layer_pdfs import RemappedTextPdf, StandIn
from _vaults import TempVault, TextPdf

ROMAN = "Roman"


def line(text: str, symbol_at: tuple[int, ...] = (), page: int = 0) -> TextLine:
    fonts = tuple(LASY9 if index in symbol_at else ROMAN for index in range(len(text)))
    return TextLine(page, NO_BBOX, text, fonts)


def disagreements_of(pairs: list[tuple[TextLine, str]]) -> list[Disagreement]:
    verdicts = GlyphVerdicts()
    for text_line, ocr in pairs:
        verdicts.add_all(LineComparison(text_line, ocr).readings())
    return verdicts.disagreements()


class FakeReader:
    def __init__(self, texts: list[str | None]) -> None:
        self.texts = texts
        self.lines: list[TextLine] = []

    def read(self, lines: list[TextLine]) -> list[tuple[TextLine, str | None]]:
        self.lines = lines
        return list(zip(lines, self.texts))


class FakeEngine:
    def __init__(self, unread_sheets: int) -> None:
        self._unread_sheets = unread_sheets
        self.lines: list[TextLine] = []

    def read(self, lines: list[TextLine]) -> EngineReadings:
        self.lines = lines
        return EngineReadings([(text_line, None) for text_line in lines], self._unread_sheets)


class TestLineComparison(unittest.TestCase):
    def test_a_line_the_engine_reads_as_written_agrees_at_every_glyph(self) -> None:
        readings = LineComparison(line("so are A and B."), "so are A and B.").readings()
        self.assertTrue(all(reading.agrees() for reading in readings))

    def test_a_glyph_read_as_another_character_carries_that_reading(self) -> None:
        readings = LineComparison(line("so are ✸A.", symbol_at=(7,)), "so are ◇A.").readings()
        disagreeing = [reading for reading in readings if not reading.agrees()]
        self.assertEqual([(Glyph(LASY9, "✸"), "◇")], [(reading.glyph, reading.read) for reading in disagreeing])

    def test_a_ligature_read_as_its_letters_agrees(self) -> None:
        readings = LineComparison(line("a ﬁne line"), "a fine line").readings()
        self.assertTrue(all(reading.agrees() for reading in readings))

    def test_a_letter_drawn_before_its_spacing_accent_agrees_with_the_composed_reading(self) -> None:
        readings = LineComparison(line("Luka´cs wrote"), "Lukács wrote").readings()
        self.assertTrue(all(reading.agrees() for reading in readings))

    def test_a_letter_drawn_after_its_spacing_accent_agrees_with_the_composed_reading(self) -> None:
        readings = LineComparison(line("Luk´acs wrote"), "Lukács wrote").readings()
        self.assertTrue(all(reading.agrees() for reading in readings))

    def test_a_letter_read_as_accented_without_an_accent_glyph_disagrees(self) -> None:
        readings = LineComparison(line("Lukacs wrote"), "Lukács wrote").readings()
        disagreeing = [reading for reading in readings if not reading.agrees()]
        self.assertEqual([(Glyph(ROMAN, "a"), "á")], [(reading.glyph, reading.read) for reading in disagreeing])

    def test_a_glyph_the_engine_dropped_has_no_reading(self) -> None:
        readings = LineComparison(line("A ✸ B", symbol_at=(2,)), "A B").readings()
        dropped = next(reading for reading in readings if reading.glyph.font == LASY9)
        self.assertIsNone(dropped.read)

    def test_a_prime_and_an_apostrophe_agree(self) -> None:
        readings = LineComparison(line("A′ holds"), "A' holds").readings()
        self.assertTrue(all(reading.agrees() for reading in readings))

    def test_a_small_capital_read_as_a_capital_agrees(self) -> None:
        readings = LineComparison(line("hegel"), "HEGEL").readings()
        self.assertTrue(all(reading.agrees() for reading in readings))

    def test_spaces_do_not_take_part(self) -> None:
        readings = LineComparison(line("a  b"), "ab").readings()
        self.assertTrue(all(reading.agrees() for reading in readings))


class TestGlyphVerdicts(unittest.TestCase):
    def test_a_glyph_read_differently_every_time_is_a_disagreement_with_its_reading(self) -> None:
        pairs = [(line("so are ✸A.", (7,)), "so are ◇A."), (line("✸B too", (0,)), "◇B too")]
        self.assertEqual([Disagreement(LASY9, "✸", 2, 0, "◇")], disagreements_of(pairs))

    def test_a_single_sample_decides_nothing(self) -> None:
        self.assertEqual([], disagreements_of([(line("so are ✸A.", (7,)), "so are ◇A.")]))

    def test_an_occasional_misreading_of_a_common_glyph_is_not_a_disagreement(self) -> None:
        pairs = [(line("v is v and v"), "v is v and v")] * 3 + [(line("v"), "ν")]
        self.assertEqual([], disagreements_of(pairs))

    def test_readings_that_never_settle_leave_the_reading_open(self) -> None:
        pairs = [(line("✸", (0,)), "◇"), (line("✸", (0,)), "□"), (line("✸", (0,)), "◊")]
        self.assertEqual([Disagreement(LASY9, "✸", 3, 0, None)], disagreements_of(pairs))

    def test_a_line_no_reader_could_read_is_skipped(self) -> None:
        verdicts = GlyphVerdicts()
        PixelCheck._compare(verdicts, [(line("✸", (0,)), None), (line("✸", (0,)), "◇")], lambda glyph: True)
        self.assertEqual((1, []), (verdicts.glyph_count(), verdicts.disagreements()))

    def test_only_the_glyphs_a_reader_can_read_are_counted(self) -> None:
        verdicts = GlyphVerdicts()
        PixelCheck._compare(verdicts, [(line("A ✸", (2,)), "A •")], Glyph.is_plain)
        self.assertEqual(1, verdicts.glyph_count())


class TestLineSample(unittest.TestCase):
    def test_every_plain_glyph_is_covered_by_at_most_three_spread_lines(self) -> None:
        lines = [line("common", page=number) for number in range(10)] + [line("✸ rare", (0,), page=10)]
        chosen = LineSample(lines, Glyph.is_plain).chosen()
        self.assertEqual([0, 4, 9, 10], [chosen_line.page for chosen_line in chosen])

    def test_the_symbol_sample_holds_only_lines_with_a_symbol(self) -> None:
        lines = [line("common", page=number) for number in range(10)] + [line("✸ rare", (0,), page=10)]
        self.assertEqual([10], [chosen_line.page for chosen_line in LineSample(lines, Glyph.is_symbol).chosen()])


class TestGlyphClasses(unittest.TestCase):
    def test_latin_letters_digits_and_punctuation_are_plain(self) -> None:
        self.assertTrue(all(Glyph(ROMAN, char).is_plain() for char in "Aé9%'"))

    def test_greek_symbols_and_private_use_are_symbols(self) -> None:
        self.assertTrue(all(Glyph(LASY9, char).is_symbol() for char in "ν□✸\uf022"))

    def test_spread_picks_the_ends_and_the_middle(self) -> None:
        self.assertEqual([0, 5, 10], spread(list(range(11)), 3))


class TestLineSheet(unittest.TestCase):
    def test_the_merged_line_joins_the_sheets_lines_with_a_blank_glyph(self) -> None:
        merged = LineSheet([line("ab"), line("✸", (0,))], []).merged_line()
        self.assertEqual(("ab ✸", (ROMAN, ROMAN, "", LASY9)), (merged.text, merged.fonts))


class TestOcrText(unittest.TestCase):
    def test_tags_are_dropped_and_math_becomes_unicode(self) -> None:
        html_text = "<p>If <i>A</i> is <math>\\square A</math> and <math>\\nu</math>.</p>"
        self.assertEqual("If A is □ A and ν.", OcrText().plain(html_text))

    def test_macros_pylatexenc_lacks_become_unicode(self) -> None:
        self.assertEqual("¬ A ⟨ w ⟩", OcrText().plain("<math>\\neg A \\langle w \\rangle</math>"))

    def test_an_entity_inside_math_is_its_character(self) -> None:
        self.assertEqual("i > 0", OcrText().plain("<math>i &gt; 0</math>"))

    def test_a_bare_less_than_sign_is_not_a_tag(self) -> None:
        self.assertEqual("|x| < 1 and a > b", OcrText().plain("<p>|x| < 1 and a > b</p>"))

    def test_entities_are_unescaped(self) -> None:
        self.assertEqual("a & b", OcrText().plain("<p>a &amp; b</p>"))


class TestPixelCheckOnAPdf(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.pdf_path = TextPdf(self.directory / "plain.pdf").write()
        self.addCleanup(setattr, vault, "SCRATCH_DIR", vault.SCRATCH_DIR)
        vault.SCRATCH_DIR = self.directory / "scratch"

    def test_the_lines_of_the_pdf_carry_their_font_and_text(self) -> None:
        lines = TextLines(self.pdf_path).collect()
        self.assertTrue(lines and all(len(text_line.fonts) == len(text_line.text) for text_line in lines))

    def test_the_result_is_cached_by_the_text_layer_and_reused(self) -> None:
        cache = PixelCache(self.pdf_path)
        reader = FakeReader([None] * 100)
        first = PixelCheck(self.pdf_path, LineReaders(reader, FakeReader([])), cache).result()
        again = PixelCheck(self.pdf_path, LineReaders(FakeReader([]), FakeReader([])), cache).result()
        self.assertEqual((first, True), (again, reader.lines != []))

    def test_a_result_round_trips_through_its_dictionary(self) -> None:
        result = PixelResult(3, 2, [Disagreement(LASY9, "✸", 2, 0, "◇")], 1)
        self.assertEqual(result, PixelResult.from_dict(result.as_dict()))


class TestPixelCheckWithUnreadEngineSheets(unittest.TestCase):
    SYMBOL_LINES = ["so are x and x here", "we see x again"]
    STAND_INS = {"x": StandIn("✸")}

    def setUp(self) -> None:
        self.vault = TempVault().activate()
        self.addCleanup(self.vault.discard)
        self.pdf_path = RemappedTextPdf(self.vault.named("symbols.pdf"), self.SYMBOL_LINES, self.STAND_INS).write()

    def _checked_with(self, engine: FakeEngine) -> PixelResult:
        readers = LineReaders(FakeReader([None] * 100), engine)
        return PixelCheck(self.pdf_path, readers, PixelCache(self.pdf_path)).result()

    def test_a_check_with_unread_engine_sheets_reports_their_count(self) -> None:
        self.assertEqual(1, self._checked_with(FakeEngine(1)).unread_sheets)

    def test_a_check_with_unread_engine_sheets_is_not_cached_so_the_next_check_reads_them(self) -> None:
        self._checked_with(FakeEngine(1))
        engine = FakeEngine(0)
        self._checked_with(engine)
        self.assertNotEqual([], engine.lines)

    def test_a_complete_check_is_cached_so_the_next_check_reads_nothing(self) -> None:
        self._checked_with(FakeEngine(0))
        engine = FakeEngine(0)
        self._checked_with(engine)
        self.assertEqual([], engine.lines)


class TestTextLayerDigest(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault().activate()
        self.addCleanup(self.vault.discard)
        self.pdf_path = TextPdf(self.vault.named("work.pdf")).write()

    def test_a_key_is_its_stamp_followed_by_the_digest(self) -> None:
        digest = TextLayerDigest(self.pdf_path)
        self.assertEqual(["stamp", digest.value()], TextLayerKey(digest, ["stamp"]).value())

    def test_two_keys_over_one_digest_share_its_value(self) -> None:
        digest = TextLayerDigest(self.pdf_path)
        first, second = TextLayerKey(digest, [1]).value(), TextLayerKey(digest, [2]).value()
        self.assertEqual(first[-1], second[-1])

    def test_a_cache_given_a_digest_keys_on_it(self) -> None:
        digest = TextLayerDigest(self.pdf_path)
        cache = PixelCache(self.pdf_path, digest)
        cache.save(PixelResult.empty())
        self.assertEqual(PixelResult.empty(), PixelCache(self.pdf_path).load())


class TestTextLayerCacheEntry(unittest.TestCase):
    LONE_SURROGATE = "\ud800"

    def setUp(self) -> None:
        self.vault = TempVault().activate()
        self.addCleanup(self.vault.discard)
        self.pdf_path = TextPdf(self.vault.named("work.pdf")).write()

    def test_a_payload_carrying_a_lone_surrogate_round_trips(self) -> None:
        entry = TextLayerCacheEntry(self.pdf_path, "entry.json", TextLayerKey(TextLayerDigest(self.pdf_path), []))
        entry.save({"char": self.LONE_SURROGATE})
        self.assertEqual({"char": self.LONE_SURROGATE}, entry.load())


class TestOcrModuleImportsLazily(unittest.TestCase):
    PROBE = "import sys; import _clean.ocr; print('ocrmac' in sys.modules)"

    def test_importing_the_ocr_module_leaves_the_vision_framework_unloaded(self) -> None:
        command = [sys.executable, "-c", self.PROBE]
        printed = subprocess.run(command, capture_output=True, text=True, check=True, env=self._environment()).stdout
        self.assertEqual("False", printed.strip())

    def _environment(self) -> dict[str, str]:
        search_path = os.pathsep.join(entry for entry in sys.path if entry)
        return {**os.environ, "PYTHONPATH": search_path, "PYTHONDONTWRITEBYTECODE": "1"}


if __name__ == "__main__":
    unittest.main()
