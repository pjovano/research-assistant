from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import bibliographies
import vault
from _vaults import TempVault

PLACEMENT_DIRS = ("CORPUS_DIR", "TRANSCRIPTS_DIR", "BIBLIOGRAPHIES_DIR")
PRIMARY_WORKS_HEADING = "Primary works"
SECONDARY_WORKS_HEADING = "Secondary literature"
EMPTY_SECTION_MARKER = "*(none)*"
MAPS_HEADING = bibliographies.MAPS_HEADING
HEGEL = "Hegel - 1969 - Wissenschaft der Logik"
HOULGATE = "Houlgate - 2006 - The Opening of Hegel's Logic"
PIPPIN_TALK = "Pippin - 2019 - Hegel on Logic as Metaphysics"


class TemporaryVault:
    def __init__(self, case: unittest.TestCase) -> None:
        self._vault = TempVault(*PLACEMENT_DIRS).activate()
        case.addCleanup(self._vault.discard)
        self._notes = self._vault.corpus
        self._bibliographies = vault.BIBLIOGRAPHIES_DIR

    def note(self, basename: str, **meta) -> None:
        vault.write_frontmatter(self._notes / f"{basename}.md", meta, "")

    def transcript(self, basename: str, **meta) -> None:
        vault.write_frontmatter(vault.TRANSCRIPTS_DIR / f"{basename}.md", {**meta, "source_type": "transcript"}, "")

    def bibliography(self, name: str, body: str = "", **meta) -> None:
        vault.write_frontmatter(self._bibliographies / f"{name}.md", meta, body)

    def parent_of(self, name: str, *children: str, **meta) -> None:
        listed = "\n".join(f"- [[{child}]]" for child in children)
        self.bibliography(name, f"## {MAPS_HEADING}\n\n{listed}\n", **meta)

    def bibliography_in(self, folder: str, name: str, body: str = "", **meta) -> None:
        directory = self._bibliographies / folder
        directory.mkdir(parents=True, exist_ok=True)
        vault.write_frontmatter(directory / f"{name}.md", meta, body)

    def body_in(self, folder: str, name: str) -> str:
        return vault.read_frontmatter(self._bibliographies / folder / f"{name}.md")[1]

    def raw_bibliography(self, name: str, text: str) -> Path:
        path = self._bibliographies / f"{name}.md"
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def raw_note(self, name: str, text: str) -> None:
        (self._notes / f"{name}.md").write_text(text, encoding="utf-8", newline="\n")

    def writing_note(self, folder: str, name: str, text: str) -> Path:
        directory = vault.WRITING_DIR / folder
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{name}.md"
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def body_of(self, name: str) -> str:
        return vault.read_frontmatter(self._bibliographies / f"{name}.md")[1]

    def named(self, name: str) -> bibliographies.Bibliography:
        return bibliographies.Bibliographies().named(name)

    def tree(self) -> bibliographies.BibliographyTree:
        return bibliographies.BibliographyTree(bibliographies.Bibliographies().entries())

    def plan_for(self, basename: str) -> list[bibliographies.NoteChange]:
        note = bibliographies.Corpus().note(basename)
        return bibliographies.WorkPlacement(note, bibliographies.Bibliographies()).plan()

    def place(self, basename: str) -> None:
        for change in self.plan_for(basename):
            change.write()

    def report(self) -> bibliographies.Report:
        return bibliographies.ReportBuilder(bibliographies.Bibliographies(), bibliographies.Corpus(),
                                            bibliographies.Writing()).build()

    def printed_report(self) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.report().print()
        return buffer.getvalue()


def works_section(*lines: str) -> str:
    return "\n".join([f"## {SECONDARY_WORKS_HEADING}", "", *lines, ""])
