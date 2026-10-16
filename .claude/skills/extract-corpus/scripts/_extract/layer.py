from __future__ import annotations

import dataclasses
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pymupdf

import accents
from math_fonts import DRAWN_FONT

from _extract.box import EMPTY_BOX, Box
from _extract.drawnshapes import BulletShapes
from _extract.layermarks import AccentedChars, DrawnMarks
from _extract.layerrules import DrawnDashes, DrawnFractions, LayerRule, PageRules, position_on_its_line
from _extract.tracedfonts import ScanTracedFonts

SUPERSCRIPT_FLAG = 1
_BOLD_NAME_RE = re.compile(r"bold|black|heavy|semibold|demi")
_ITALIC_NAME_RE = re.compile(r"italic|oblique|-it\b|it$|slant")
ITALIC_FLAG = 2
BOLD_FLAG = 16
MIN_TEXT_CHARS = 100
MAX_STROKE_THICKNESS = 1.2
MIN_STROKE_LENGTH = 3.0
MAX_STEM_HEIGHT = 20.0
MAX_BAR_WIDTH = 40.0
STEM_ALIGNMENT = 3.0
STEM_WIDTH = 1.2
BAR_MIDDLE_LOW = 0.3
BAR_MIDDLE_HIGH = 0.7
MAX_TEXT_DISTANCE = 20.0
TEXT_ABOVE_STEM = 2.0
TEXT_BELOW_STEM = 6.0
FACING_RIGHT = "right"
FACING_LEFT = "left"
TURNSTILE_CHARS = {
    (FACING_RIGHT, 1, 1): "⊢", (FACING_RIGHT, 1, 2): "⊨", (FACING_RIGHT, 2, 1): "⊩", (FACING_RIGHT, 2, 2): "⊫",
    (FACING_LEFT, 1, 1): "⊣", (FACING_LEFT, 1, 2): "⫤", (FACING_LEFT, 2, 1): "⫣", (FACING_LEFT, 2, 2): "⫥",
}
MAX_STEMS = 2
MAX_DOUBLE_STEM_GAP = 3.0
SNAKE_STEM_CHAR = "∣"
TILDE_CHARS = frozenset("∼~")
MAX_TILDE_GAP = 3.0
SOFT_HYPHEN = "­"
HARD_HYPHEN = "-"
MAX_SHUT_ROOM_SHARE = 0.01
FORMAT_CATEGORY = "Cf"
VISIBLE_TEXT_PAINTS = frozenset({"fill-text", "stroke-text"})
LAID_TEXT_PAINTS = VISIBLE_TEXT_PAINTS | {"ignore-text"}
IMAGE_PAINT = "fill-image"


@dataclass(frozen=True)
class LayerChar:
    char: str
    center: tuple[float, float]
    raised: bool
    size: float
    bold: bool = False
    italic: bool = False
    font: str = ""
    origin: tuple[float, float] = (0.0, 0.0)
    bbox: Box = EMPTY_BOX
    line: int = 0
    in_margin: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "bbox", Box.of(self.bbox))

    @property
    def baseline(self) -> float:
        return self.origin[1]

    @property
    def is_blank(self) -> bool:
        return self.char.isspace()


@dataclass(frozen=True)
class LayerLine:
    text: str
    x0: float
    x1: float
    y0: float
    center: tuple[float, float]

    @property
    def box(self) -> Box:
        return Box(self.x0, self.y0, self.x1, 2 * self.center[1] - self.y0)


class _OpenDocument:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path
        self._document: pymupdf.Document | None = None

    def page(self, file_page: int) -> pymupdf.Page:
        return self.opened()[file_page - 1]

    def page_count(self) -> int:
        return self.opened().page_count

    def is_labelled(self, file_page: int) -> bool:
        page_index = file_page - 1
        return any(label_range["startpage"] <= page_index for label_range in self.opened().get_page_labels())

    def opened(self) -> pymupdf.Document:
        if self._document is None:
            self._document = pymupdf.open(self._pdf_path)
        return self._document

    def close(self) -> None:
        if self._document is not None:
            self._document.close()
            self._document = None


class _BandedChars:
    def __init__(self, chars: list[LayerChar]) -> None:
        self._bands = self._banded(chars)

    def inside(self, box: Box) -> list[LayerChar]:
        return [char for top, bottom, band in self._bands if box.spans_rows(top, bottom)
                for char in band if box.contains(char.center)]

    @staticmethod
    def _banded(chars: list[LayerChar]) -> list[tuple[float, float, list[LayerChar]]]:
        by_line: dict[int, list[LayerChar]] = {}
        for char in chars:
            by_line.setdefault(char.line, []).append(char)
        return [(min(char.center[1] for char in band), max(char.center[1] for char in band), band)
                for band in by_line.values()]


class TextLayer:
    def __init__(self, pdf_path: Path) -> None:
        self._document = _OpenDocument(pdf_path)
        self._raw: dict[int, list[LayerChar]] = {}
        self._pages: dict[int, _BandedChars] = {}
        self._unstacked: dict[int, list[LayerChar]] = {}
        self._lines: dict[int, list[LayerLine]] = {}
        self._rules: dict[int, list[LayerRule]] = {}
        self._texts: dict[int, str] = {}
        self._drawn: dict[int, bool] = {}

    def chars_in(self, file_page: int, bbox: Box) -> list[LayerChar]:
        return self._chars(file_page).inside(bbox)

    def unstacked(self) -> UnstackedLayer:
        return UnstackedLayer(self)

    def unstacked_chars_in(self, file_page: int, bbox: Box) -> list[LayerChar]:
        return _BandedChars(self._unstacked_chars(file_page)).inside(bbox)

    def rules_in(self, file_page: int, bbox: tuple[float, float, float, float]) -> list[LayerRule]:
        return [rule for rule in self._rules_of(file_page) if Box.of(bbox).contains(((rule.x0 + rule.x1) / 2, rule.y))]

    def shapes_in(self, file_page: int, bbox: Box) -> list[Box]:
        shapes = BulletShapes(self._chars(file_page).inside).of(self._document.page(file_page))
        return [shape for shape in shapes if Box.of(bbox).contains(shape.center)]

    def lines_in(self, file_page: int, bbox: Box) -> list[LayerLine]:
        return [line for line in self.lines(file_page) if Box.of(bbox).contains(line.center)]

    def lines(self, file_page: int) -> list[LayerLine]:
        if file_page not in self._lines:
            self._lines[file_page] = _RawLines(self._document.page(file_page), self._dashes(file_page)).all()
        return self._lines[file_page]

    def text(self, file_page: int) -> str:
        if file_page not in self._texts:
            self._texts[file_page] = accents.composed(self._document.page(file_page).get_text())
        return self._texts[file_page]

    def label(self, file_page: int) -> str | None:
        if self._document.is_labelled(file_page):
            return self._document.page(file_page).get_label() or None
        return None

    def has_text(self, file_page: int) -> bool:
        return self.has_text_in(self.text(file_page))

    def is_drawn(self, file_page: int) -> bool:
        if file_page not in self._drawn:
            page = self._document.page(file_page)
            self._drawn[file_page] = _PaintingOrder().shows_text(page) and not ScanTracedFonts().set_most_text_of(page)
        return self._drawn[file_page]

    def has_text_in(self, text: str) -> bool:
        return len(text.strip()) >= MIN_TEXT_CHARS

    def page_count(self) -> int:
        return self._document.page_count()

    def close(self) -> None:
        self._document.close()

    def _chars(self, file_page: int) -> _BandedChars:
        if file_page not in self._pages:
            unstacked = self._unstacked_chars(file_page)
            self._pages[file_page] = _BandedChars(DrawnFractions(unstacked, self._rules_of(file_page)).merged(unstacked))
        return self._pages[file_page]

    def _unstacked_chars(self, file_page: int) -> list[LayerChar]:
        if file_page not in self._unstacked:
            page = self._document.page(file_page)
            raw = self._raw_chars(file_page)
            drawn = _DrawnChars().merged(raw, self._turnstiles(page, raw))
            self._unstacked[file_page] = self._dashes(file_page).merged(drawn)
        return self._unstacked[file_page]

    def _dashes(self, file_page: int) -> DrawnDashes:
        return DrawnDashes(self._raw_chars(file_page), self._rules_of(file_page))

    def _rules_of(self, file_page: int) -> list[LayerRule]:
        if file_page not in self._rules:
            page = self._document.page(file_page)
            turnstiles = self._turnstiles(page, self._raw_chars(file_page))
            self._rules[file_page] = PageRules().of(page, {bar for turnstile in turnstiles for bar in turnstile.bars})
        return self._rules[file_page]

    def _raw_chars(self, file_page: int) -> list[LayerChar]:
        if file_page not in self._raw:
            self._raw[file_page] = _RawChars().of(self._document.page(file_page))
        return self._raw[file_page]

    @staticmethod
    def _turnstiles(page, raw: list[LayerChar]) -> list[_Turnstile]:
        return _DrawnTurnstiles(raw).of(page)


class UnstackedLayer:
    def __init__(self, layer: TextLayer) -> None:
        self._layer = layer

    def chars_in(self, file_page: int, bbox: Box) -> list[LayerChar]:
        return self._layer.unstacked_chars_in(file_page, bbox)


class _PaintingOrder:
    def shows_text(self, page) -> bool:
        text_area = _TextArea()
        images_painted_later: list[pymupdf.Rect] = []
        for kind, bbox in reversed(page.get_bboxlog()):
            painted = pymupdf.Rect(bbox)
            if kind == IMAGE_PAINT:
                images_painted_later.append(painted)
            elif kind in VISIBLE_TEXT_PAINTS and not self._covered(painted, images_painted_later):
                text_area.show(painted)
            elif kind in LAID_TEXT_PAINTS:
                text_area.hide(painted)
        return text_area.is_mostly_shown()

    @staticmethod
    def _covered(painted: pymupdf.Rect, images: list[pymupdf.Rect]) -> bool:
        return any(image.contains(painted) for image in images)


class _TextArea:
    def __init__(self) -> None:
        self._shown = 0.0
        self._hidden = 0.0

    def show(self, painted: pymupdf.Rect) -> None:
        self._shown += painted.get_area()

    def hide(self, painted: pymupdf.Rect) -> None:
        self._hidden += painted.get_area()

    def is_mostly_shown(self) -> bool:
        return self._shown > self._hidden


@dataclass(frozen=True)
class _Turnstile:
    char: str
    stem: tuple[float, float, float, float]
    bars: tuple
    tilde: LayerChar | None = None


class _DrawnTurnstiles:
    def __init__(self, chars: list[LayerChar]) -> None:
        self._inked = [char for char in chars if not char.is_blank and char.font != DRAWN_FONT]

    def of(self, page) -> list[_Turnstile]:
        stems, bars = self._strokes(page)
        found = []
        for group in self._stem_groups(stems):
            turnstile = self._turnstile(group, bars)
            if turnstile is not None and self._sits_in_text(group[0]):
                found.append(turnstile)
        return found

    def _turnstile(self, group: tuple, bars: list) -> _Turnstile | None:
        right = tuple(bar for bar in bars if self._joins(group[-1], bar, bar[0]))
        left = tuple(bar for bar in bars if self._joins(group[0], bar, bar[2]))
        if bool(right) != bool(left):
            facing = FACING_RIGHT if right else FACING_LEFT
            char = TURNSTILE_CHARS.get((facing, len(group), len(right or left)))
            return _Turnstile(char, group[0], right or left) if char else None
        if right or len(group) > 1:
            return None
        tilde = next((char for char in self._inked if self._opens_tilde(group[0], char)), None)
        return _Turnstile(SNAKE_STEM_CHAR, group[0], (), tilde) if tilde is not None else None

    @staticmethod
    def _stem_groups(stems: list) -> list[tuple]:
        groups: list[list[tuple]] = []
        for stem in sorted(stems, key=lambda found: (round(found[1]), found[0])):
            if groups and len(groups[-1]) < MAX_STEMS and _pair_as_double_stem(groups[-1][-1], stem):
                groups[-1].append(stem)
            else:
                groups.append([stem])
        return [tuple(group) for group in groups]

    @staticmethod
    def _opens_tilde(stem: tuple, char: LayerChar) -> bool:
        gap = char.bbox.left - stem[2]
        beside = -STEM_ALIGNMENT <= gap <= MAX_TILDE_GAP and stem[1] <= char.center[1] <= stem[3]
        return char.char in TILDE_CHARS and beside

    def _sits_in_text(self, stem: tuple) -> bool:
        return any(stem[1] - TEXT_ABOVE_STEM <= char.center[1] <= stem[3] + TEXT_BELOW_STEM
                   and abs(char.center[0] - stem[0]) <= MAX_TEXT_DISTANCE for char in self._inked)

    @staticmethod
    def char_of(turnstile: _Turnstile) -> LayerChar:
        left, top, _right, bottom = turnstile.stem
        left = min([left] + [bar[0] for bar in turnstile.bars])
        if turnstile.tilde is not None:
            left = turnstile.tilde.bbox.left - STEM_WIDTH
        box = Box(left, top, left + STEM_WIDTH, bottom)
        return LayerChar(turnstile.char, box.center, False, bottom - top, font=DRAWN_FONT, origin=(left, bottom),
                         bbox=box)

    @staticmethod
    def _joins(stem: tuple, bar: tuple, bar_end: float) -> bool:
        position = (bar[1] - stem[1]) / (stem[3] - stem[1])
        return abs(bar_end - stem[0]) < STEM_ALIGNMENT and BAR_MIDDLE_LOW <= position <= BAR_MIDDLE_HIGH

    @staticmethod
    def _strokes(page) -> tuple[list, list]:
        stems, bars = [], []
        for drawing in page.get_drawings():
            rect = drawing["rect"]
            if rect.width <= MAX_STROKE_THICKNESS and MIN_STROKE_LENGTH < rect.height < MAX_STEM_HEIGHT:
                stems.append(tuple(rect))
            elif rect.height <= MAX_STROKE_THICKNESS and MIN_STROKE_LENGTH < rect.width < MAX_BAR_WIDTH:
                bars.append(tuple(rect))
        return stems, bars


def _pair_as_double_stem(first: tuple, second: tuple) -> bool:
    gap = second[0] - first[2]
    level = abs(first[1] - second[1]) < STEM_ALIGNMENT and abs(first[3] - second[3]) < STEM_ALIGNMENT
    return 0 < gap <= MAX_DOUBLE_STEM_GAP and level


class _DrawnChars:
    def merged(self, chars: list[LayerChar], turnstiles: list) -> list[LayerChar]:
        if not turnstiles or not chars:
            return chars
        merged = list(chars)
        for turnstile in sorted(turnstiles, key=lambda found: found.stem[0], reverse=True):
            self._insert(merged, turnstile, chars)
        return merged

    def _insert(self, merged: list[LayerChar], turnstile: _Turnstile, chars: list[LayerChar]) -> None:
        drawn = _DrawnTurnstiles.char_of(turnstile)
        if turnstile.tilde is not None:
            merged.insert(merged.index(turnstile.tilde), dataclasses.replace(drawn, line=turnstile.tilde.line))
            return
        placed = self._on_a_line(drawn, chars)
        merged.insert(position_on_its_line(placed, merged), placed)

    @staticmethod
    def _on_a_line(drawn: LayerChar, chars: list[LayerChar]) -> LayerChar:
        nearest = min(chars, key=lambda char: (round(abs(char.baseline - drawn.baseline)),
                                               abs(char.center[0] - drawn.center[0])))
        return dataclasses.replace(drawn, line=nearest.line)


class _SoftHyphens:
    def resolved(self, chars: list[LayerChar]) -> list[LayerChar]:
        kept: list[LayerChar] = []
        for position, char in enumerate(chars):
            if char.char != SOFT_HYPHEN:
                kept.append(char)
            elif self._breaks_a_word(chars, position, kept):
                kept.append(dataclasses.replace(char, char=HARD_HYPHEN))
        return kept

    @staticmethod
    def _breaks_a_word(chars: list[LayerChar], position: int, kept: list[LayerChar]) -> bool:
        line = chars[position].line
        ends_its_line = all(later.is_blank for later in chars[position + 1:] if later.line == line)
        follows_a_hyphen = bool(kept) and kept[-1].line == line and kept[-1].char == HARD_HYPHEN
        return ends_its_line and not follows_a_hyphen


class OverlappedSpaces:
    def dropped(self, chars: list[LayerChar]) -> list[LayerChar]:
        room = _SpaceRoom(chars)
        return [char for position, char in enumerate(chars) if not room.is_shut_at(position)]


class _SpaceRoom:
    def __init__(self, chars: list[LayerChar]) -> None:
        self._chars = chars
        self._word_reaches = _word_reaches(chars)
        self._following_ink = _following_ink(chars)

    def is_shut_at(self, position: int) -> bool:
        char = self._chars[position]
        reach = self._word_reaches[position]
        if not char.is_blank or reach is None or char.bbox.width <= 0:
            return False
        following = self._following_ink[position]
        room_end = char.bbox.right if following is None else min(char.bbox.right, following.bbox.left)
        return room_end - reach < MAX_SHUT_ROOM_SHARE * char.size


def _word_reaches(chars: list[LayerChar]) -> list[float | None]:
    reaches: list[float | None] = []
    reach, line = None, None
    for char in chars:
        if char.line != line:
            reach, line = None, char.line
        reaches.append(reach)
        reach = _reach_after(char, reach)
    return reaches


def _reach_after(char: LayerChar, reach: float | None) -> float | None:
    if char.is_blank:
        return None
    if not _draws_ink(char):
        return reach
    return char.bbox.right if reach is None else max(reach, char.bbox.right)


def _following_ink(chars: list[LayerChar]) -> list[LayerChar | None]:
    following: list[LayerChar | None] = []
    upcoming, line = None, None
    for char in reversed(chars):
        if char.line != line:
            upcoming, line = None, char.line
        following.append(upcoming)
        upcoming = char if _draws_ink(char) else upcoming
    return following[::-1]


def _draws_ink(char: LayerChar) -> bool:
    return not char.is_blank and unicodedata.category(char.char[:1]) != FORMAT_CATEGORY


class _RawChars:
    def of(self, page) -> list[LayerChar]:
        chars: list[LayerChar] = []
        for line_number, line in enumerate(_raw_lines(page)):
            for span in line["spans"]:
                chars.extend(self.span_chars(span, line_number))
        placed = DrawnMarks(page).placed(OverlappedSpaces().dropped(chars))
        return _SoftHyphens().resolved(AccentedChars().merged(placed))

    def span_chars(self, span: dict, line_number: int) -> list[LayerChar]:
        flags, font = span["flags"], span["font"].lower()
        bold = bool(flags & BOLD_FLAG) or _BOLD_NAME_RE.search(font) is not None
        italic = bool(flags & ITALIC_FLAG) or _ITALIC_NAME_RE.search(font) is not None
        boxes = [Box.of(char["bbox"]) for char in span["chars"]]
        return [LayerChar(char["c"], box.center, bool(flags & SUPERSCRIPT_FLAG), float(span["size"]),
                          bold, italic, span["font"], tuple(char["origin"]), box, line_number)
                for char, box in zip(span["chars"], boxes)]


class _RawLines:
    def __init__(self, page, dashes: DrawnDashes) -> None:
        self._page = page
        self._drawn_marks = DrawnMarks(page)
        self._dashes = dashes

    def all(self) -> list[LayerLine]:
        lines = [self._line(line, number) for number, line in enumerate(_raw_lines(self._page))]
        return sorted(lines, key=lambda line: (round(line.y0), line.x0))

    def _line(self, line: dict, number: int) -> LayerLine:
        chars = [char for span in line["spans"] for char in _RawChars().span_chars(span, number)]
        marked = AccentedChars().merged(self._drawn_marks.placed(chars))
        text = "".join(char.char for char in self._dashes.merged(marked))
        box = Box.union([Box.of(line["bbox"])] + [dash.bbox for dash in self._dashes.on_line(number)])
        return LayerLine(text, box.left, box.right, box.top, box.center)


def _raw_lines(page) -> list[dict]:
    return [line for block in page.get_text("rawdict")["blocks"] for line in block.get("lines", [])]
