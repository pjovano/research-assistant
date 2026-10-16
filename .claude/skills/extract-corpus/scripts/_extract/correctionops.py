from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from _pagetext.folio import FOLIO_WORD_PATTERN
from page_marker import PageMarker

from _extract.correctionanchors import (
    Anchors,
    CorrectionContext,
    CorrectionRefused,
    CorrectionStale,
    core_of,
    is_heading,
)
from _extract.correctiontext import MARK_RE, TrialText, Unit, letters_of, normalized

MAX_DROP_WORDS = 15
MIN_RECURRENCES = 2
_DIGITS_RE = re.compile(r"\d+")
_FOLIO_RE = re.compile(FOLIO_WORD_PATTERN, re.IGNORECASE)
_HYPHENATED_END_RE = re.compile(r"(?P<word>[^\W\d_]+)-$")
_OPENING_WORD_RE = re.compile(r"^(?P<word>[^\W\d_]+)(?P<rest>.*)$", re.DOTALL)
_LEADING_MARKER_RE = re.compile(r"^\s*(%%[^%]*%%)")


@dataclass(frozen=True)
class Effect:
    dropped: Counter
    restored: Counter


NO_EFFECT = Effect(Counter(), Counter())


@dataclass(frozen=True)
class Split:
    page: int
    anchor: str

    def apply(self, text: TrialText, _context: CorrectionContext) -> Effect:
        found = Anchors(text).in_body(self.page, self.anchor)
        unit = text.units[found.index]
        if is_heading(unit):
            raise CorrectionRefused("a heading line is never split")
        if found.at_start:
            raise CorrectionStale("the paragraph already opens at the anchor")
        left, right = unit.text[:found.start].rstrip(), unit.text[found.start:]
        pieces = _peeled_marker(left)
        text.units[found.index:found.index + 1] = [unit.with_text(pieces[0])] + \
            [Unit(piece) for piece in pieces[1:]] + [Unit(right)]
        return NO_EFFECT


@dataclass(frozen=True)
class Join:
    page: int
    anchor: str
    dehyphenate: bool = False

    def apply(self, text: TrialText, context: CorrectionContext) -> Effect:
        found = Anchors(text).in_body(self.page, self.anchor)
        if not found.at_start:
            raise CorrectionStale("the anchor already runs on inside its paragraph")
        previous = _joinable_before(text, found.index)
        markers = [text.units[index].text.strip() for index in range(previous + 1, found.index)]
        seam = Seam.between(text.units[previous].text, markers, text.units[found.index].text)
        joined = seam.dehyphenated(context) if self.dehyphenate else seam.joined()
        text.units[previous:found.index + 1] = [text.units[previous].with_text(joined)]
        return NO_EFFECT


@dataclass(frozen=True)
class Seam:
    before: str
    markers: tuple[str, ...]
    after: str

    @classmethod
    def between(cls, before: str, markers: list[str], after: str) -> Seam:
        leading = []
        while _LEADING_MARKER_RE.match(after):
            marker = _LEADING_MARKER_RE.match(after)
            leading.append(marker.group(1))
            after = after[marker.end():]
        return cls(before.rstrip(), tuple(markers + leading), after.lstrip())

    def joined(self) -> str:
        return " ".join([self.before, *self.markers, self.after])

    def dehyphenated(self, context: CorrectionContext) -> str:
        end, opening = _HYPHENATED_END_RE.search(self.before), _OPENING_WORD_RE.match(self.after)
        if end is None or opening is None:
            raise CorrectionRefused("dehyphenating needs a word broken by a hyphen at the seam")
        word = end.group("word") + opening.group("word")
        if not context.knows(word):
            raise CorrectionRefused(f"the work prints {word!r} nowhere else: the hyphen stays")
        closing, _space, remainder = opening.group("rest").partition(" ")
        pieces = [self.before[:end.start()] + word + closing, *self.markers, remainder]
        return " ".join(piece for piece in pieces if piece)


@dataclass(frozen=True)
class Move:
    page: int
    anchor: str
    target_page: int
    target_anchor: str | None = None

    def apply(self, text: TrialText, _context: CorrectionContext) -> Effect:
        anchors = Anchors(text)
        source = anchors.in_body(self.page, self.anchor).index
        unit = text.units[source]
        if unit.carries_a_marker:
            raise CorrectionRefused("a paragraph that crosses a page is never moved")
        if abs(self.page - self.target_page) > 1:
            raise CorrectionRefused("a paragraph moves on its own page or to the page beside it")
        target = self._target(anchors)
        if target == source:
            raise CorrectionRefused("a paragraph is never moved after itself")
        if target == source - 1:
            raise CorrectionStale("the paragraph already follows its target")
        del text.units[source]
        target_after_removal = target if target < source else target - 1
        text.units.insert(target_after_removal + 1, unit.with_separator(""))
        return NO_EFFECT

    def _target(self, anchors: Anchors) -> int:
        if self.target_anchor is None:
            return anchors.opening_marker(self.target_page)
        return anchors.in_body(self.target_page, self.target_anchor).index


@dataclass(frozen=True)
class Drop:
    page: int
    text: str

    def apply(self, text: TrialText, context: CorrectionContext) -> Effect:
        quoted = normalized(self.text)
        self._require_furniture(quoted, context)
        found = Anchors(text).span(self.page, self.text)
        unit = text.units[found.index]
        dropped = unit.text[found.start:found.end]
        kept = (unit.text[:found.start].rstrip() + " " + unit.text[found.end:].lstrip()).strip()
        if kept:
            text.units[found.index] = unit.with_text(kept)
        else:
            del text.units[found.index]
        return Effect(letters_of(dropped), Counter())

    def _require_furniture(self, quoted: str, context: CorrectionContext) -> None:
        if len(quoted.split()) > MAX_DROP_WORDS:
            raise CorrectionRefused(f"furniture runs to at most {MAX_DROP_WORDS} words")
        if MARK_RE.search(self.text) or PageMarker.located(self.text):
            raise CorrectionRefused("a note mark or a page marker is never dropped")
        if not (_FOLIO_RE.fullmatch(quoted) or _recurrences(context.original, quoted) >= MIN_RECURRENCES):
            raise CorrectionRefused("dropped text must be a folio or recur, digits aside, on two or more pages")


ROLE_HEADING = "heading"
ROLE_PARAGRAPH = "paragraph"
ROLE_BOLD = "bold"
ROLES = (ROLE_HEADING, ROLE_PARAGRAPH, ROLE_BOLD)


@dataclass(frozen=True)
class Role:
    page: int
    anchor: str
    to: str
    level: int | None = None

    def apply(self, text: TrialText, context: CorrectionContext) -> Effect:
        found = Anchors(text).in_body(self.page, self.anchor)
        unit = text.units[found.index]
        self._require_single_line(unit)
        core = core_of(unit)
        wanted = self._text_of(core)
        if wanted == unit.text.strip():
            raise CorrectionStale(f"the line is already a {self.to}")
        self._require_outline_kept(unit, core, context)
        text.units[found.index] = unit.with_text(wanted)
        return NO_EFFECT

    def _text_of(self, core: str) -> str:
        if self.to == ROLE_HEADING:
            return "#" * self.level + " " + core
        return f"**{core}**" if self.to == ROLE_BOLD else core

    @staticmethod
    def _require_single_line(unit: Unit) -> None:
        if unit.carries_a_marker or "\n" in unit.text.strip():
            raise CorrectionRefused("only a single line with no page marker changes its role")

    def _require_outline_kept(self, unit: Unit, core: str, context: CorrectionContext) -> None:
        if is_heading(unit) and context.is_outline_title(core):
            raise CorrectionRefused("an outline heading never changes its role or level")
        if self.to == ROLE_HEADING and MARK_RE.search(core):
            raise CorrectionRefused("a heading line never carries a note mark")


def _joinable_before(text: TrialText, index: int) -> int:
    if is_heading(text.units[index]):
        raise CorrectionRefused("a heading line is never joined")
    previous = index - 1
    while previous >= 0 and text.units[previous].is_marker_only:
        previous -= 1
    if previous < 0 or text.units[previous].in_notes or is_heading(text.units[previous]):
        raise CorrectionRefused("a paragraph joins only a paragraph before it")
    return previous


def _peeled_marker(left: str) -> list[str]:
    located = PageMarker.located(left)
    if located and located[-1][1] == len(left) and left[:located[-1][0]].strip():
        return [left[:located[-1][0]].rstrip(), left[located[-1][0]:]]
    return [left]


def _recurrences(original: TrialText, quoted: str) -> int:
    wanted = _digitless(quoted).casefold()
    edges = [_digitless(normalized(piece)).casefold() for unit in original.body_units()
             for piece in _pieces_between_markers(unit.text)]
    return sum(1 for edge in edges if edge.startswith(wanted) or edge.endswith(wanted))


def _pieces_between_markers(text: str) -> list[str]:
    bounds = [0] + [offset for start, end, _marker in PageMarker.located(text) for offset in (start, end)] + [len(text)]
    return [text[bounds[index]:bounds[index + 1]] for index in range(0, len(bounds), 2)]


def _digitless(text: str) -> str:
    return " ".join(_DIGITS_RE.sub(" ", text).split())
