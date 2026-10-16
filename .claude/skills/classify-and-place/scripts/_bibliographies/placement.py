from __future__ import annotations

import re
from dataclasses import dataclass

import vault

from .notes import Bibliographies, Bibliography, Corpus, CorpusNote, NoteChange, NoteNotFound
from .sections import EMPTY_SECTION_MARKER, Section

_LINE_JOIN = "\n"
_LIST_MARK_RE = re.compile(r"^[-*]\s+")
_GROUP_HEADING_RE = re.compile(r"^###\s+(?P<title>.+?)\s*$")
_NO_YEAR = 0

PRIMARY_WORKS_HEADING = "Primary works"
SECONDARY_WORKS_HEADING = "Secondary literature"
TRANSCRIPTS_HEADING = "Talk transcripts"
TRANSCRIPT_SOURCE_TYPE = "transcript"
PRIMARY_ROLE = "primary"
WORK_LIST_HEADINGS = (PRIMARY_WORKS_HEADING, SECONDARY_WORKS_HEADING, TRANSCRIPTS_HEADING)
UNSORTED_GROUP = "Unsorted"
ORIGINAL_YEAR_FIELD = "orig_year"
YEAR_FIELD = "year"


class RepeatedWorkList(RuntimeError):
    pass


class ListingLine:
    @staticmethod
    def is_list_item(line: str) -> bool:
        return _LIST_MARK_RE.match(line.strip()) is not None

    @staticmethod
    def basename_of(line: str) -> str | None:
        stripped = line.strip()
        if not ListingLine.is_list_item(stripped):
            return None
        target = vault.wikilink_target(stripped)
        return vault.nfc(target) if target else None

    @staticmethod
    def group_title_of(line: str) -> str | None:
        heading = _GROUP_HEADING_RE.match(line.strip())
        return heading.group("title") if heading else None


class WorkOrder:
    def __init__(self, corpus: Corpus) -> None:
        self._corpus = corpus

    def key(self, basename: str) -> tuple[int, str]:
        return self._year_of(basename), basename.casefold()

    def _year_of(self, basename: str) -> int:
        try:
            meta = self._corpus.note(basename).meta
        except NoteNotFound:
            meta = {}
        parsed = vault.parse_library_filename(f"{basename}.pdf") or {}
        candidates = (meta.get(ORIGINAL_YEAR_FIELD), meta.get(YEAR_FIELD), parsed.get("year"))
        return next((year for year in map(self._as_year, candidates) if year is not None), _NO_YEAR)

    @staticmethod
    def _as_year(value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class ListingGroups:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._headings = [index for index, line in enumerate(lines) if ListingLine.group_title_of(line)]

    def exist(self) -> bool:
        return bool(self._headings)

    def span_of(self, title: str) -> tuple[int, int] | None:
        for position, index in enumerate(self._headings):
            if ListingLine.group_title_of(self._lines[index]) == title:
                end = self._headings[position + 1] if position + 1 < len(self._headings) else len(self._lines)
                return index + 1, end
        return None

    def title_at(self, line_index: int) -> str | None:
        above = [index for index in self._headings if index < line_index]
        return ListingLine.group_title_of(self._lines[above[-1]]) if above else None


@dataclass(frozen=True)
class NewListing:
    basename: str
    line: str


class WorkList:
    def __init__(self, section: Section, body: str, order: WorkOrder) -> None:
        self._section = section
        self._body = body
        self._order = order

    def with_work(self, basename: str) -> str:
        return self.with_listing(basename, f"- [[{basename}]]", None)

    def with_listing(self, basename: str, line: str, group: str | None) -> str:
        content = self._section.content_in(self._body)
        lines = content.split(_LINE_JOIN)
        if basename in self.listed_basenames(lines):
            return content
        return _LINE_JOIN.join(self._inserted(lines, NewListing(basename, line), group))

    def with_work_grouped(self, basename: str, group: str) -> str:
        content = self._section.content_in(self._body)
        lines = content.split(_LINE_JOIN)
        index = self._index_outside_a_group(lines, basename)
        if index is None:
            return content
        others = lines[:index] + lines[index + 1:]
        return _LINE_JOIN.join(self._into_group(others, group, NewListing(basename, lines[index].strip())))

    @staticmethod
    def _index_outside_a_group(lines: list[str], basename: str) -> int | None:
        groups = ListingGroups(lines)
        return next((index for index, line in enumerate(lines) if ListingLine.basename_of(line) == basename
                     and groups.title_at(index) in (None, UNSORTED_GROUP)), None)

    def _inserted(self, lines: list[str], listing: NewListing, group: str | None) -> list[str]:
        if group is None and not ListingGroups(lines).exist():
            return self._in_order(lines, (0, len(lines)), listing)
        return self._into_group(lines, group or UNSORTED_GROUP, listing)

    def _into_group(self, lines: list[str], title: str, listing: NewListing) -> list[str]:
        span = ListingGroups(lines).span_of(title)
        if span is None:
            return self._with_new_group(lines, title, listing.line)
        return self._in_order(lines, span, listing)

    @staticmethod
    def _with_new_group(lines: list[str], title: str, line: str) -> list[str]:
        group = [f"### {title}", "", line]
        unsorted = ListingGroups(lines).span_of(UNSORTED_GROUP) if title != UNSORTED_GROUP else None
        if unsorted is not None:
            heading = unsorted[0] - 1
            return lines[:heading] + group + [""] + lines[heading:]
        kept = WorkList._kept([kept_line for kept_line in lines if kept_line.strip() != EMPTY_SECTION_MARKER])
        return kept + [""] + group + WorkList._closing_blanks(lines)

    @staticmethod
    def _closing_blanks(lines: list[str]) -> list[str]:
        content_lines = len(WorkList._kept(lines))
        return lines[content_lines:] or [""]

    def _in_order(self, lines: list[str], span: tuple[int, int], listing: NewListing) -> list[str]:
        listed = [(index, ListingLine.basename_of(lines[index])) for index in range(*span)]
        work_indices = [index for index, found in listed if found]
        if not work_indices:
            return self._first_listing(lines, span, listing.line)
        key = self._order.key(listing.basename)
        later = [index for index, found in listed if found and self._order.key(found) > key]
        position = later[0] if later else work_indices[-1] + 1
        return lines[:position] + [listing.line] + lines[position:]

    def _first_listing(self, lines: list[str], span: tuple[int, int], line: str) -> list[str]:
        start, end = span
        marker = next((index for index in range(start, end) if lines[index].strip() == EMPTY_SECTION_MARKER), None)
        if marker is not None:
            return lines[:marker] + [line] + lines[marker + 1:]
        if end < len(lines):
            return lines[:end] + [line, ""] + lines[end:]
        return self._appended(lines, line)

    @staticmethod
    def _appended(lines: list[str], listing: str) -> list[str]:
        return WorkList._kept(lines) + [listing, ""]

    @staticmethod
    def _kept(lines: list[str]) -> list[str]:
        content = _LINE_JOIN.join(lines).rstrip()
        return content.split(_LINE_JOIN) if content else []

    @staticmethod
    def listed_basenames(lines: list[str]) -> list[str]:
        found = (ListingLine.basename_of(line) for line in lines)
        return [basename for basename in found if basename]


class WorkPlacement:
    def __init__(self, note: CorpusNote, bibliographies: Bibliographies, corpus: Corpus | None = None) -> None:
        self._note = note
        self._bibliographies = bibliographies
        self._order = WorkOrder(corpus or Corpus())

    def plan(self) -> list[NoteChange]:
        changes = (self._change_of(self._bibliographies.named(name))
                   for name in self._note.bibliographies)
        return [change for change in changes if change is not None]

    def _change_of(self, bibliography: Bibliography) -> NoteChange | None:
        heading = self.heading_for(bibliography)
        section = Section(heading)
        if section.is_repeated_in(bibliography.body):
            raise RepeatedWorkList(f"{bibliography.name}: carries ## {heading} twice; merge the two lists by hand "
                                   f"before placing a work on it")
        body = self._without_misfiled_listing(bibliography.body, heading)
        content = WorkList(section, body, self._order).with_work(self._note.basename)
        new_body = section.with_content(body, content)
        if new_body == bibliography.body:
            return None
        return NoteChange(bibliography, new_body)

    def _without_misfiled_listing(self, body: str, heading: str) -> str:
        for other in WORK_LIST_HEADINGS:
            section = Section(other)
            if other != heading and section.is_in(body):
                lines = section.content_in(body).split(_LINE_JOIN)
                kept = [line for line in lines if ListingLine.basename_of(line) != self._note.basename]
                body = section.with_content(body, _LINE_JOIN.join(kept)) if kept != lines else body
        return body

    def heading_for(self, bibliography: Bibliography) -> str:
        if self._note.source_type == TRANSCRIPT_SOURCE_TYPE:
            return TRANSCRIPTS_HEADING
        return PRIMARY_WORKS_HEADING if self._is_primary_on(bibliography) else SECONDARY_WORKS_HEADING

    def _is_primary_on(self, bibliography: Bibliography) -> bool:
        if bibliography.author is None:
            return self._note.source_role == PRIMARY_ROLE
        return bibliography.author in {name.lower() for name in self._note.authors}
