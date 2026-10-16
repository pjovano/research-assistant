from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _extract.layer import LayerLine
from _extract.lists import HangingIndentList
from _extract_fixtures import (
    BBOX, ENTRY_LEFT, FIRST_BASELINE, FLUSH_LEFT, FULL_MEASURE, HANGING_LEFT, LINE_PITCH, NOTE_NUMBER_LEFT,
    NOTE_RUN_ON_LEFT, FakeLayer, LineExtent, layer_line,
)

TWO_DIGIT_NOTE_LEFT = 56.7
COLUMN_ROWS = 6
COLUMN_WIDTH = 90.0
RAGGED_RIGHT_STEP = 5.0
LEFT_COLUMN_LEFT, LEFT_COLUMN_CENTER = 60.0, 100.0
RIGHT_COLUMN_LEFT, RIGHT_COLUMN_CENTER = 300.0, 340.0


def entries(lines: list[LayerLine]) -> list[str]:
    return HangingIndentList(FakeLayer(lines=lines)).entries(1, BBOX)


def column(prefix: str, left: float, center_x: float) -> list[LayerLine]:
    baselines = [FIRST_BASELINE + LINE_PITCH * row for row in range(COLUMN_ROWS)]
    return [LayerLine(f"{prefix}{row}, entry", left, left + COLUMN_WIDTH + RAGGED_RIGHT_STEP * row, baseline,
                      (center_x, baseline)) for row, baseline in enumerate(baselines)]


class TestHangingIndentList(unittest.TestCase):
    def test_two_columns_are_read_left_column_first(self) -> None:
        left = column("L", LEFT_COLUMN_LEFT, LEFT_COLUMN_CENTER)
        right = column("R", RIGHT_COLUMN_LEFT, RIGHT_COLUMN_CENTER)
        expected = ([f"L{row}, entry" for row in range(COLUMN_ROWS)]
                    + [f"R{row}, entry" for row in range(COLUMN_ROWS)])
        self.assertEqual(expected, entries(left + right))

    def test_a_flush_left_justified_list_breaks_where_a_line_ends_short(self) -> None:
        lines = [layer_line("Allison, H. E. (2004), Kant's Transcendental", LineExtent(FLUSH_LEFT, FULL_MEASURE), 0),
                 layer_line("Idealism. New Haven: Yale University Press.", LineExtent(FLUSH_LEFT, 189.4), 1),
                 layer_line("Bolzano, B. (1972), Theory of Science, ed. R.", LineExtent(FLUSH_LEFT, FULL_MEASURE), 2),
                 layer_line("George. Oxford: Oxford University Press.", LineExtent(FLUSH_LEFT, 268.6), 3)]
        self.assertEqual(["Allison, H. E. (2004), Kant's Transcendental Idealism. New Haven: Yale University Press.",
                          "Bolzano, B. (1972), Theory of Science, ed. R. George. Oxford: Oxford University Press."],
                         entries(lines))

    def test_numbered_endnotes_open_at_their_numbers_whatever_their_indent(self) -> None:
        lines = [layer_line("8 Eighth note opens here and", LineExtent(NOTE_NUMBER_LEFT, FULL_MEASURE), 0),
                 layer_line("runs on to a second line.", LineExtent(NOTE_RUN_ON_LEFT, 300.0), 1),
                 layer_line("9 Ninth note sits at the single-digit", LineExtent(NOTE_NUMBER_LEFT, FULL_MEASURE), 2),
                 layer_line("position and continues.", LineExtent(NOTE_RUN_ON_LEFT, 260.0), 3),
                 layer_line("10 Tenth note hangs further left.", LineExtent(TWO_DIGIT_NOTE_LEFT, 330.0), 4)]
        self.assertEqual(["8 Eighth note opens here and runs on to a second line.",
                          "9 Ninth note sits at the single-digit position and continues.",
                          "10 Tenth note hangs further left."], entries(lines))

    def test_an_italic_run_set_on_its_own_line_stays_in_its_entry(self) -> None:
        lines = [layer_line("Allison, H. E. (2004), Kant's Transcendental", LineExtent(FLUSH_LEFT, FULL_MEASURE), 0),
                 layer_line("Idealism. New Haven: Yale University Press.", LineExtent(FLUSH_LEFT, 189.4), 1),
                 layer_line("Faye, E. (2007), Heidegger, l'introduction du", LineExtent(FLUSH_LEFT, FULL_MEASURE), 2),
                 layer_line("nazisme. Paris: Albin Michel.", LineExtent(FLUSH_LEFT, 251.2), 3),
                 layer_line("Forster, M. (1998), Hegel's Idea of a", LineExtent(FLUSH_LEFT, FULL_MEASURE), 4),
                 layer_line("Phenomenology. Chicago: Chicago Press.", LineExtent(FLUSH_LEFT, 118.3), 5),
                 layer_line("Grondin, J. (2003),", LineExtent(FLUSH_LEFT, 126.6), 6),
                 layer_line("Hans-Georg Gadamer: A Biography.", LineExtent(136.9, FULL_MEASURE), 7),
                 layer_line("New Haven: Yale University Press.", LineExtent(FLUSH_LEFT, 243.1), 8)]
        self.assertEqual("Grondin, J. (2003), Hans-Georg Gadamer: A Biography. New Haven: Yale University Press.",
                         entries(lines)[-1])

    def test_an_entry_opening_breaks_a_line_that_filled_the_measure(self) -> None:
        lines = [layer_line("Allison, H. E. (2004), Kant's Transcendental", LineExtent(FLUSH_LEFT, FULL_MEASURE), 0),
                 layer_line("Idealism. New Haven: Yale University Press.", LineExtent(FLUSH_LEFT, 189.4), 1),
                 layer_line("Souche-Dagues, D. (1990), Hegelianisme et dualisme. Paris: Vrin.",
                            LineExtent(FLUSH_LEFT, FULL_MEASURE), 2),
                 layer_line("Spiegelberg, H. (1960), The Phenomenological Movement.",
                            LineExtent(FLUSH_LEFT, FULL_MEASURE), 3),
                 layer_line("2 vols. The Hague: Nijhoff.", LineExtent(FLUSH_LEFT, 164.6), 4)]
        self.assertEqual(["Allison, H. E. (2004), Kant's Transcendental Idealism. New Haven: Yale University Press.",
                          "Souche-Dagues, D. (1990), Hegelianisme et dualisme. Paris: Vrin.",
                          "Spiegelberg, H. (1960), The Phenomenological Movement. 2 vols. The Hague: Nijhoff."],
                         entries(lines))

    def test_a_hyphen_at_a_line_end_is_rejoined(self) -> None:
        lines = [layer_line("Trans-", LineExtent(ENTRY_LEFT, 300.0), 0),
                 layer_line("cendental.", LineExtent(HANGING_LEFT, 200.0), 1)]
        self.assertEqual(["Transcendental."], entries(lines))


if __name__ == "__main__":
    unittest.main()
