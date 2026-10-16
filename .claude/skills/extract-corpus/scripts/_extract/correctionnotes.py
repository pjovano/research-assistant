from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from _extract.correctionanchors import Anchors, CorrectionContext, CorrectionRefused, CorrectionStale, is_heading
from _extract.correctionops import NO_EFFECT, Effect
from _extract.correctiontext import DEFINITION_RE, DEFINITION_SEPARATOR, TrialText, Unit, letters_of, normalized

MAX_RESTORED_LINES = 40
NEIGHBOURING_PAGES = 1
_PRINTED_KEY_RE = re.compile(r"^(?:\d{1,3}|[*†‡§¶]+)(?:[.)]|\s)")
_LINE_END_HYPHEN_RE = re.compile(r"(?P<word>[^\W\d_]+)-$")
_LINE_OPENING_RE = re.compile(r"^(?P<word>[a-zà-öø-ÿ]+)")


@dataclass(frozen=True)
class ToNote:
    page: int
    anchor: str
    mark: str | None = None

    def apply(self, text: TrialText, _context: CorrectionContext) -> Effect:
        found = Anchors(text).in_body(self.page, self.anchor)
        unit = text.units[found.index]
        if is_heading(unit) or unit.carries_a_marker:
            raise CorrectionRefused("only a paragraph with no page marker becomes a note")
        label = self._label(text, unit)
        del text.units[found.index]
        definition = Unit(f"[^{label}]: {unit.text.strip()}", DEFINITION_SEPARATOR, True)
        text.units.insert(NoteOrder(text).position_for(self.page), definition)
        return NO_EFFECT

    def _label(self, text: TrialText, unit: Unit) -> str:
        defined = {definition.label for definition in text.definitions()}
        if self.mark is None:
            return self._fresh_label(defined, unit)
        if self.mark in defined:
            raise CorrectionStale(f"the mark {self.mark} already has its note")
        if not _is_raised_near(text, self.mark, self.page):
            raise CorrectionRefused(f"no mark [^{self.mark}] is raised on page {self.page} or beside it")
        return self.mark

    @staticmethod
    def _fresh_label(defined: set[str | None], unit: Unit) -> str:
        if not _PRINTED_KEY_RE.match(unit.text.strip()):
            raise CorrectionRefused("an unmarked paragraph becomes a note only if it opens with its printed key")
        numbered = [int(label) for label in defined if label and label.isdigit()]
        return str(max(numbered, default=0) + 1)


@dataclass(frozen=True)
class Pair:
    page: int
    mark: str
    anchor: str

    def apply(self, text: TrialText, _context: CorrectionContext) -> Effect:
        if self.page not in text.mark_pages().get(self.mark, set()):
            raise CorrectionRefused(f"no mark [^{self.mark}] is raised on page {self.page}")
        chosen = Anchors(text).definition(self.anchor).index
        current = text.units[chosen].label
        if current == self.mark:
            raise CorrectionStale(f"the mark {self.mark} already leads to that note")
        holder = next((index for index, unit in enumerate(text.units) if unit.in_notes and unit.label == self.mark),
                      None)
        text.units[chosen] = _relabelled(text.units[chosen], self.mark)
        if holder is not None:
            text.units[holder] = _relabelled(text.units[holder], current)
        return NO_EFFECT


@dataclass(frozen=True)
class Restore:
    page: int
    first_line: int
    last_line: int
    anchor: str | None = None

    def apply(self, text: TrialText, context: CorrectionContext) -> Effect:
        if not context.layer.is_drawn(self.page):
            raise CorrectionRefused(f"page {self.page} draws no text layer to restore from")
        restored = LineJoin(context).joined(self._lines(context))
        if normalized(restored) in normalized(self._page_text(text)):
            raise CorrectionStale("the page already holds the restored text")
        anchors = Anchors(text)
        after = anchors.opening_marker(self.page) if self.anchor is None else anchors.in_body(self.page,
                                                                                               self.anchor).index
        text.units.insert(after + 1, Unit(restored))
        return Effect(Counter(), letters_of(restored))

    def _lines(self, context: CorrectionContext) -> list[str]:
        lines = context.layer.lines(self.page)
        span = self.last_line - self.first_line + 1
        if not 1 <= self.first_line <= self.last_line <= len(lines) or span > MAX_RESTORED_LINES:
            raise CorrectionRefused(f"lines {self.first_line}-{self.last_line} are not a run of at most "
                                    f"{MAX_RESTORED_LINES} of the page's {len(lines)} text-layer lines")
        return lines[self.first_line - 1:self.last_line]

    def _page_text(self, text: TrialText) -> str:
        pages = text.pages()
        return " ".join(unit.text for index, unit in enumerate(text.units) if self.page in pages[index])


class NoteOrder:
    def __init__(self, text: TrialText) -> None:
        self._text = text

    def position_for(self, page: int) -> int:
        mark_pages = self._text.mark_pages()
        key = None
        for index, unit in enumerate(self._text.units):
            if not unit.in_notes:
                continue
            key = min(mark_pages.get(unit.label or "", set()), default=key)
            if key is not None and key > page:
                return index
        return len(self._text.units)


class LineJoin:
    def __init__(self, context: CorrectionContext) -> None:
        self._context = context

    def joined(self, lines: list[str]) -> str:
        text = ""
        for line in (line.strip() for line in lines):
            text = self._seamed(text, line) if text else line
        return text

    def _seamed(self, text: str, line: str) -> str:
        end, opening = _LINE_END_HYPHEN_RE.search(text), _LINE_OPENING_RE.match(line)
        if end is None or opening is None:
            return f"{text} {line}"
        if self._context.knows(end.group("word") + opening.group("word")):
            return text[:-1] + line
        return text + line


def _is_raised_near(text: TrialText, mark: str, page: int) -> bool:
    return any(abs(raised - page) <= NEIGHBOURING_PAGES for raised in text.mark_pages().get(mark, set())
               if raised is not None)


def _relabelled(unit: Unit, label: str) -> Unit:
    return unit.with_text(DEFINITION_RE.sub(f"[^{label}]:", unit.text, count=1))
