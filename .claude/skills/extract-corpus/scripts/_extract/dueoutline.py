from __future__ import annotations

import dataclasses

from _extract.blocks import FOOTNOTE_KIND, HEADING_KIND, Block
from _extract.elements import Heading, Paragraph
from _extract.headings import BARE_LABEL_RE, TitleParts, prints_the_opening_of, shape_of
from _extract.outline import Heading as OutlineHeading
from _extract.pagework import PageWork
from _extract.policy import SectionOpening
from _extract.runintitles import RunInTitle
from _extract.spans import PagePlace
from _extract.statements import StatementLabel

class DueOutline:
    def __init__(self, work: PageWork, due: list[OutlineHeading], heading_texts: list[str]) -> None:
        self._texts, self._output, self._entries = work.texts, work.output, work.entries
        self._policy, self._match = work.policy, work.match
        self._content, self._due = work.texts.blocks, due
        self._labels = StatementLabel()
        self._printed_whole = self._titles_printed_whole()
        self._pending = [heading for heading in due if self._printed_among(heading, heading_texts)]
        self._top = [heading for heading in due if heading not in self._pending]
        self._run_in_openings = {heading: index for heading in self._top
                                 if (index := self._run_in_opening(heading)) is not None}
        self._printed_openings = {heading: index for heading in self._top
                                  if (index := self._printed_opening(heading)) is not None}
        self._title_parts = sorted(self._blocks_printing_a_title_part())
        self._consumed: set[int] = self._blocks_printing_only_a_title() | set(self._title_parts)

    def consumes(self, index: int) -> bool:
        return index in self._consumed

    def open_due_above(self, block: Block, index: int) -> None:
        while self._next_top_opens_above(block, index):
            self._entries.flush()
            heading = self._top.pop(0)
            self._open_outline(heading, self.merge_partner(index), _destination_of(heading))

    def open_the_rest(self) -> None:
        for heading in sorted(self._top + self._pending, key=self._due.index):
            self._open_outline(heading, None, _destination_of(heading))

    def pending_matching(self, text: str) -> OutlineHeading | None:
        return next((heading for heading in self._pending if self._anchors(text, heading)), None)

    def pass_over(self, text: str) -> None:
        matched = self.pending_matching(text)
        if matched is not None:
            self._pending.remove(matched)
            self._policy.opens(SectionOpening(matched.level, matched.title))

    def open_matched(self, index: int, block: Block, matched: OutlineHeading) -> None:
        self._pending.remove(matched)
        self._consumed |= self._title_lines_after(index, matched.title)
        self._output.raise_marks(self._texts.labels_printed_in(index))
        self._open_outline(matched, self.merge_partner(index + 1), PagePlace.of_block(block))
        self._output.emit(self._lines_below_the_title(index, matched.title.strip()))

    def without_the_title_opening(self, index: int, elements: list) -> list:
        title = self._title_run_into(index)
        if title is None or not elements or not isinstance(elements[0], Paragraph):
            return elements
        remainder = self._past_the_run_in_title(elements[0].text, title)
        if remainder == elements[0].text:
            return elements
        return ([dataclasses.replace(elements[0], text=remainder)] if remainder else []) + elements[1:]

    def merge_partner(self, start: int) -> int | None:
        for index in range(start, len(self._content)):
            block = self._content[index]
            if block.kind == HEADING_KIND:
                return None if self._pending_matches(block.plain_text) else index
            if block.kind != FOOTNOTE_KIND:
                return None
        return None

    def merged_with_partner(self, title: str, partner: int | None) -> str:
        if partner is None:
            return title
        self._consumed.add(partner)
        printed = self._content[partner].plain_text
        return printed if _opens_with(printed, title.strip()) else f"{title}: {printed}"

    def _open_outline(self, heading: OutlineHeading, partner: int | None, place: PagePlace) -> None:
        absorbed = partner if BARE_LABEL_RE.match(heading.title.strip()) else None
        self._output.raise_marks(self._taken_title_part_marks())
        title = self.merged_with_partner(heading.title, absorbed)
        self._output.open(Heading(heading.level, title, heading.file_page, None), self._policy.resumed(place))

    def _taken_title_part_marks(self) -> list[str]:
        parts, self._title_parts = self._title_parts, []
        return [mark for index in parts for mark in self._texts.marks_printed_in(index)]

    def _next_top_opens_above(self, block: Block, index: int) -> bool:
        if not self._top or self._waits_for_pending(self._top[0]):
            return False
        opening = self._printed_openings.get(self._top[0])
        return index >= opening if opening is not None else self._places_above(self._top[0], block)

    def _waits_for_pending(self, heading: OutlineHeading) -> bool:
        return any(self._due.index(pending) < self._due.index(heading) for pending in self._pending)

    @staticmethod
    def _places_above(heading: OutlineHeading, block: Block) -> bool:
        return _destination_of(heading) < PagePlace.of_block(block)

    def _run_in_opening(self, heading: OutlineHeading) -> int | None:
        title = heading.title.strip()
        return next((index for index, block in enumerate(self._content)
                     if self._places_above(heading, block) and self._prints_run_in(index, title)),
                    None)

    def _printed_opening(self, heading: OutlineHeading) -> int | None:
        label_opening = next((index for index, block in enumerate(self._content)
                              if self._places_above(heading, block) and self._prints_the_label_of(index, heading)), None)
        openings = [self._run_in_openings.get(heading), label_opening]
        return min((opening for opening in openings if opening is not None), default=None)

    def _prints_the_label_of(self, index: int, heading: OutlineHeading) -> bool:
        text = self._texts.unmarked_text_at(index)
        return BARE_LABEL_RE.match(text.strip()) is not None and TitleParts(heading.title).names_one(text)

    def _prints_run_in(self, index: int, title: str) -> bool:
        return _opens_with(self._texts.plain_text_at(index), title) or self._bold_opening_names(
            self._texts.markdown_at(index), title)

    def _bold_opening_names(self, text: str, title: str) -> bool:
        opening = self._labels.bold_opening(text)
        return opening is not None and self._match.matches(opening, title)

    def _past_the_run_in_title(self, text: str, title: str) -> str:
        past = _past_the_title(text, title)
        if past == text and self._bold_opening_names(text, title):
            return self._labels.without(text)
        return past

    def _blocks_printing_only_a_title(self) -> set[int]:
        return {index for heading, index in self._run_in_openings.items()
                if _prints_whole(self._texts.plain_text_at(index), heading.title)}

    def _blocks_printing_a_title_part(self) -> set[int]:
        parts = [TitleParts(heading.title) for heading in self._due]
        anchors = {self._first_heading_block_matching(heading) for heading in self._pending}
        return {index for index in range(len(self._content))
                if index not in anchors and any(part.names_one(self._texts.unmarked_text_at(index)) for part in parts)}

    def _first_heading_block_matching(self, heading: OutlineHeading) -> int | None:
        return next((index for index, block in enumerate(self._content) if block.kind == HEADING_KIND
                     and self._match.matches(self._texts.heading_text_at(index), heading.title)), None)

    def _title_run_into(self, index: int) -> str | None:
        return next((heading.title.strip() for heading, opening in self._run_in_openings.items()
                     if opening == index and _reads_apart_from_prose(heading.title.strip())), None)

    def _title_lines_after(self, index: int, title: str) -> set[int]:
        printed, lines = self._texts.unmarked_text_at(index), set()
        for following in range(index + 1, len(self._content)):
            printed = f"{printed} {self._texts.unmarked_text_at(following)}"
            if self._content[following].kind != HEADING_KIND or not prints_the_opening_of(printed, title):
                break
            lines.add(following)
        return lines

    def _lines_below_the_title(self, index: int, title: str) -> list:
        printed = self._texts.unmarked_text_at(index)
        below = _past_the_title(printed, title)
        if below == printed or not self._opens_a_line(index, below):
            return []
        return [Paragraph(below, False, self._content[index].file_page)]

    def _opens_a_line(self, index: int, text: str) -> bool:
        lines = self._texts.line_texts_at(index)
        return bool(text) and any(shape_of(" ".join(lines[start:])) == shape_of(text) for start in range(1, len(lines)))

    def _printed_among(self, heading: OutlineHeading, texts: list[str]) -> bool:
        return any(self._anchors(text, heading) for text in texts)

    def _pending_matches(self, text: str) -> bool:
        return any(self._anchors(text, heading) for heading in self._pending)

    def _anchors(self, text: str, heading: OutlineHeading) -> bool:
        if heading in self._printed_whole:
            return _prints_whole(text, heading.title)
        return self._match.matches(text, heading.title)

    def _titles_printed_whole(self) -> set[OutlineHeading]:
        texts = [self._texts.heading_text_at(index) for index, block in enumerate(self._content)
                 if block.kind == HEADING_KIND]
        return {heading for heading in self._due if any(_prints_whole(text, heading.title) for text in texts)}


def _destination_of(heading: OutlineHeading) -> PagePlace:
    return PagePlace(heading.file_page, heading.position)


def _prints_whole(text: str, title: str) -> bool:
    return shape_of(text) == shape_of(title)


def _opens_with(text: str, title: str) -> bool:
    return RunInTitle(title).opens(text)


def _reads_apart_from_prose(title: str) -> bool:
    return len(title.split()) > 1 or not title[-1].isalnum()


def _past_the_title(text: str, title: str) -> str:
    return RunInTitle(title).past(text)
