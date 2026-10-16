from __future__ import annotations

from .glossing import DESCRIPTION_FIELD, Introduction, ListedWorks, Listing, kind_of
from .notes import Bibliographies, Bibliography, BibliographyNotFound, Corpus, NoteNotFound
from .placement import UNSORTED_GROUP, WORK_LIST_HEADINGS, ListingGroups, ListingLine, WorkList, WorkOrder
from .sections import EMPTY_SECTION_MARKER, Section

MAX_INTRODUCTION_WORDS = 80
MAX_GROUP_NOTE_WORDS = 50
INTRODUCTION_KEY = "introduction"
GROUPS_KEY = "groups"
SORTED_KEY = "sorted"
_LINE_JOIN = "\n"


class GroupNotes:
    def __init__(self, section: Section, body: str) -> None:
        self._lines = section.content_in(body).split(_LINE_JOIN)

    def of(self, title: str) -> str:
        span = ListingGroups(self._lines).span_of(title)
        lines = self._lines[slice(*span)] if span else []
        return " ".join(line.strip() for line in lines if self._is_prose(line))

    def with_note(self, title: str, note: str) -> str:
        start, end = ListingGroups(self._lines).span_of(title)
        beneath = self._lines[start:end]
        kept = [line for line in beneath if line.strip() and not self._is_prose(line)]
        noted = ["", note.strip(), "", *kept, *self._closing_blanks(beneath)]
        return _LINE_JOIN.join(self._lines[:start] + noted + self._lines[end:])

    @staticmethod
    def _closing_blanks(lines: list[str]) -> list[str]:
        content_lines = len(_LINE_JOIN.join(lines).rstrip().split(_LINE_JOIN))
        return lines[content_lines:] or [""]

    @staticmethod
    def _is_prose(line: str) -> bool:
        stripped = line.strip()
        return bool(stripped) and stripped != EMPTY_SECTION_MARKER and not ListingLine.is_list_item(stripped)


class EmptiedUnsortedGroup:
    def __init__(self, section: Section, body: str) -> None:
        self._section = section
        self._body = body

    def removed(self) -> str:
        lines = self._section.content_in(self._body).split(_LINE_JOIN)
        span = ListingGroups(lines).span_of(UNSORTED_GROUP)
        if span is None or any(line.strip() for line in lines[slice(*span)]):
            return self._body
        heading, end = span[0] - 1, span[1]
        return self._section.with_content(self._body, _LINE_JOIN.join(lines[:heading] + lines[end:]))


class IntroductionListing:
    def __init__(self, bibliographies: Bibliographies, corpus: Corpus) -> None:
        self._bibliographies = bibliographies
        self._corpus = corpus
        self._order = WorkOrder(corpus)

    def of(self, name: str) -> dict:
        bibliography = self._bibliographies.named(name)
        listed = ListedWorks(bibliography.body)
        return {"bibliography": name, "kind": kind_of(bibliography),
                INTRODUCTION_KEY: Introduction(bibliography.body).text(),
                "maps": [self._map(child) for child in bibliography.children],
                GROUPS_KEY: self._groups(bibliography.body, listed),
                "works": [self._work(listing) for listing in listed.all()],
                "unsorted": [listing.basename for listing in listed.unsorted()]}

    def _map(self, child: str) -> dict:
        try:
            body = self._bibliographies.named(child).body
        except BibliographyNotFound:
            body = ""
        return {"name": child, INTRODUCTION_KEY: Introduction(body).text()}

    @staticmethod
    def _groups(body: str, listed: ListedWorks) -> list[dict]:
        return [{"section": heading, "title": title, "note": GroupNotes(Section(heading), body).of(title)}
                for heading in WORK_LIST_HEADINGS for title in listed.groups_of(heading) if title != UNSORTED_GROUP]

    def _work(self, listing: Listing) -> dict:
        meta = self._meta_of(listing.basename)
        return {"basename": listing.basename, "section": listing.section, "group": listing.group,
                "year": self._order.key(listing.basename)[0], "title": meta.get("title"),
                "author": meta.get("author"), DESCRIPTION_FIELD: meta.get(DESCRIPTION_FIELD)}

    def _meta_of(self, basename: str) -> dict:
        try:
            return self._corpus.note(basename).meta
        except NoteNotFound:
            return {}


class ProseCheck:
    def __init__(self, listed: list[str]) -> None:
        self._listed = listed

    def problems(self, label: str, text: object, word_limit: int) -> list[str]:
        if not isinstance(text, str) or not text.strip():
            return [f"{label} is empty"]
        checks = {f"{label} runs over one paragraph": _LINE_JOIN in text.strip(),
                  f"{label} runs over {word_limit} words": len(text.split()) > word_limit,
                  f"{label} names a listed work; it says what the works share": self._names_a_listed_work(text)}
        return [problem for problem, found in checks.items() if found]

    def _names_a_listed_work(self, text: str) -> bool:
        return any(f"[[{basename}" in text for basename in self._listed)


class Sortings:
    def __init__(self, bibliography: Bibliography, given: list[dict], order: WorkOrder) -> None:
        self._body = bibliography.body
        self._given = given
        self._order = order

    def problems(self) -> list[str]:
        unsorted = {listing.basename for listing in ListedWorks(self._body).unsorted()}
        return [problem for sorting in self._given for problem in self._problems_of(sorting, unsorted)]

    def body(self) -> str:
        body = self._body
        for sorting in self._given:
            section = Section(ListedWorks(body).named(sorting["basename"]).section)
            grouped = WorkList(section, body, self._order).with_work_grouped(sorting["basename"], sorting["group"])
            body = EmptiedUnsortedGroup(section, section.with_content(body, grouped)).removed()
        return body

    @staticmethod
    def _problems_of(sorting: dict, unsorted: set[str]) -> list[str]:
        basename, group = sorting.get("basename"), sorting.get("group")
        if basename not in unsorted:
            return [f"[[{basename}]] is no unsorted listing of a list of works that carries groups"]
        if not isinstance(group, str) or not group.strip() or group.strip() == UNSORTED_GROUP:
            return [f"[[{basename}]] is sorted into no group"]
        return []


class IntroductionWrite:
    def __init__(self, bibliography: Bibliography, answers: dict, order: WorkOrder) -> None:
        self._bibliography = bibliography
        self._introduction = answers.get(INTRODUCTION_KEY)
        self._notes = [note for note in answers.get(GROUPS_KEY) or [] if isinstance(note, dict)]
        sortings = [sorting for sorting in answers.get(SORTED_KEY) or [] if isinstance(sorting, dict)]
        self._sortings = Sortings(bibliography, sortings, order)
        self._prose = ProseCheck(ListedWorks(bibliography.body).basenames())

    def problems(self) -> list[str]:
        found = self._prose.problems("the introduction", self._introduction, MAX_INTRODUCTION_WORDS)
        found += self._sortings.problems()
        return found + self._note_problems() if not found else found

    def write(self) -> None:
        body = self._sortings.body()
        for note in self._notes:
            section = Section(note["section"])
            body = section.with_content(body, GroupNotes(section, body).with_note(note["title"], note["note"]))
        self._bibliography.write(Introduction(body).replaced_by(self._introduction))

    def _note_problems(self) -> list[str]:
        sorted_works = ListedWorks(self._sortings.body())
        return [problem for note in self._notes for problem in self._problems_of(note, sorted_works)]

    def _problems_of(self, note: dict, sorted_works: ListedWorks) -> list[str]:
        section, title = note.get("section"), note.get("title")
        label = f"the note on ### {title}"
        is_a_group = section in WORK_LIST_HEADINGS and title != UNSORTED_GROUP and title in sorted_works.groups_of(section)
        if not is_a_group:
            return [f"{label}: ## {section} carries no such group"]
        return self._prose.problems(label, note.get("note"), MAX_GROUP_NOTE_WORDS)
