from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

import vault

from .catalogue import AuthorCatalogue
from .fields import FieldRewrite
from .diagnostics import AUTHORS_FOLDER
from .foldfinding import MIN_WORKS_FOR_A_BIBLIOGRAPHY
from .folding import Fold, FoldChecks, FoldWrite
from .glossing import KIND_AUTHOR, KIND_PERIOD, KIND_TOPIC, PERIODS_FOLDER, TOPICS_FOLDER
from .maps import MapLink, MapsList, PlannedTree
from .notes import MAPS_HEADING, Bibliographies, Bibliography, Corpus, NoteChange, NoteNotFound, Writing
from .placement import (
    PRIMARY_WORKS_HEADING,
    SECONDARY_WORKS_HEADING,
    WORK_LIST_HEADINGS,
    ListingLine,
    WorkPlacement,
)
from .sections import EMPTY_SECTION_MARKER, Section
from .shapelisting import ShapeListing
from .tree import BibliographyTree

__all__ = ["MapsList", "Reshape", "ReshapeAnswers", "ReshapeRefused", "ShapeListing", "WorkListRemoval"]

FOLDER_OF_KIND = {KIND_AUTHOR: AUTHORS_FOLDER, KIND_PERIOD: PERIODS_FOLDER, KIND_TOPIC: TOPICS_FOLDER}
KIND_OF_FOLDER = {folder: kind for kind, folder in FOLDER_OF_KIND.items()}
ROOT_KINDS = (KIND_TOPIC, KIND_PERIOD)
LISTS_OF_A_NEW_BIBLIOGRAPHY = (PRIMARY_WORKS_HEADING, SECONDARY_WORKS_HEADING)


class ReshapeRefused(ValueError):
    pass


@dataclass(frozen=True)
class Creation:
    name: str
    kind: str
    parent: str | None
    author: str | None
    works: list[str]

    @classmethod
    def of(cls, given: dict) -> Creation:
        parent = vault.nfc(str(given.get("parent") or "")).strip() or None
        return cls(vault.nfc(str(given.get("name") or "")).strip(), str(given.get("kind") or ""), parent,
                   given.get("author") or None, [vault.nfc(str(work)) for work in given.get("works") or []])

    @property
    def is_root(self) -> bool:
        return self.parent is None

    def body(self) -> str:
        sections = "".join(f"\n## {heading}\n\n{EMPTY_SECTION_MARKER}\n" for heading in LISTS_OF_A_NEW_BIBLIOGRAPHY)
        return f"## {MAPS_HEADING}\n{sections}"

    def meta(self) -> dict:
        return {"author": self.author} if self.kind == KIND_AUTHOR else {}


@dataclass(frozen=True)
class Move:
    work: str
    source: str
    target: str

    @classmethod
    def of(cls, given: dict) -> Move:
        return cls(vault.nfc(str(given.get("work") or "")), vault.nfc(str(given.get("from") or "")),
                   vault.nfc(str(given.get("to") or "")))


@dataclass(frozen=True)
class Addition:
    work: str
    target: str

    @classmethod
    def of(cls, given: dict) -> Addition:
        return cls(vault.nfc(str(given.get("work") or "")), vault.nfc(str(given.get("to") or "")))

    def summary(self) -> dict:
        return {"work": self.work, "to": self.target}


@dataclass
class ReshapeAnswers:
    creations: list[Creation] = field(default_factory=list)
    moves: list[Move] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    links: list[MapLink] = field(default_factory=list)
    unlinks: list[MapLink] = field(default_factory=list)
    additions: list[Addition] = field(default_factory=list)
    folds: list[Fold] = field(default_factory=list)

    @classmethod
    def read(cls, path: Path) -> ReshapeAnswers:
        given = json.loads(path.read_text(encoding="utf-8"))
        return cls([Creation.of(item) for item in given.get("create") or []],
                   [Move.of(item) for item in given.get("move") or []],
                   [str(question) for question in given.get("questions") or []],
                   [MapLink.of(item) for item in given.get("link") or []],
                   [MapLink.of(item) for item in given.get("unlink") or []],
                   [Addition.of(item) for item in given.get("add") or []],
                   [Fold.of(item) for item in given.get("fold") or []])

    def touched(self) -> list[str]:
        names = [creation.name for creation in self.creations]
        names += [creation.parent for creation in self.creations if not creation.is_root]
        names += [move.source for move in self.moves] + [move.target for move in self.moves]
        names += [name for link in self.links + self.unlinks for name in (link.name, link.parent)]
        names += [addition.target for addition in self.additions]
        names += [name for fold in self.folds for name in (fold.name, fold.target)]
        return sorted(set(names))

    def works(self, corpus: Corpus) -> list[str]:
        created = {work for creation in self.creations for work in creation.works}
        folded = {work for fold in self.folds for work in fold.works(corpus)}
        moved = {move.work for move in self.moves} | {addition.work for addition in self.additions}
        return sorted(created | moved | folded)

    def named_beside_the_folds(self) -> set[str]:
        names = {creation.parent for creation in self.creations if not creation.is_root}
        names |= {name for move in self.moves for name in (move.source, move.target)}
        names |= {name for link in self.links + self.unlinks for name in (link.name, link.parent)}
        return names | {addition.target for addition in self.additions}

    def fold_links(self, tree: BibliographyTree) -> list[MapLink]:
        return [link for fold in self.folds for link in fold.links(tree)]

    def planned_tree(self, tree: BibliographyTree) -> PlannedTree:
        created = {creation.name: creation.parent for creation in self.creations}
        links = self.links + self.fold_links(tree)
        unlinks = self.unlinks + [unlink for fold in self.folds for unlink in fold.unlinks(tree)]
        return PlannedTree.planned(tree, created, links, unlinks)

    def planned_catalogue(self, bibliographies: Bibliographies) -> AuthorCatalogue:
        created = {creation.name: creation.author for creation in self.creations
                   if creation.kind == KIND_AUTHOR and creation.author}
        return AuthorCatalogue(bibliographies, created)

    def with_strays_moved(self, bibliographies: Bibliographies, corpus: Corpus) -> ReshapeAnswers:
        catalogue = self.planned_catalogue(bibliographies)
        folded = {fold.name for fold in self.folds}
        strays = [Move(note.basename, name, catalogue.maps_of(note)[0])
                  for note in corpus.notes() for name in catalogue.strays_of(note) if name not in folded]
        return replace(self, moves=self.moves + [move for move in strays if move not in self.moves])


class ReshapeChecks:
    def __init__(self, answers: ReshapeAnswers, bibliographies: Bibliographies, corpus: Corpus) -> None:
        self._answers = answers
        self._names = bibliographies.names()
        self._created = {creation.name for creation in answers.creations}
        self._tree = BibliographyTree(bibliographies.entries())
        self._planned = answers.planned_tree(self._tree)
        self._kinds = {entry.name: KIND_OF_FOLDER.get(entry.folder) for entry in bibliographies.entries()}
        self._kinds.update({creation.name: creation.kind for creation in answers.creations})
        self._catalogue = answers.planned_catalogue(bibliographies)
        self._corpus = corpus
        self._folds = FoldChecks(answers.folds, bibliographies, answers.named_beside_the_folds())

    def require_sound(self) -> None:
        problems = [problem for creation in self._answers.creations for problem in self._creation_problems(creation)]
        problems += [problem for move in self._answers.moves for problem in self._move_problems(move)]
        problems += [problem for addition in self._answers.additions for problem in self._addition_problems(addition)]
        problems += [problem for link in self._answers.links for problem in self._link_problems(link)]
        problems += [problem for unlink in self._answers.unlinks for problem in self._unlink_problems(unlink)]
        problems += self._folds.problems()
        if problems:
            raise ReshapeRefused("; ".join(problems))

    def _link_problems(self, link: MapLink) -> list[str]:
        known = self._names | self._created
        problems = [f"link: '{name}' is not a bibliography" for name in (link.name, link.parent) if name not in known]
        return problems or self._cycle_problems(link.name)

    def _unlink_problems(self, unlink: MapLink) -> list[str]:
        if unlink.parent not in self._tree.parents_of(unlink.name):
            return [f"unlink: '{unlink.parent}' does not list '{unlink.name}'"]
        if self._kinds.get(unlink.name) == KIND_AUTHOR and not self._planned.parents_of(unlink.name):
            return [f"unlink: '{unlink.name}' would be an author bibliography no bibliography lists"]
        return []

    def _cycle_problems(self, name: str) -> list[str]:
        if self._planned.sits_beneath_itself(name):
            return [f"'{name}': sits beneath itself, through {self._planned.ancestors_of(name)}"]
        return []

    def _creation_problems(self, creation: Creation) -> list[str]:
        problems = self._identity_problems(creation) + self._place_problems(creation)
        gathered = self._gathered(creation, frozenset())
        if len(gathered) < MIN_WORKS_FOR_A_BIBLIOGRAPHY:
            problems.append(f"'{creation.name}': {len(gathered)} works on it and beneath it; a bibliography needs "
                            f"{MIN_WORKS_FOR_A_BIBLIOGRAPHY} works that share its subject")
        return problems + self._work_problems(creation.works, creation.name)

    def _identity_problems(self, creation: Creation) -> list[str]:
        problems = []
        if not creation.name or creation.name in self._names:
            problems.append(f"'{creation.name}' is no new name")
        if creation.kind not in FOLDER_OF_KIND:
            problems.append(f"'{creation.name}': kind '{creation.kind}' is not author, period, or topic")
        if creation.kind == KIND_AUTHOR and not creation.author:
            problems.append(f"'{creation.name}': an author bibliography carries author:")
        return problems

    def _place_problems(self, creation: Creation) -> list[str]:
        problems = []
        if creation.is_root and creation.kind not in ROOT_KINDS:
            problems.append(f"'{creation.name}': a root is a discipline or a period, never kind '{creation.kind}'")
        if not creation.is_root and creation.parent not in self._names | self._created:
            problems.append(f"'{creation.name}': parent '{creation.parent}' is not a bibliography")
        return problems + self._cycle_problems(creation.name)

    def _gathered(self, creation: Creation, seen: frozenset[str]) -> set[str]:
        beneath = [child for child in self._answers.creations
                   if child.parent == creation.name and child.name not in seen]
        within = seen | {creation.name}
        linked = [link.name for link in self._answers.links if link.parent == creation.name]
        gathered = set(creation.works).union(*(self._gathered(child, within) for child in beneath))
        return gathered | self._works_on(linked)

    def _works_on(self, names: list[str]) -> set[str]:
        if not names:
            return set()
        return {note.basename for note in self._corpus.notes() if set(names).intersection(note.bibliographies)}

    def _move_problems(self, move: Move) -> list[str]:
        problems = self._work_problems([move.work], move.target)
        if move.target not in self._names | self._created:
            problems.append(f"'{move.work}': '{move.target}' is not a bibliography")
        if not problems and self._catalogue.holds(self._corpus.note(move.work), move.source):
            problems.append(f"'{move.work}': '{move.source}' is its author's bibliography, which lists every work "
                            "the author wrote; add the work to '{move.target}' instead")
        return problems

    def _addition_problems(self, addition: Addition) -> list[str]:
        problems = self._work_problems([addition.work], addition.target)
        if addition.target not in self._names | self._created:
            problems.append(f"'{addition.work}': '{addition.target}' is not a bibliography")
        return problems or self._lineage_problems(addition)

    def _lineage_problems(self, addition: Addition) -> list[str]:
        note = self._corpus.note(addition.work)
        if self._catalogue.holds(note, addition.target):
            return []
        placed = [name for name in note.bibliographies if not self._catalogue.holds(note, name)]
        related = [name for name in placed if name in self._planned.ancestors_of(addition.target)
                   or addition.target in self._planned.ancestors_of(name)]
        return [f"'{addition.work}': '{addition.target}' and '{name}' sit on one line of descent; a work sits on "
                "the most specific bibliography only" for name in related]

    def _work_problems(self, works: list[str], target: str) -> list[str]:
        unknown = [f"'{work}' has no corpus file" for work in works if not self._exists(work)]
        held = [self._corpus.note(work) for work in works if self._exists(work)]
        return unknown + [f"'{note.basename}': a primary work whose author carries a bibliography sits on its "
                          f"author's bibliography alone, never on '{target}'"
                          for note in held if not self._catalogue.admits(note, target)]

    def _exists(self, basename: str) -> bool:
        try:
            self._corpus.note(basename)
        except NoteNotFound:
            return False
        return True


class WorkListRemoval:
    def __init__(self, body: str) -> None:
        self._body = body

    def without(self, basename: str) -> str:
        body = self._body
        for heading in WORK_LIST_HEADINGS:
            section = Section(heading)
            if section.is_in(body):
                lines = section.content_in(body).split("\n")
                kept = [line for line in lines if ListingLine.basename_of(line) != basename]
                body = section.with_content(body, "\n".join(kept)) if kept != lines else body
        return body


class Reshape:
    def __init__(self, answers: ReshapeAnswers, corpus: Corpus | None = None) -> None:
        self._answers = answers
        self._corpus = corpus or Corpus()
        self._writing = Writing()

    def plan(self) -> dict:
        self._check_and_complete(Bibliographies())
        return self._report(False)

    def apply(self) -> dict:
        bibliographies = Bibliographies()
        self._check_and_complete(bibliographies)
        tree = BibliographyTree(bibliographies.entries())
        planned = self._answers.planned_tree(tree)
        report = self._report(True)
        self._write_maps()
        self._place_works(planned)
        folded = [work for fold in self._answers.folds for work in FoldWrite(fold, Corpus(), self._writing).apply()]
        linked = {link.name for link in self._answers.links + self._answers.fold_links(tree)}
        for work in sorted(set(self._beneath(linked, planned)) | set(folded)):
            self._deepen(work, planned)
        return report

    def _check_and_complete(self, bibliographies: Bibliographies) -> None:
        ReshapeChecks(self._answers, bibliographies, self._corpus).require_sound()
        self._answers = self._answers.with_strays_moved(bibliographies, self._corpus)

    def _place_works(self, planned: PlannedTree) -> None:
        for creation in self._answers.creations:
            for work in creation.works:
                self._take(work, creation.name, planned.ancestors_of(creation.name))
        for move in self._answers.moves:
            self._move(move.work, [move.source], move.target)
        for addition in self._answers.additions:
            self._move(addition.work, [], addition.target)

    def _write_maps(self) -> None:
        for creation in self._answers.creations:
            self._create(creation)
        for link in self._answers.links:
            link.link()
        for unlink in self._answers.unlinks:
            unlink.unlink()

    def _take(self, work: str, target: str, ancestors: list[str]) -> None:
        sources = [name for name in self._movable_placements(work) if name in ancestors]
        self._move(work, sources, target)

    @staticmethod
    def _movable_placements(work: str) -> list[str]:
        note = Corpus().note(work)
        catalogue = AuthorCatalogue(Bibliographies())
        return [name for name in note.bibliographies if not catalogue.holds(note, name)]

    @staticmethod
    def _beneath(linked: set[str], planned: PlannedTree) -> list[str]:
        return [note.basename for note in Corpus().notes()
                if any(name in linked or linked.intersection(planned.ancestors_of(name)) for name in note.bibliographies)]

    def _deepen(self, work: str, planned: PlannedTree) -> None:
        subjects = self._movable_placements(work)
        above = {ancestor for name in subjects for ancestor in planned.ancestors_of(name)}
        sources = [name for name in subjects if name in above]
        deepest = [name for name in subjects if name not in above]
        if sources and deepest:
            self._move(work, sources, deepest[0])

    def _create(self, creation: Creation) -> None:
        directory = vault.BIBLIOGRAPHIES_DIR / FOLDER_OF_KIND[creation.kind]
        directory.mkdir(parents=True, exist_ok=True)
        vault.write_frontmatter(directory / f"{creation.name}.md", creation.meta(), creation.body())
        if creation.is_root:
            return
        parent = Bibliographies().named(creation.parent)
        NoteChange(parent, MapsList(parent.body).with_child(creation.name)).write()

    def _move(self, work: str, sources: list[str], target: str) -> None:
        FieldRewrite(Corpus().note(work)).moved(sources, target)
        held = Bibliographies().names()
        for source in sources:
            if source in held:
                self._unlist(source, work)
        for change in WorkPlacement(Corpus().note(work), Bibliographies()).plan():
            change.write()

    @staticmethod
    def _unlist(source: str, work: str) -> None:
        bibliography: Bibliography = Bibliographies().named(source)
        stripped = WorkListRemoval(bibliography.body).without(work)
        if stripped != bibliography.body:
            NoteChange(bibliography, stripped).write()

    def _report(self, applied: bool) -> dict:
        return {"created": [creation.name for creation in self._answers.creations],
                "moved": [{"work": move.work, "from": move.source, "to": move.target} for move in self._answers.moves],
                "linked": [link.summary() for link in self._answers.links],
                "unlinked": [unlink.summary() for unlink in self._answers.unlinks],
                "added": [addition.summary() for addition in self._answers.additions],
                "folded": [fold.summary(self._corpus, self._writing) for fold in self._answers.folds],
                "touched": self._answers.touched(), "works": self._answers.works(self._corpus),
                "questions": list(self._answers.questions), "applied": applied}
