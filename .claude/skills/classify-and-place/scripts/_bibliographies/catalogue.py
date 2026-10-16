from __future__ import annotations

from .notes import Bibliographies, CorpusNote
from .placement import PRIMARY_ROLE
from .tree import BibliographyTree


class AuthorCatalogue:
    def __init__(self, bibliographies: Bibliographies, created: dict[str, str] | None = None) -> None:
        self._author_of = {entry.name: entry.author for entry in bibliographies.entries() if entry.author is not None}
        self._author_of.update({name: author.lower() for name, author in (created or {}).items()})

    def holds(self, note: CorpusNote, name: str) -> bool:
        author = self._author_of.get(name)
        return author is not None and author in {creator.lower() for creator in note.authors}

    def maps_of(self, note: CorpusNote) -> list[str]:
        return sorted(name for name in self._author_of if self.holds(note, name))

    def missing_from(self, note: CorpusNote) -> list[str]:
        return [name for name in self.maps_of(note) if name not in note.bibliographies]

    def holds_alone(self, note: CorpusNote) -> bool:
        return note.source_role == PRIMARY_ROLE and bool(self.maps_of(note))

    def admits(self, note: CorpusNote, name: str) -> bool:
        return self.holds(note, name) or not self.holds_alone(note)

    def strays_of(self, note: CorpusNote) -> list[str]:
        return [name for name in note.bibliographies if not self.admits(note, name)]


class MostSpecificField:
    def __init__(self, catalogue: list[str], tree: BibliographyTree) -> None:
        self._catalogue = catalogue
        self._tree = tree

    def keeps_to_the_catalogue(self, source_role: str | None) -> bool:
        return source_role == PRIMARY_ROLE and bool(self._catalogue)

    def of(self, names: list[str], source_role: str | None) -> list[str]:
        if self.keeps_to_the_catalogue(source_role):
            return list(self._catalogue)
        named = list(dict.fromkeys([*self._catalogue, *names]))
        subjects = [name for name in named if name not in self._catalogue]
        above = {ancestor for name in subjects for ancestor in self._tree.ancestors_of(name)}
        return [name for name in named if name in self._catalogue or name not in above]
