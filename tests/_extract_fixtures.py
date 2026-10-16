from __future__ import annotations

from dataclasses import dataclass, field

from _support import LiveTree

LiveTree.activate()

from math_fonts import DRAWN_FONT
from _extract.blocks import Block
from _extract.box import Box
from _extract.footnotes import FootnoteLabels, FootnoteLog, FootnotePairer
from _extract.layer import LayerChar, LayerLine
from _extract.layerhtml import BlockHtml
from _extract.policy import SectionPolicy
from _extract.spans import ExcludedSpan, ExcludedSpans, PagePlace
from _extract.structure import PageAssembler, WorkInputs

BBOX = (0.0, 0.0, 100.0, 100.0)
BODY_SIZE = 10.0
ADVANCE = 6.0
DESCENT_SHARE = 0.2
MIN_MEASURED_CHARS = 100
FIRST_BASELINE = 100.0
LINE_PITCH = 12.0
PAGE_CENTER_X = 200.0
FULL_MEASURE = 370.0
FLUSH_LEFT = 46.8
ENTRY_LEFT = 72.0
HANGING_LEFT = 90.0
NOTE_NUMBER_LEFT = 60.7
NOTE_RUN_ON_LEFT = 70.6
BODY_BOX = (0.0, 0.0, 100.0, 80.0)
FOOT_BOX = (0.0, 90.0, 100.0, 100.0)
BELOW_BODY = 85.0
PROSE = ("The general point of the surveyor's report on the river crossing is that any such plan already "
         "assumes a fixed relation between the road and the two banks of the river, and so it cannot be "
         "the starting point of a careful study of the slow old crossing and all of its daily traffic. ")


class FakeFonts:
    @staticmethod
    def is_math(font: str) -> bool:
        return font == DRAWN_FONT or font.upper().startswith(("CM", "MATH"))

    @staticmethod
    def notation_characters() -> set:
        return set()


class FakeHyphens:
    def __init__(self, kept: set[str] | None = None) -> None:
        self._kept = kept or set()

    def keeps_hyphen(self, before: str, after: str) -> bool:
        return any(word in f"{before}{after}".casefold() for word in self._kept)


class FakeLayer:
    def __init__(self, chars: list[LayerChar] | None = None, text: str = "", lines: list | None = None) -> None:
        self._chars = chars or []
        self._text = text
        self._lines = lines or []
        self._rules: list = []

    def chars_in(self, file_page: int, bbox) -> list[LayerChar]:
        return list(self._chars)

    def rules_in(self, file_page: int, bbox) -> list:
        return list(self._rules)

    def shapes_in(self, file_page: int, bbox) -> list:
        return []

    def lines_in(self, file_page: int, bbox) -> list:
        return list(self._lines)

    def lines(self, file_page: int) -> list:
        return list(self._lines)

    def text(self, file_page: int) -> str:
        return self._text

    def has_text_in(self, text: str) -> bool:
        return len(text.strip()) >= MIN_MEASURED_CHARS

    def label(self, file_page: int) -> str | None:
        return None

    def is_drawn(self, file_page: int) -> bool:
        return True

    def unstacked(self) -> FakeLayer:
        return self


class BoxedLayer(FakeLayer):
    def chars_in(self, file_page: int, bbox) -> list[LayerChar]:
        return [char for char in self._chars if Box.of(bbox).contains(char.center)]


@dataclass(frozen=True)
class BlockPlace:
    box: tuple
    index: int
    file_page: int = 1

    def block(self, kind: str, html: str) -> Block:
        return Block(self.file_page, kind, html, self.box, {}, f"/page/{self.file_page}/{kind}/{self.index}")


def keep_everything() -> SectionPolicy:
    return SectionPolicy.keeping_everything()


def excluding(start: PagePlace, resume: PagePlace) -> SectionPolicy:
    return SectionPolicy(ExcludedSpans([ExcludedSpan(start, resume)]))


@dataclass(frozen=True)
class PrintedWork:
    work_title: str = ""
    folios: dict[int, str] = field(default_factory=dict)
    pixel_pages: frozenset[int] = frozenset()
    furniture: list[str] = field(default_factory=list)


def page_assembler(layer, policy: SectionPolicy, printed: PrintedWork = PrintedWork()) -> PageAssembler:
    block_html = BlockHtml(FakeHyphens())
    work = WorkInputs(layer, block_html, FakeFonts(), printed.work_title, folios=printed.folios or {},
                      pixel_pages=printed.pixel_pages, furniture=printed.furniture or [])
    return PageAssembler(work, policy, FootnotePairer(FootnoteLabels(), FootnoteLog()))


@dataclass(frozen=True)
class RunSetting:
    left: float
    baseline: float
    line: int
    font: str = ""
    size: float = BODY_SIZE


def positioned(text: str, setting: RunSetting) -> list[LayerChar]:
    placed = []
    size, baseline = setting.size, setting.baseline
    for index, char in enumerate(text):
        x = setting.left + index * ADVANCE
        box = (x, baseline - size, x + ADVANCE, baseline + size * DESCENT_SHARE)
        placed.append(LayerChar(char, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), False, size,
                                font=setting.font, origin=(x, baseline), bbox=box, line=setting.line))
    return placed


@dataclass(frozen=True)
class LineExtent:
    left: float
    right: float


def layer_line(text: str, extent: LineExtent, row: int) -> LayerLine:
    baseline = FIRST_BASELINE + row * LINE_PITCH
    return LayerLine(text, extent.left, extent.right, baseline, (PAGE_CENTER_X, baseline))
