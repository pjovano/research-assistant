from __future__ import annotations

import re
from dataclasses import dataclass

import vault

from .notes import Bibliographies, Bibliography, Corpus, NoteChange, NoteNotFound
from .placement import UNSORTED_GROUP, WORK_LIST_HEADINGS, ListingLine
from .sections import Section

PERIODS_FOLDER = "1 historical periods"
TOPICS_FOLDER = "3 topics"
KIND_AUTHOR = "author"
KIND_PERIOD = "period"
KIND_TOPIC = "topic"
DESCRIPTION_FIELD = "description"
GLOSS_SEPARATOR = " — "
_LINE_JOIN = "\n"
_PARAGRAPH_JOIN = "\n\n"
_LISTING_RE = re.compile(r"^(?P<link>\s*[-*]\s+\[\[[^\]]*\]\])(?P<gloss>.*)$")
_SEPARATOR_RE = re.compile(r"^\s*[—–:-]\s*")
_FIRST_SECTION_RE = re.compile(r"^## ", re.MULTILINE)


def kind_of(bibliography: Bibliography) -> str:
    if bibliography.author is not None:
        return KIND_AUTHOR
    return KIND_PERIOD if bibliography.folder == PERIODS_FOLDER else KIND_TOPIC


@dataclass(frozen=True)
class Listing:
    section: str
    group: str | None
    basename: str
    gloss: str

    @property
    def is_unsorted(self) -> bool:
        return self.group in (None, UNSORTED_GROUP)

    @staticmethod
    def gloss_of(line: str) -> str:
        match = _LISTING_RE.match(line)
        return _SEPARATOR_RE.sub("", match.group("gloss")).strip() if match else ""


class ListedWorks:
    def __init__(self, body: str) -> None:
        self._body = body

    def all(self) -> list[Listing]:
        return [listing for heading in WORK_LIST_HEADINGS for listing in self._under(heading)]

    def basenames(self) -> list[str]:
        return [listing.basename for listing in self.all()]

    def named(self, basename: str) -> Listing | None:
        return next((listing for listing in self.all() if listing.basename == basename), None)

    def groups(self) -> list[str]:
        return list(dict.fromkeys(title for heading in WORK_LIST_HEADINGS for title in self.groups_of(heading)))

    def groups_of(self, heading: str) -> list[str]:
        titles = (ListingLine.group_title_of(line) for line in Section(heading).lines_in(self._body))
        return list(dict.fromkeys(title for title in titles if title))

    def unsorted(self) -> list[Listing]:
        return [listing for listing in self.all() if listing.is_unsorted and self._is_grouped(listing.section)]

    def _is_grouped(self, heading: str) -> bool:
        return any(title != UNSORTED_GROUP for title in self.groups_of(heading))

    def _under(self, heading: str) -> list[Listing]:
        listings, group = [], None
        for line in Section(heading).lines_in(self._body):
            group = ListingLine.group_title_of(line) or group
            basename = ListingLine.basename_of(line)
            if basename:
                listings.append(Listing(heading, group, basename, Listing.gloss_of(line)))
        return listings


class Introduction:
    def __init__(self, body: str) -> None:
        self._body = body

    def text(self) -> str:
        return _FIRST_SECTION_RE.split(vault.body_after_source_link(self._body), maxsplit=1)[0].strip()

    def replaced_by(self, text: str) -> str:
        first_section = _FIRST_SECTION_RE.search(self._body)
        sections = self._body[first_section.start():] if first_section else ""
        return _PARAGRAPH_JOIN.join(part for part in (text.strip(), sections) if part).rstrip() + _LINE_JOIN


class Descriptions:
    def __init__(self, corpus: Corpus) -> None:
        self._corpus = corpus

    def of(self, basename: str) -> str:
        try:
            given = self._corpus.note(basename).meta.get(DESCRIPTION_FIELD)
        except NoteNotFound:
            given = None
        return " ".join(str(given).split()) if given else ""


class DescribedBody:
    def __init__(self, descriptions: Descriptions) -> None:
        self._descriptions = descriptions

    def of(self, body: str) -> str:
        for heading in WORK_LIST_HEADINGS:
            body = self._with_list_described(body, Section(heading))
        return body

    def _with_list_described(self, body: str, section: Section) -> str:
        if section.is_repeated_in(body):
            return body
        content = section.content_in(body)
        described = _LINE_JOIN.join(self._described(line) for line in content.split(_LINE_JOIN))
        return section.with_content(body, described) if described != content else body

    def _described(self, line: str) -> str:
        listing = _LISTING_RE.match(line)
        basename = ListingLine.basename_of(line)
        description = self._descriptions.of(basename) if listing and basename else ""
        return f"{listing.group('link')}{GLOSS_SEPARATOR}{description}" if description else line


class GlossCopy:
    def __init__(self, bibliographies: Bibliographies, descriptions: Descriptions) -> None:
        self._bibliographies = bibliographies
        self._described = DescribedBody(descriptions)

    def changes(self) -> list[NoteChange]:
        described = ((entry, self._described.of(entry.body)) for entry in self._bibliographies.entries())
        return [NoteChange(entry, body) for entry, body in described if body != entry.body]


class GlossPlan:
    def __init__(self, bibliographies: Bibliographies, corpus: Corpus) -> None:
        self._bibliographies = bibliographies
        self._corpus = corpus

    def for_works(self, basenames: list[str], bibliographies: list[str] = ()) -> list[str]:
        placed_on = {name for basename in basenames for name in self._bibliographies_of(vault.nfc(basename))}
        touched = placed_on | {vault.nfc(name) for name in bibliographies}
        return [entry.name for entry in self._listing_anything()
                if entry.name in touched or not Introduction(entry.body).text()]

    def for_all(self) -> list[str]:
        return [entry.name for entry in self._listing_anything()]

    def _listing_anything(self) -> list[Bibliography]:
        entries = sorted(self._bibliographies.entries(), key=lambda entry: entry.name)
        return [entry for entry in entries if entry.children or ListedWorks(entry.body).all()]

    def _bibliographies_of(self, basename: str) -> list[str]:
        try:
            return self._corpus.note(basename).bibliographies
        except NoteNotFound:
            return []
