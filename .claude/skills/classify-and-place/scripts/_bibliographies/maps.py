from __future__ import annotations

from dataclasses import dataclass

import vault

from .notes import MAPS_HEADING, Bibliographies, NoteChange
from .sections import EMPTY_SECTION_MARKER, Section
from .tree import BibliographyTree


def wikilink(target: str) -> str:
    return f"[[{target}]]"


class MapsList:
    def __init__(self, body: str) -> None:
        self._body = body

    def with_child(self, name: str) -> str:
        lines = self._lines()
        if any(vault.wikilink_target(line) == name for line in lines):
            return self._body
        kept = [line for line in lines if line.strip() and line.strip() != EMPTY_SECTION_MARKER]
        listed = sorted([*kept, f"- {wikilink(name)}"], key=lambda line: (vault.wikilink_target(line) or line).casefold())
        return self._with(listed)

    def without_child(self, name: str) -> str:
        lines = self._lines()
        kept = [line for line in lines if line.strip() and vault.wikilink_target(line) != name]
        return self._body if len(kept) == len([line for line in lines if line.strip()]) else self._with(kept)

    def _lines(self) -> list[str]:
        return Section(MAPS_HEADING).content_in(self._body).split("\n")

    def _with(self, listed: list[str]) -> str:
        content = "\n" + "\n".join(listed) + "\n" if listed else "\n"
        return Section(MAPS_HEADING).with_content(self._body, content)


@dataclass(frozen=True)
class MapLink:
    name: str
    parent: str

    @classmethod
    def of(cls, given: dict) -> MapLink:
        return cls(vault.nfc(str(given.get("name") or "")).strip(), vault.nfc(str(given.get("parent") or "")).strip())

    def summary(self) -> dict:
        return {"name": self.name, "parent": self.parent}

    def link(self) -> None:
        parent = Bibliographies().named(self.parent)
        NoteChange(parent, MapsList(parent.body).with_child(self.name)).write()

    def unlink(self) -> None:
        parent = Bibliographies().named(self.parent)
        NoteChange(parent, MapsList(parent.body).without_child(self.name)).write()


class PlannedTree:
    def __init__(self, parents: dict[str, set[str]]) -> None:
        self._parents = parents

    @classmethod
    def planned(cls, tree: BibliographyTree, created: dict[str, str | None], links: list[MapLink],
                unlinks: list[MapLink]) -> PlannedTree:
        parents = {name: set(tree.parents_of(name)) for name in tree.names()}
        parents.update({name: {parent} if parent else set() for name, parent in created.items()})
        for link in links:
            parents.setdefault(link.name, set()).add(link.parent)
        for unlink in unlinks:
            parents.get(unlink.name, set()).discard(unlink.parent)
        return cls(parents)

    def parents_of(self, name: str) -> list[str]:
        return sorted(self._parents.get(name, set()))

    def ancestors_of(self, name: str) -> list[str]:
        ancestors: list[str] = []
        parents = self.parents_of(name)
        while parents:
            unseen = [parent for parent in parents if parent not in ancestors]
            ancestors.extend(unseen)
            parents = [above for parent in unseen for above in self.parents_of(parent)]
        return ancestors

    def sits_beneath_itself(self, name: str) -> bool:
        return name in self.ancestors_of(name)
