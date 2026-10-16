from __future__ import annotations

import re
from dataclasses import dataclass

import vault

from .catalogue import AuthorCatalogue
from .fields import FieldRewrite
from .glossing import ListedWorks, Listing
from .maps import MapLink
from .notes import Bibliographies, Bibliography, Corpus, CorpusNote, NoteChange, Writing
from .placement import WorkList, WorkOrder, WorkPlacement
from .sections import Section
from .tree import BibliographyTree

_FORBIDDEN_IN_A_GROUP = re.compile(r"[#\[\]|\n]")


@dataclass(frozen=True)
class Fold:
    name: str
    target: str
    group: str

    @classmethod
    def of(cls, given: dict) -> Fold:
        name = vault.nfc(str(given.get("name") or "")).strip()
        group = str(given.get("group") or "").strip() or name
        return cls(name, vault.nfc(str(given.get("into") or "")).strip(), group)

    def links(self, tree: BibliographyTree) -> list[MapLink]:
        return [MapLink(child, self.target) for child in tree.children_of(self.name)]

    def unlinks(self, tree: BibliographyTree) -> list[MapLink]:
        above = [MapLink(self.name, parent) for parent in tree.parents_of(self.name)]
        return above + [MapLink(child, self.name) for child in tree.children_of(self.name)]

    def works(self, corpus: Corpus) -> list[str]:
        return sorted(note.basename for note in corpus.notes() if self.name in note.bibliographies)

    def writing(self, writing: Writing) -> list[str]:
        return sorted(note.basename for note in writing.placed_on(self.name))

    def summary(self, corpus: Corpus, writing: Writing) -> dict:
        return {"name": self.name, "into": self.target, "group": self.group, "works": self.works(corpus),
                "writing": self.writing(writing)}


class FoldChecks:
    def __init__(self, folds: list[Fold], bibliographies: Bibliographies, named_elsewhere: set[str]) -> None:
        self._folds = folds
        self._entries = {entry.name: entry for entry in bibliographies.entries()}
        self._tree = BibliographyTree(bibliographies.entries())
        self._named_elsewhere = named_elsewhere

    def problems(self) -> list[str]:
        return [problem for fold in self._folds for problem in self._problems_of(fold)]

    def _problems_of(self, fold: Fold) -> list[str]:
        unknown = [f"fold: '{name}' is not a bibliography" for name in (fold.name, fold.target)
                   if name not in self._entries]
        return unknown or self._identity_problems(fold) + self._answer_problems(fold)

    def _identity_problems(self, fold: Fold) -> list[str]:
        folded = self._entries[fold.name]
        problems = []
        if folded.author is not None:
            problems.append(f"fold: '{fold.name}' is an author bibliography, which lists every work its author wrote")
        if folded.aliases:
            problems.append(f"fold: '{fold.name}' carries aliases the user wrote; ask the user")
        if fold.name == fold.target or fold.name in self._tree.ancestors_of(fold.target):
            problems.append(f"fold: '{fold.target}' sits beneath '{fold.name}', or is it")
        if _FORBIDDEN_IN_A_GROUP.search(fold.group):
            problems.append(f"fold: the group '{fold.group}' carries one of # [ ] |")
        return problems

    def _answer_problems(self, fold: Fold) -> list[str]:
        folded = [other.name for other in self._folds]
        problems = []
        if folded.count(fold.name) > 1:
            problems.append(f"fold: '{fold.name}' is folded twice")
        if fold.target in folded:
            problems.append(f"fold: '{fold.target}' is folded itself, into another bibliography")
        if fold.name in self._named_elsewhere:
            problems.append(f"fold: '{fold.name}' is named by another answer of the same reshaping")
        return problems


class FoldWrite:
    def __init__(self, fold: Fold, corpus: Corpus, writing: Writing) -> None:
        self._fold = fold
        self._corpus = corpus
        self._writing = writing

    def apply(self) -> list[str]:
        folded = Bibliographies().named(self._fold.name)
        listings = {listing.basename: listing for listing in ListedWorks(folded.body).all()}
        works = self._fold.works(self._corpus)
        for basename in works:
            self._carry(self._corpus.note(basename), listings.get(basename))
        self._carry_writing()
        self._relink(BibliographyTree(Bibliographies().entries()))
        Bibliographies().named(self._fold.name).delete()
        return works

    def _carry_writing(self) -> None:
        for note in self._writing.placed_on(self._fold.name):
            FieldRewrite(note).moved([self._fold.name], self._fold.target)

    def _carry(self, note: CorpusNote, listing: Listing | None) -> None:
        catalogue = AuthorCatalogue(Bibliographies())
        if catalogue.admits(note, self._fold.target):
            self._list_on_the_target(note, listing)
            FieldRewrite(note).moved([self._fold.name], self._fold.target)
        else:
            self._leave_to_its_authors(note, catalogue.maps_of(note))

    def _list_on_the_target(self, note: CorpusNote, listing: Listing | None) -> None:
        target = Bibliographies().named(self._fold.target)
        section = Section(WorkPlacement(note, Bibliographies(), self._corpus).heading_for(target))
        order = WorkOrder(self._corpus)
        line = _listing_line(note.basename, listing)
        listed = section.with_content(target.body, WorkList(section, target.body, order).with_listing(
            note.basename, line, self._fold.group))
        grouped = WorkList(section, listed, order).with_work_grouped(note.basename, self._fold.group)
        self._write(target, section.with_content(listed, grouped))

    def _leave_to_its_authors(self, note: CorpusNote, author_bibliographies: list[str]) -> None:
        FieldRewrite(note).moved([self._fold.name], author_bibliographies[0])
        for change in WorkPlacement(Corpus().note(note.basename), Bibliographies(), self._corpus).plan():
            change.write()

    def _relink(self, tree: BibliographyTree) -> None:
        for link in self._fold.links(tree):
            link.link()
        for parent in tree.parents_of(self._fold.name):
            MapLink(self._fold.name, parent).unlink()

    @staticmethod
    def _write(bibliography: Bibliography, body: str) -> None:
        if body != bibliography.body:
            NoteChange(bibliography, body).write()


def _listing_line(basename: str, listing: Listing | None) -> str:
    if listing is None or not listing.gloss:
        return f"- [[{basename}]]"
    return f"- [[{basename}]] — {listing.gloss}"
