from __future__ import annotations

from _support import LiveTree

LiveTree.activate()

from _extract.correctionanchors import CorrectionContext
from _extract.correctionrun import CorrectionPass, PassResult, parsed_corrections
from _extract.correctiontext import TrialText

FAMILY = {"family": "paragraphs", "defect_class": "a property of the page, naming no work"}
OUTLINE_TITLES = frozenset({"introduction"})
BODY = (
    "%% p. 1 (file p. 1) %%\n\n"
    "# Introduction\n\n"
    "The opening paragraph states the first claim of the work in full. The second claim follows in the same "
    "paragraph without any break.\n\n"
    "The examination of the second claim runs across the page break until it ends with exam-\n\n"
    "%% p. 2 (file p. 2) %%\n\n"
    "THE WORK\n\n"
    "ination of the evidence, which the reader follows to the end of the sentence.[^1]\n\n"
    "A displaced paragraph that the page prints last of all on its page.\n\n"
    "The closing paragraph of the second page that the page prints after the heading.[^2]\n\n"
    "%% p. 3 (file p. 3) %%\n\n"
    "THE WORK\n\n"
    "3 A note the engine left in the body that the page prints at its foot.\n\n"
    "The third page raises a mark that no note answers yet.[^4]\n\n"
    "**Bold Line Of Text**\n\n"
    "Smith, A. (1990), A Book on the First Topic, London: Press. Jones, B. (1991), Another Book on the Second "
    "Topic, Oxford: Press.\n\n"
    "# Notes\n\n"
    "[^1]: The first note's text as the page prints it at the foot.\n"
    "[^2]: The second note's text, which the trial pairs with the wrong mark."
)
LAYER_LINES = {3: ["A line the trial lost ends with a broken hyph-", "enated word and goes on.",
                   "Another lost line breaks the word exam-", "ination at its end."]}


class FakeLayer:
    def __init__(self, lines: dict[int, list[str]] | None = None, undrawn: frozenset[int] = frozenset()) -> None:
        self._lines = LAYER_LINES if lines is None else lines
        self._undrawn = undrawn

    def lines(self, file_page: int) -> list[str]:
        return self._lines.get(file_page, [])

    def is_drawn(self, file_page: int) -> bool:
        return file_page not in self._undrawn


class CorrectedBody:
    def __init__(self, body: str = BODY, layer: FakeLayer | None = None) -> None:
        self.body = body
        self._layer = layer or FakeLayer()

    def run(self, *corrections: dict) -> PassResult:
        text = TrialText.parsed(self.body)
        context = CorrectionContext(TrialText.parsed(self.body), OUTLINE_TITLES, self._layer)
        return CorrectionPass(context).run(text, parsed_corrections([{**FAMILY, **raw} for raw in corrections]))

    def outcome(self, *corrections: dict) -> str:
        return self.run(*corrections).outcomes[-1]["outcome"]

    def rendered(self, *corrections: dict) -> str:
        return self.run(*corrections).text.rendered()
