from __future__ import annotations

import re
from dataclasses import dataclass

from _extract.elements import Heading, PageMarker, Paragraph, Verbatim
from _extract.footnotes import FootnoteDefinition
from _extract.labels import BracketedNotation
from _extract.sentences import HYPHENATED_END_RE, breaks_off_mid_sentence

HEADING_MARK = "#"
NOTES_HEADING = "Notes"
BLOCK_SEPARATOR = "\n\n"
WORD_SEPARATOR = " "
_BOLD_LINE_RE = re.compile(r"\*\*[^*]+\*\*(?:\[\^[^\]\s]+\])*")
_LOWERCASE_START_RE = re.compile(r"^[a-zà-öø-ÿα-ω]")
_FIRST_WORD_RE = re.compile(r"^(?P<word>\S*)\s*(?P<rest>.*)$", re.DOTALL)


@dataclass(frozen=True)
class Rendered:
    text: str


class NoteWriter:
    def render(self, elements: list, definitions: list[FootnoteDefinition]) -> Rendered:
        blocks = _Blocks()
        for element in elements:
            blocks.add(element)
        blocks.release_captions()
        rendered = blocks.rendered()
        footnotes = self._definitions(definitions)
        text = BLOCK_SEPARATOR.join(rendered + ([footnotes] if footnotes else [])).strip() + "\n"
        return Rendered(text)

    def _definitions(self, definitions: list[FootnoteDefinition]) -> str:
        if not definitions:
            return ""
        listed = "\n".join(BracketedNotation().resolved(definition.rendered()) for definition in definitions)
        return f"{HEADING_MARK} {NOTES_HEADING}{BLOCK_SEPARATOR}{listed}"


class _Blocks:
    def __init__(self) -> None:
        self._brackets = BracketedNotation()
        self._rendered: list[str] = []
        self._open_paragraph = False
        self._held_marker: PageMarker | None = None
        self._last_was_paragraph = False
        self._held_captions: list[Paragraph] = []
        self._adders = {PageMarker: self._hold_marker, Paragraph: self._add_paragraph,
                        Heading: self._add_block, Verbatim: self._add_block}
        self._renderers = {Heading: self._heading_text, Paragraph: self._body_text, Verbatim: self._body_text}

    def rendered(self) -> list[str]:
        return [block for block in self._rendered if block]

    def add(self, element) -> None:
        if _is_caption(element):
            self._held_captions.append(element)
            return
        if not self._runs_on_past_the_captions(element):
            self.release_captions()
        self._adders[type(element)](element)

    def release_captions(self) -> None:
        captions, self._held_captions = self._held_captions, []
        for caption in captions:
            self._add_block(caption)

    def _runs_on_past_the_captions(self, element) -> bool:
        if not isinstance(element, Paragraph):
            return False
        resumes_its_sentence = self._open_paragraph or self._resumes_mid_sentence(element)
        return resumes_its_sentence and self._joins(element)

    def _joins(self, paragraph: Paragraph) -> bool:
        return self._open_paragraph or self._runs_on(paragraph)

    def _hold_marker(self, marker: PageMarker) -> None:
        self._held_marker = marker

    def _add_paragraph(self, paragraph: Paragraph) -> None:
        if self._joins(paragraph):
            self._joined(paragraph)
            return
        self._add_block(paragraph)
        self._leave_open(paragraph)

    def _leave_open(self, paragraph: Paragraph) -> None:
        self._open_paragraph = paragraph.continues
        self._last_was_paragraph = True

    def _add_block(self, element) -> None:
        self._place_marker_before_block()
        self._rendered.append(self._renderers[type(element)](element))
        self._last_was_paragraph = False

    def _runs_on(self, paragraph: Paragraph) -> bool:
        if not self._rendered or not self._last_was_paragraph:
            return False
        if self._held_marker is None:
            return paragraph.resumes and self._breaks_off_mid_sentence()
        if paragraph.resumes:
            return True
        return self._resumes_mid_sentence(paragraph) and self._breaks_off_mid_sentence()

    @staticmethod
    def _resumes_mid_sentence(paragraph: Paragraph) -> bool:
        return paragraph.resumes_mid_sentence or _LOWERCASE_START_RE.match(paragraph.text) is not None

    def _breaks_off_mid_sentence(self) -> bool:
        previous = self._rendered[-1]
        if _BOLD_LINE_RE.fullmatch(previous):
            return False
        return breaks_off_mid_sentence(previous)

    def _joined(self, paragraph: Paragraph) -> None:
        current = self._rendered[-1]
        marker = self._taken_marker()
        text = self._brackets.resolved(paragraph.text)
        if HYPHENATED_END_RE.search(current) is not None:
            self._rendered[-1] = self._joined_at_hyphen(current[:-1], text, marker)
        else:
            self._rendered[-1] = WORD_SEPARATOR.join(part for part in (current, marker, text) if part)
        self._leave_open(paragraph)

    def _joined_at_hyphen(self, head: str, text: str, marker: str) -> str:
        if not marker:
            return f"{head}{text}"
        split = _FIRST_WORD_RE.match(text)
        rejoined_word = f"{head}{split.group('word')}"
        return WORD_SEPARATOR.join(part for part in (rejoined_word, marker, split.group("rest")) if part)

    def _place_marker_before_block(self) -> None:
        marker = self._taken_marker()
        if marker:
            self._rendered.append(marker)
        self._open_paragraph = False

    def _taken_marker(self) -> str:
        if self._held_marker is None:
            return ""
        marker = self._held_marker.comment()
        self._held_marker = None
        return marker

    def _heading_text(self, heading: Heading) -> str:
        return f"{HEADING_MARK * heading.level} {self._brackets.resolved(heading.title)}"

    def _body_text(self, element) -> str:
        return self._brackets.resolved(element.text)


def _is_caption(element) -> bool:
    return isinstance(element, Paragraph) and element.is_caption
