from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.layer import TextLayer
from _extract.lists import HangingIndentList

FONT = "cour"
FONT_SIZE = 9.0
LINE_PITCH = 11.0
FIRST_BASELINE = 100.0
MARGIN = 63.0
FIRST_LINE_INDENT = 9.5
OPENING_LEFT = MARGIN + FIRST_LINE_INDENT
NARROW_NOTE = "47. Kritik, A50/B47."
WORD_GAP_SHORT_OF_A_GUTTER = 8.9
TAB_STOP = OPENING_LEFT + pymupdf.get_text_length(NARROW_NOTE, fontname=FONT, fontsize=FONT_SIZE) \
    + WORD_GAP_SHORT_OF_A_GUTTER
WHOLE_PAGE = Box(0.0, 0.0, 480.0, 660.0)
ROWS = [[["44. Ibid., pp. 408-9."]],
        [["45. Ibid., p. 12."]],
        [["46. A long note naming a book and its publisher runs to the", "end of the measure, 1956), p. 17."]],
        [[NARROW_NOTE], ["48. Ibid., A50/B47; cf. A147."]],
        [["49. Ibid., A104."], ["50. Ibid., B3."]],
        [["51. Ibid., Bxiv."], ["52. Ibid., A369."]],
        [["53. Ibid., B136."]],
        [["54. See a translated book whose title runs across the whole",
          "measure and wraps (The Hague: Nijhoff, 1983), p. 62."]],
        [["55. See another translated book whose title is also long and",
          "wraps twice, trans. by its translator (Evanston, IL:", "Northwestern University Press, 1970), p. 30."]],
        [["56. A last note that wraps onto a second line of the list,",
          "trans. by its translator (The Hague: Nijhoff, 1969), p. 26."]]]
EXPECTED = [" ".join(note) for row in ROWS for note in row]


class NarrowlyParallelNotesPdf:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._baseline = FIRST_BASELINE

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=WHOLE_PAGE.right, height=WHOLE_PAGE.bottom)
            for row in ROWS:
                self._row(page, row)
            document.save(self._path)
        return self._path

    def _row(self, page, notes: list[list[str]]) -> None:
        for opening_left, note in zip((OPENING_LEFT, TAB_STOP), notes):
            for position, line in enumerate(note):
                left = opening_left if position == 0 else MARGIN
                origin = (left, self._baseline + position * LINE_PITCH)
                page.insert_text(origin, line, fontsize=FONT_SIZE, fontname=FONT)
        self._baseline += LINE_PITCH * max(len(note) for note in notes)


class TestEntryListsSettingASecondNoteWithinAWordGapOfTheFirst(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.layer = TextLayer(NarrowlyParallelNotesPdf(Path(directory.name) / "notes.pdf").write())
        self.addCleanup(self.layer.close)

    def test_each_note_is_one_whole_entry_in_reading_order(self) -> None:
        entries = HangingIndentList(self.layer).boxed_entries(1, [WHOLE_PAGE])
        self.assertEqual(EXPECTED, [" ".join(entry.text.split()) for entry in entries])


if __name__ == "__main__":
    unittest.main()
