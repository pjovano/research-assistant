from __future__ import annotations

from pathlib import Path

import vault

from .sections import Section

MAPS_HEADING = "Maps"
SECONDARY_ROLE = "secondary"


class NoteNotFound(LookupError):
    pass


def maps_listed_in(body: str) -> list[str]:
    lines = Section(MAPS_HEADING).lines_in(body)
    targets = (vault.wikilink_target(line) for line in lines)
    return [vault.nfc(target) for target in targets if target]


class BibliographyNotFound(LookupError):
    pass


class CorpusNote:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.basename = vault.basename_of(path)
        self.meta = vault.read_frontmatter_only(path)
        self.is_transcript = path.parent == vault.TRANSCRIPTS_DIR

    @property
    def bibliographies(self) -> list[str]:
        return [vault.nfc(topic) for topic in vault.field_topics(self.meta)]

    @property
    def source_role(self) -> str | None:
        return self.meta.get("source_role")

    @property
    def source_type(self) -> str | None:
        return self.meta.get("source_type")

    @property
    def authors(self) -> list[str]:
        listed = self.meta.get("author") or []
        names = [listed] if isinstance(listed, str) else listed
        return [vault.nfc(str(name)) for name in names]

    @property
    def commentary_target(self) -> str | None:
        return vault.commentary_target(self.meta)


class Bibliography:
    def __init__(self, path: Path) -> None:
        self.name = vault.basename_of(path)
        self.folder = path.parent.name
        self._stored = vault.GuardedNote(path)
        self.meta, self.body = vault.parse_note(self._stored.text())

    @property
    def children(self) -> list[str]:
        return maps_listed_in(self.body)

    @property
    def author(self) -> str | None:
        given = self.meta.get("author")
        names = [str(name) for name in (given if isinstance(given, list) else [given]) if name]
        return names[0].lower() if names else None

    @property
    def aliases(self) -> list[str]:
        given = self.meta.get("aliases") or []
        return [str(alias) for alias in (given if isinstance(given, list) else [given])]

    def summary(self) -> dict:
        return {"name": self.name, "folder": self.folder, "author": self.author, "aliases": self.aliases,
                "maps": self.children}

    def write(self, body: str) -> None:
        frontmatter_block, _old_body = vault.split_note(self._stored.text())
        self._stored.replace(vault.join_note(frontmatter_block, body))

    def delete(self) -> None:
        self._stored.remove()


class NoteChange:
    def __init__(self, note: Bibliography, new_body: str) -> None:
        self._note = note
        self._new_body = new_body

    @property
    def name(self) -> str:
        return self._note.name

    def write(self) -> None:
        self._note.write(self._new_body)


class Corpus:
    def __init__(self) -> None:
        self._notes: list[CorpusNote] | None = None

    def notes(self) -> list[CorpusNote]:
        if self._notes is None:
            self._notes = [CorpusNote(path) for path in vault.list_held_notes()]
        return list(self._notes)

    def basenames(self) -> set[str]:
        return {vault.basename_of(path) for path in vault.list_held_notes()}

    def conflict_copies(self) -> list[str]:
        directories = (vault.CORPUS_DIR, vault.TRANSCRIPTS_DIR)
        return [path.name for directory in directories for path in vault.conflict_copies(directory)]

    def note(self, basename: str) -> CorpusNote:
        path = vault.held_note_path(basename)
        if not path.exists():
            raise NoteNotFound(f"no corpus file or transcript named {basename!r}")
        return CorpusNote(path)


class WritingNote:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.basename = vault.basename_of(path)
        self.meta = vault.read_frontmatter_only(path)

    @property
    def bibliographies(self) -> list[str]:
        return [vault.nfc(topic) for topic in vault.field_topics(self.meta)]


class Writing:
    def notes(self) -> list[WritingNote]:
        return [WritingNote(path) for path in vault.list_placed_writing()]

    def placed_on(self, name: str) -> list[WritingNote]:
        return [note for note in self.notes() if name in note.bibliographies]


class Bibliographies:
    def __init__(self) -> None:
        self._entries = [Bibliography(path) for path in vault.list_bibliographies()]

    def entries(self) -> list[Bibliography]:
        return list(self._entries)

    def names(self) -> set[str]:
        return {entry.name for entry in self._entries}

    def authors(self) -> set[str]:
        return {entry.author for entry in self._entries if entry.author is not None}

    def conflict_copies(self) -> list[str]:
        return [path.name for path in vault.bibliography_conflict_copies()]

    def named(self, name: str) -> Bibliography:
        for entry in self._entries:
            if entry.name == name:
                return entry
        raise BibliographyNotFound(f"field: names [[{name}]], which is not a bibliography")
