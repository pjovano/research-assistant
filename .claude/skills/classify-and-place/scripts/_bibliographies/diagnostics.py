from __future__ import annotations

from collections import Counter

import vault

from .catalogue import AuthorCatalogue
from .notes import SECONDARY_ROLE, Bibliographies, Bibliography, Corpus, CorpusNote, Writing, WritingNote
from .placement import (
    PRIMARY_WORKS_HEADING,
    SECONDARY_WORKS_HEADING,
    TRANSCRIPT_SOURCE_TYPE,
    WORK_LIST_HEADINGS,
    WorkList,
)
from .routing import RoutingFindings
from .sections import Section
from .tree import BibliographyTree

WORKS_FOR_AN_AUTHOR_BIBLIOGRAPHY = 5
AUTHORS_FOLDER = "2 authors"
PRIMARY_ROLE = "primary"
HISTORICAL_TYPE = "historical"
ORIGINAL_YEAR_FIELD = "orig_year"
REISSUES_HEADING = "Reissues -- a primary or historical work with no orig_year"
CATALOGUE_HEADING = "Catalogue -- an author's work missing from the author's bibliography"
STRAY_HEADING ="Catalogue -- a primary work off its author's bibliography"
ROUTING_HEADING = "Routing -- a work on a routing bibliography"
WRITING_HEADING = "Writing -- an atomic note or project file placed off the bibliographies"


class Report:
    def __init__(self) -> None:
        self._blocking: list[tuple[str, list[str]]] = []
        self._advisory: list[tuple[str, list[str]]] = []

    def add(self, heading: str, problems: list[str]) -> None:
        if problems:
            self._blocking.append((heading, problems))

    def add_advisory(self, heading: str, problems: list[str]) -> None:
        if problems:
            self._advisory.append((heading, problems))

    @property
    def is_clean(self) -> bool:
        return not self._blocking

    def as_dict(self) -> dict:
        return {"blocking": dict(self._blocking), "advisory": dict(self._advisory)}

    def print(self) -> None:
        for heading, problems in self._blocking:
            self._print_group(heading, problems)
        for heading, problems in self._advisory:
            self._print_group(f"{heading} (advisory)", problems)
        if self._is_empty:
            print("nothing to report")

    @property
    def _is_empty(self) -> bool:
        return not (self._blocking or self._advisory)

    def _print_group(self, heading: str, problems: list[str]) -> None:
        print(f"\n{heading}")
        for problem in problems:
            print(f"  {problem}")


class TreeChecks:
    def __init__(self, bibliographies: Bibliographies) -> None:
        self._entries = bibliographies.entries()
        self._names = bibliographies.names()

    def repeated_names(self) -> list[str]:
        counted = Counter(entry.name for entry in self._entries)
        return [f"{name}: {count} bibliographies carry this name, and a wikilink names only one"
                for name, count in sorted(counted.items()) if count > 1]

    def dangling_children(self) -> list[str]:
        return [f"{entry.name}: lists [[{child}]] as a map beneath it, which is not a bibliography"
                for entry in self._entries for child in entry.children
                if child not in self._names]

    def cycles(self) -> list[str]:
        tree = BibliographyTree(self._entries)
        return [f"{name}: sits beneath itself, through {tree.ancestors_of(name)}"
                for name in sorted(self._names) if name in tree.ancestors_of(name)]


class ConflictCopyChecks:
    def __init__(self, bibliographies: Bibliographies, corpus: Corpus) -> None:
        self._names = bibliographies.conflict_copies() + corpus.conflict_copies()

    def copies(self) -> list[str]:
        return [f"{name}: a sync conflict copy sits beside the note; merge it by hand and delete it"
                for name in self._names]


class ListingChecks:
    def __init__(self, bibliographies: Bibliographies, notes: list[CorpusNote]) -> None:
        self._entries = bibliographies.entries()
        self._field_of = {note.basename: note.bibliographies for note in notes}

    def unbacked_listings(self) -> list[str]:
        return [f"{entry.name}: lists [[{basename}]], whose corpus file's field: does not name it"
                for entry in self._entries for basename in self._listed(entry)
                if entry.name not in self._field_of.get(basename, [])]

    def double_listings(self) -> list[str]:
        return [f"{entry.name}: lists [[{basename}]] under both {PRIMARY_WORKS_HEADING} and {SECONDARY_WORKS_HEADING}"
                for entry in self._entries for basename in self._in_both_sections(entry)]

    def repeated_lists(self) -> list[str]:
        return [f"{entry.name}: carries ## {heading} twice; merge the two lists by hand"
                for entry in self._entries for heading in WORK_LIST_HEADINGS
                if Section(heading).is_repeated_in(entry.body)]

    def _in_both_sections(self, entry: Bibliography) -> set[str]:
        return set(self._under(entry, PRIMARY_WORKS_HEADING)) & set(self._under(entry, SECONDARY_WORKS_HEADING))

    def _listed(self, entry: Bibliography) -> list[str]:
        return [basename for heading in WORK_LIST_HEADINGS for basename in self._under(entry, heading)]

    def _under(self, entry: Bibliography, heading: str) -> list[str]:
        return WorkList.listed_basenames(Section(heading).lines_in(entry.body))


class PlacementChecks:
    def __init__(self, notes: list[CorpusNote], tree: BibliographyTree, catalogue: AuthorCatalogue) -> None:
        self._notes = notes
        self._tree = tree
        self._catalogue = catalogue

    def unknown_bibliographies(self) -> list[str]:
        return [f"{note.basename}: field: names [[{name}]], which is not a bibliography"
                for note in self._notes for name in note.bibliographies
                if name not in self._tree.names()]

    def ancestor_placements(self) -> list[str]:
        return [f"{note.basename}: field: names [[{name}]] and its ancestor [[{ancestor}]]; "
                f"a work sits at the deepest bibliography only"
                for note in self._notes for name in note.bibliographies
                if not self._catalogue.holds(note, name)
                for ancestor in self._tree.ancestors_of(name) if self._sits_on_ancestor(note, ancestor)]

    def _sits_on_ancestor(self, note: CorpusNote, ancestor: str) -> bool:
        return ancestor in note.bibliographies and not self._catalogue.holds(note, ancestor)

    def unplaced(self) -> list[str]:
        return [f"{note.basename}: sits on no bibliography yet"
                for note in self._notes if not note.bibliographies]


class WritingChecks:
    def __init__(self, notes: list[WritingNote], tree: BibliographyTree) -> None:
        self._notes = notes
        self._tree = tree

    def unknown_bibliographies(self) -> list[str]:
        return [f"{note.basename}: field: names [[{name}]], which is not a bibliography"
                for note in self._notes for name in note.bibliographies
                if name not in self._tree.names()]

    def ancestor_placements(self) -> list[str]:
        return [f"{note.basename}: field: names [[{name}]] and its ancestor [[{ancestor}]]; "
                f"a note sits on the most specific bibliography only"
                for note in self._notes for name in note.bibliographies
                for ancestor in self._tree.ancestors_of(name) if ancestor in note.bibliographies]


class AuthorChecks:
    def __init__(self, bibliographies: Bibliographies, notes: list[CorpusNote]) -> None:
        self._entries = bibliographies.entries()
        self._covered = bibliographies.authors()
        corpus_files = [note for note in notes if not note.is_transcript]
        self._works_of = Counter(author for note in corpus_files for author in note.authors)
        self._basenames_of: dict[str, list[str]] = {}
        for note in corpus_files:
            for author in note.authors:
                self._basenames_of.setdefault(author, []).append(note.basename)

    def bibliographies_outside_the_authors_folder(self) -> list[str]:
        return [f"{entry.name}: an author bibliography outside {AUTHORS_FOLDER}/"
                for entry in self._entries
                if entry.author is not None and entry.folder != AUTHORS_FOLDER]

    def authors_to_propose(self) -> list[str]:
        return [f"{author}: {count} works in the library; propose an author bibliography"
                for author, count in self._uncovered()]

    def uncovered_authors(self) -> list[dict]:
        return [{"author": author, "count": count, "works": sorted(self._basenames_of[author])}
                for author, count in self._uncovered()]

    def _uncovered(self) -> list[tuple[str, int]]:
        counted = sorted(self._works_of.items(), key=lambda entry: (-entry[1], entry[0]))
        return [(author, count) for author, count in counted
                if count >= WORKS_FOR_AN_AUTHOR_BIBLIOGRAPHY and author.lower() not in self._covered]


class ClassificationChecks:
    def __init__(self, notes: list[CorpusNote], known_basenames: set[str]) -> None:
        self._notes = notes
        self._known = known_basenames

    def invalid_values(self) -> list[str]:
        return (self._outside("source_type", vault.SOURCE_TYPES)
                + self._outside("source_role", vault.SOURCE_ROLES))

    def _outside(self, key: str, vocabulary: dict) -> list[str]:
        values = ((note.basename, note.meta.get(key)) for note in self._notes)
        return [f"{basename}: {key} '{value}' is not one of {sorted(vocabulary)}"
                for basename, value in values if value and value not in vocabulary]

    def misplaced_transcript_types(self) -> list[str]:
        return self._transcripts_of_another_type() + self._corpus_files_typed_transcript()

    def _transcripts_of_another_type(self) -> list[str]:
        return [f"{note.basename}: a transcript's source_type is '{note.source_type}'; a transcript takes "
                f"{TRANSCRIPT_SOURCE_TYPE}" for note in self._notes
                if note.is_transcript and note.source_type and note.source_type != TRANSCRIPT_SOURCE_TYPE]

    def _corpus_files_typed_transcript(self) -> list[str]:
        return [f"{note.basename}: a corpus file's source_type is '{TRANSCRIPT_SOURCE_TYPE}', which only a "
                f"transcript takes" for note in self._notes
                if not note.is_transcript and note.source_type == TRANSCRIPT_SOURCE_TYPE]

    def unclassified(self) -> list[str]:
        return [f"{note.basename}: no source_type or source_role yet"
                for note in self._notes if not (note.source_type and note.source_role)]

    def reissues_without_an_original_year(self) -> list[str]:
        return [f"{note.basename}: a {note.source_role} {note.source_type} with no orig_year; set it if the held "
                "edition is not the first" for note in self._notes if self._may_be_a_reissue(note)]

    @staticmethod
    def _may_be_a_reissue(note: CorpusNote) -> bool:
        original = note.source_role == PRIMARY_ROLE or note.source_type == HISTORICAL_TYPE
        return original and not note.meta.get(ORIGINAL_YEAR_FIELD)

    def commentaries_not_secondary(self) -> list[str]:
        return [f"{note.basename}: commentary_on: [[{note.commentary_target}]] but source_role "
                f"is '{note.source_role}'; a commentary is roled {SECONDARY_ROLE}"
                for note in self._notes
                if note.commentary_target and note.source_role != SECONDARY_ROLE]

    def pending_commentary_targets(self) -> list[str]:
        return [f"{note.basename}: commentary_on: [[{note.commentary_target}]], which has no corpus file yet"
                for note in self._notes
                if note.commentary_target and note.commentary_target not in self._known]


class ReportBuilder:
    def __init__(self, bibliographies: Bibliographies, corpus: Corpus, writing: Writing) -> None:
        notes = corpus.notes()
        tree = BibliographyTree(bibliographies.entries())
        self._tree_checks = TreeChecks(bibliographies)
        self._conflicts = ConflictCopyChecks(bibliographies, corpus)
        self._placement = PlacementChecks(notes, tree, AuthorCatalogue(bibliographies))
        self._writing = WritingChecks(writing.notes(), tree)
        self._routing = RoutingFindings(bibliographies, notes)
        self._listings = ListingChecks(bibliographies, notes)
        self._authors = AuthorChecks(bibliographies, notes)
        self._classification = ClassificationChecks(notes, corpus.basenames())

    def build(self) -> Report:
        report = Report()
        self._add_findings(report)
        self._add_advisories(report)
        return report

    def _add_findings(self, report: Report) -> None:
        report.add("Conflict copies", self._conflicts.copies())
        report.add("Bibliographies", self._tree_checks.repeated_names()
                   + self._tree_checks.dangling_children()
                   + self._tree_checks.cycles())
        report.add("Placement", self._placement.unknown_bibliographies()
                   + self._placement.ancestor_placements())
        report.add("Listings", self._listings.unbacked_listings() + self._listings.double_listings()
                   + self._listings.repeated_lists())
        report.add("Classification", self._classification.invalid_values()
                   + self._classification.misplaced_transcript_types()
                   + self._classification.commentaries_not_secondary())

    def _add_advisories(self, report: Report) -> None:
        report.add_advisory("Authors -- five or more works and no author bibliography",
                            self._authors.authors_to_propose())
        report.add_advisory(f"Authors -- an author bibliography outside {AUTHORS_FOLDER}/",
                            self._authors.bibliographies_outside_the_authors_folder())
        report.add_advisory("Backlog -- unclassified", self._classification.unclassified())
        report.add_advisory(REISSUES_HEADING, self._classification.reissues_without_an_original_year())
        report.add_advisory("Backlog -- unplaced", self._placement.unplaced())
        report.add_advisory(CATALOGUE_HEADING, [f"{gap['work']}: not on {gap['missing']}"
                                                for gap in self._routing.catalogue_gaps()])
        report.add_advisory(STRAY_HEADING, [
            f"{placement['work']}: sits on {', '.join(f'[[{name}]]' for name in placement['on'])} as well"
            for placement in self._routing.stray_placements()])
        report.add_advisory(ROUTING_HEADING, [f"{placement['work']}: sits on [[{placement['on']}]], a routing bibliography"
                                              for placement in self._routing.routing_placements()])
        report.add_advisory("Commentaries -- targets with no corpus file yet",
                            self._classification.pending_commentary_targets())
        report.add_advisory(WRITING_HEADING, self._writing.unknown_bibliographies()
                            + self._writing.ancestor_placements())
