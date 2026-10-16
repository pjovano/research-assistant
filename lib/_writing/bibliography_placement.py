from __future__ import annotations

from pathlib import Path

from .linked_note import FIELD, LinkedNote
from .tree import ProjectTree
from .saved import save_text


class BibliographyPlacement:
    def __init__(self, tree: ProjectTree, name: str, bibliographies: list[str], held: set[str]) -> None:
        self._name = name
        self._file = PlacedFile(tree, name).path()
        self._bibliographies = bibliographies
        BibliographyChoice(bibliographies, held).check()

    def plan(self) -> dict:
        return {"note": self._name, "file": str(self._file), "field": self._bibliographies,
                "was": self._read().links(FIELD)}

    def apply(self) -> None:
        placed = self._read().with_links(FIELD, self._bibliographies)
        save_text(self._file, placed.text)

    def _read(self) -> LinkedNote:
        return LinkedNote.parsed(self._file.read_text(encoding="utf-8"))


class PlacedFile:
    def __init__(self, tree: ProjectTree, name: str) -> None:
        self._tree = tree
        self._name = name

    def path(self) -> Path:
        candidates = [path for path in (self._tree.folders.atomic_note(self._name),
                                        self._tree.folders.project_file(self._name)) if path.is_file()]
        if not candidates:
            raise ValueError(f"no atomic note or project file named {self._name!r}")
        if len(candidates) > 1:
            raise ValueError(f"{self._name!r} names an atomic note and a project file: rename one in Obsidian")
        return candidates[0]


class BibliographyChoice:
    def __init__(self, bibliographies: list[str], held: set[str]) -> None:
        self._bibliographies = bibliographies
        self._held = held

    def check(self) -> None:
        if not self._bibliographies:
            raise ValueError("name at least one bibliography")
        if len(set(self._bibliographies)) < len(self._bibliographies):
            raise ValueError("a bibliography is named once")
        unknown = [name for name in self._bibliographies if name not in self._held]
        if unknown:
            raise ValueError(f"not a bibliography: {unknown}")
