from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _extract.arrowstacks import ArrowStack
from _extract.box import Box
from _extract.guardedmath import GuardedMath, LayerFormulas, NotationLog
from _extract.hyphens import Hyphens
from _extract.layer import TextLayer
from _extract.layerhtml import BlockHtml
from _extract.layerlines import rows_of
from _extract.notationguard import AGREED, NotationGuard
from _layer_pdfs import FONT_NAME, GLYPH_WIDTH, RemappedTextPdf, StandIn

FILE_PAGE = 1
WHOLE_PAGE = Box(0.0, 0.0, 1000.0, 1000.0)
GLYPH_UNITS_PER_EM = 1000
OBJECT_SIZE = 11.0
ARROW_SIZE = 8.0
LABEL_SIZE = 6.0
OBJECT_BASELINE = 100.0
UPPER_ARROW_BASELINE = 94.5
LOWER_ARROW_BASELINE = 98.7
OVER_LABEL_BASELINE = 90.5
UNDER_LABEL_BASELINE = 100.3
SUBSCRIPT_BASELINE = 102.4
SOURCE_LEFT = 72.0
ARROW_LEFT = 86.0
LABEL_LEFT = 88.0
TARGET_LEFT = 102.0
STAND_INS = {">": StandIn("→"), "-": StandIn("−"), "p": StandIn("π")}
ARROW = "-->"
OVER_LABEL = "| |"
UNDER_LABEL = "p"
SUBSCRIPT = "0"
STACK_LATEX = "\\begin{matrix}\\xrightarrow{|\\,|} \\\\ \\xrightarrow[\\pi_{0}]{}\\end{matrix}"
ENGINE_LATEX = "X \\xrightarrow{|||} S"
ENGINE_HTML = f'<math display="block">{ENGINE_LATEX}</math>'


@dataclass(frozen=True)
class PlacedRun:
    left: float
    baseline: float
    text: str
    size: float

    def draw(self, page) -> None:
        page.insert_text((self.left, self.baseline), self.text, fontname=FONT_NAME, fontsize=self.size)


class ArrowDiagramPdf(RemappedTextPdf):
    def __init__(self, path: Path, arrow_baselines: tuple[float, ...]) -> None:
        super().__init__(path, [], STAND_INS)
        self._arrow_baselines = arrow_baselines

    def draw(self, page, _lines: list[str]) -> None:
        for run in self._runs():
            run.draw(page)

    def _runs(self) -> list[PlacedRun]:
        arrows = [PlacedRun(ARROW_LEFT, baseline, ARROW, ARROW_SIZE) for baseline in self._arrow_baselines]
        return [PlacedRun(SOURCE_LEFT, OBJECT_BASELINE, "X", OBJECT_SIZE), *arrows,
                PlacedRun(LABEL_LEFT, OVER_LABEL_BASELINE, OVER_LABEL, LABEL_SIZE),
                PlacedRun(LABEL_LEFT, UNDER_LABEL_BASELINE, UNDER_LABEL, LABEL_SIZE),
                PlacedRun(LABEL_LEFT + _advance(LABEL_SIZE), SUBSCRIPT_BASELINE, SUBSCRIPT, LABEL_SIZE),
                PlacedRun(TARGET_LEFT, OBJECT_BASELINE, "S", OBJECT_SIZE)]


def _advance(size: float) -> float:
    return GLYPH_WIDTH / GLYPH_UNITS_PER_EM * size


class ArrowDiagramCase(unittest.TestCase):
    ARROW_BASELINES: tuple[float, ...] = (UPPER_ARROW_BASELINE, LOWER_ARROW_BASELINE)

    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        self.layer = TextLayer(ArrowDiagramPdf(directory / "diagram.pdf", self.ARROW_BASELINES).write())
        self.addCleanup(self.layer.close)
        self.rows = rows_of(self.layer.chars_in(FILE_PAGE, WHOLE_PAGE))

    def layer_formulas(self) -> LayerFormulas:
        return LayerFormulas(BlockHtml(Hyphens(self.layer)).of(self.rows), ArrowStack(self.rows).latex())


class TestArrowsSetOneOverTheOther(ArrowDiagramCase):
    def test_two_arrows_set_one_over_the_other_read_as_a_stack_carrying_their_labels(self) -> None:
        self.assertEqual(STACK_LATEX, ArrowStack(self.rows).latex())

    def test_the_stack_takes_the_place_of_the_one_arrow_the_engine_read(self) -> None:
        checked = GuardedMath(NotationLog()).checked_against(FILE_PAGE, ENGINE_HTML, self.layer_formulas())
        self.assertEqual(f'<math display="block">X {STACK_LATEX} S</math>', checked)

    def test_the_stack_taking_the_place_of_the_engine_arrow_is_logged_as_a_correction(self) -> None:
        log = NotationLog()
        GuardedMath(log).checked_against(FILE_PAGE, ENGINE_HTML, self.layer_formulas())
        self.assertTrue(log.entries()[0].startswith(f"file p. {FILE_PAGE}: corrected {ENGINE_LATEX} to X "))

    def test_a_formula_the_stack_does_not_complete_keeps_the_engine_reading(self) -> None:
        engine_html = '<math display="block">X \\xrightarrow{|||} S + T</math>'
        checked = GuardedMath(NotationLog()).checked_against(FILE_PAGE, engine_html, self.layer_formulas())
        self.assertEqual(engine_html, checked)


class TestOneArrowWithLabelsOnBothSides(ArrowDiagramCase):
    ARROW_BASELINES = (UPPER_ARROW_BASELINE,)

    def test_a_single_arrow_reads_as_no_stack(self) -> None:
        self.assertIsNone(ArrowStack(self.rows).latex())


class TestExtensibleArrowsAgainstTheTextLayer(unittest.TestCase):
    def test_an_extensible_arrow_agrees_with_an_arrow_the_layer_sets_as_shaft_and_head(self) -> None:
        verdict = NotationGuard().checked("A \\xrightarrow[g]{f} B", "A −−→ B f g")
        self.assertEqual(AGREED, verdict.status)

    def test_a_leftward_extensible_arrow_agrees_with_a_head_before_its_shaft(self) -> None:
        verdict = NotationGuard().checked("A \\xleftarrow{f} B", "A ←−− B f")
        self.assertEqual(AGREED, verdict.status)


if __name__ == "__main__":
    unittest.main()
