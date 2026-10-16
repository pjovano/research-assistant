from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract_fixtures import PrintedWork, keep_everything, page_assembler
from _extract.blocks import HEADING_KIND, Block, PageBlocks
from _extract.layer import TextLayer
from _extract.structure import Paragraph

FONT = "cour"
FONT_SIZE = 9.0
INVISIBLE = 3
CHAR_WIDTH = pymupdf.get_text_length("x", FONT, FONT_SIZE)
MEASURE_CHARS = 58
PAGE_WIDTH = 396.0
PAGE_HEIGHT = 656.0
LEFT = 40.0
RIGHT = LEFT + MEASURE_CHARS * CHAR_WIDTH
FILE_PAGE = 1
ENGINE_LIST_KIND = "ListGroup"
BIBLIOGRAPHY_TITLE = "References"
TITLE_BASELINE = 70.0
FIRST_BASELINE = 100.0
LINE_PITCH = 11.0
LINE_HALF_HEIGHT = 8.0
AUTHOR_LED = 0
REPEATED_AUTHOR = 2
RUN_ON = 4
FILLS = True
ENDS_SHORT = False
REPEATED_AUTHOR_ENTRIES = [
    [(AUTHOR_LED, "Adams, Anna 1969. Zum Wahrheitsproblem. Kant-Studien 60.", FILLS)],
    [(REPEATED_AUTHOR, "1971. Erscheinung bei Kant. Berlin: Gruyter.", ENDS_SHORT)],
    [(REPEATED_AUTHOR, "1974. Kant und das Problem der Dinge an sich. Bonn:", FILLS),
     (RUN_ON, "Bouvier Verlag.", ENDS_SHORT)],
    [(REPEATED_AUTHOR, "1979. Kant und die Dinge. Bonn: Bouvier Verlag.", ENDS_SHORT)],
    [(AUTHOR_LED, "Baker, Bernd 2014. Kant on the Cosmological Argument.", FILLS),
     (RUN_ON, "Imprint 14.12: 1-21.", ENDS_SHORT)]]
ENTRY_BROKEN_MID_SENTENCE = [
    [(AUTHOR_LED, "Logan, Beryl 1998. Hume and Kant on the Deity. Journal", ENDS_SHORT)],
    [(AUTHOR_LED, "for Philosophy of Religion 43.3: 133-48.", ENDS_SHORT)],
    [(AUTHOR_LED, "Longuenesse, Beatrice 2008. Kant and the Capacity to", FILLS),
     (RUN_ON, "Judge. Princeton.", ENDS_SHORT)],
    [(REPEATED_AUTHOR, "2012. Two Uses of I as Subject? Cambridge: Cambridge", FILLS),
     (RUN_ON, "University Press.", ENDS_SHORT)]]


def justified(line: str, measure_chars: int) -> str:
    words = line.split()
    spaces = measure_chars - sum(len(word) for word in words)
    gaps = len(words) - 1
    widths = [spaces // gaps + (1 if gap < spaces % gaps else 0) for gap in range(gaps)]
    return "".join(word + " " * width for word, width in zip(words, widths + [0]))


class RecognizedBibliographyScanPdf:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, entries: list[list[tuple[int, str, bool]]]) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            self._print(page, (LEFT, TITLE_BASELINE), BIBLIOGRAPHY_TITLE)
            for row, (indent_chars, text, fills) in enumerate(printed_lines(entries)):
                printed = justified(text, MEASURE_CHARS - indent_chars) if fills else text
                self._print(page, (LEFT + indent_chars * CHAR_WIDTH, FIRST_BASELINE + row * LINE_PITCH), printed)
            document.save(self._path)
        return self._path

    @staticmethod
    def _print(page, origin: tuple[float, float], text: str) -> None:
        page.insert_text(origin, text, fontsize=FONT_SIZE, fontname=FONT, render_mode=INVISIBLE)


def printed_lines(entries: list[list[tuple[int, str, bool]]]) -> list[tuple[int, str, bool]]:
    return [line for entry in entries for line in entry]


def entry_texts(entries: list[list[tuple[int, str, bool]]]) -> list[str]:
    return [" ".join(text for _indent, text, _fills in entry) for entry in entries]


def engine_block(kind: str, html_text: str, baselines: tuple[float, float]) -> Block:
    top, bottom = baselines
    box = (LEFT, top - LINE_HALF_HEIGHT, RIGHT, bottom + LINE_HALF_HEIGHT / 2)
    return Block(FILE_PAGE, kind, html_text, box, {}, f"/page/{FILE_PAGE}/{kind}/{top}")


def engine_reading(paragraphs: list[str], line_count: int) -> list[Block]:
    last_baseline = FIRST_BASELINE + (line_count - 1) * LINE_PITCH
    entries_html = "\n".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
    return [engine_block(HEADING_KIND, f"<h2>{BIBLIOGRAPHY_TITLE}</h2>", (TITLE_BASELINE, TITLE_BASELINE)),
            engine_block(ENGINE_LIST_KIND, entries_html, (FIRST_BASELINE, last_baseline))]


class TestEntryListsTheEngineReadsFromPixelsJoiningTwoEntriesInOneParagraph(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self._pdf = RecognizedBibliographyScanPdf(Path(directory.name) / "scan.pdf")

    def _written_lines(self, printed: list[list[tuple[int, str, bool]]], engine_paragraphs: list[str]) -> list[str]:
        layer = TextLayer(self._pdf.write(printed))
        self.addCleanup(layer.close)
        assembler = page_assembler(layer, keep_everything(), PrintedWork(pixel_pages=frozenset({FILE_PAGE})))
        blocks = engine_reading(engine_paragraphs, len(printed_lines(printed)))
        result = assembler.assemble(PageBlocks(FILE_PAGE, blocks), [], 1)
        paragraphs = [element.text for element in result.elements if isinstance(element, Paragraph)]
        return [line for paragraph in paragraphs for line in paragraph.split("\n")]

    def test_an_entry_the_text_layer_opens_after_a_full_stop_opens_a_line_of_its_own(self) -> None:
        entries = entry_texts(REPEATED_AUTHOR_ENTRIES)
        engine_paragraphs = [f"{entries[0]} {entries[1]}"] + entries[2:]
        self.assertEqual(entries, self._written_lines(REPEATED_AUTHOR_ENTRIES, engine_paragraphs))

    def test_an_entry_the_text_layer_opens_after_a_word_ending_no_sentence_runs_on(self) -> None:
        entries = entry_texts(ENTRY_BROKEN_MID_SENTENCE)
        engine_paragraphs = [f"{entries[0]} {entries[1]}"] + entries[2:]
        self.assertEqual(engine_paragraphs, self._written_lines(ENTRY_BROKEN_MID_SENTENCE, engine_paragraphs))


if __name__ == "__main__":
    unittest.main()
