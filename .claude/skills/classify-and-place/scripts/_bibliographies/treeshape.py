from __future__ import annotations

from .glossing import TOPICS_FOLDER
from .notes import Bibliographies, Bibliography, CorpusNote
from .tree import BibliographyTree


class TreeShape:
    def __init__(self, bibliographies: Bibliographies, notes: list[CorpusNote]) -> None:
        self._entries = {entry.name: entry for entry in bibliographies.entries()}
        self._tree = BibliographyTree(bibliographies.entries())
        self._notes = [note for note in notes if not note.is_transcript]

    def author_maps(self) -> list[dict]:
        return [self._author_map(entry) for name, entry in sorted(self._entries.items()) if entry.author is not None]

    def unlinked_subtopics(self) -> list[dict]:
        return [{"name": name, "parents": self._tree.parents_of(name)}
                for name, entry in sorted(self._entries.items()) if self._hangs_from_authors_alone(entry)]

    def _author_map(self, entry: Bibliography) -> dict:
        beneath = self._subtree(entry.name)
        works = [note for note in self._notes if beneath.intersection(note.bibliographies)]
        own = [note for note in works if entry.author in {author.lower() for author in note.authors}]
        return {"name": entry.name, "author": entry.author, "parents": self._tree.parents_of(entry.name),
                "own_works": len(own), "works_by_others": len(works) - len(own),
                "works": sorted(note.basename for note in own)}

    def _subtree(self, name: str) -> set[str]:
        reached, frontier = {name}, [name]
        while frontier:
            children = [child for parent in frontier for child in self._children(parent) if child not in reached]
            reached.update(children)
            frontier = children
        return reached

    def _children(self, name: str) -> list[str]:
        entry = self._entries.get(name)
        return entry.children if entry is not None else []

    def _hangs_from_authors_alone(self, entry: Bibliography) -> bool:
        parents = [self._entries.get(parent) for parent in self._tree.parents_of(entry.name)]
        is_topic = entry.folder == TOPICS_FOLDER
        return is_topic and bool(parents) and all(parent is not None and parent.author for parent in parents)
