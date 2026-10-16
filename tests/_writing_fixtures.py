from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

from _writing.actions import ProjectCreation
from _writing.placement import NoteCreation
from _writing.project_file import ProjectFile
from _writing.tree import ProjectTree, WritingFolders

THESIS = "Historical Essays on Transcendental Logic"
PAPER = "Kant's Critique of Mathematical Reason"
SHORT = "Kant"
LONGER = "Kant - Critique"
CLAIM = "Construction concerns the form of a proof, not the existence of an object"
OTHER_CLAIM = "Concepts without intuitions cannot yield mathematical cognition"
IDEA = "Construction as proof"
OTHER_IDEA = "Concepts and intuitions"
INTRODUCTION = "§1 Introduction"
ARGUMENT = "§2 Construction as proof"
SUBSECTION = "§2.1 Construction and existence"


class WritingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.writing_dir = Path(tempfile.mkdtemp()) / "writing"
        self.addCleanup(shutil.rmtree, self.writing_dir.parent, ignore_errors=True)
        self.folders = WritingFolders(self.writing_dir)

    def tree(self) -> ProjectTree:
        return ProjectTree(self.folders)

    def create(self, name: str, parent: str | None = None) -> None:
        ProjectCreation(self.tree(), name, parent).apply()

    def draft(self, filename: str, text: str = "") -> Path:
        path = self.folders.drafts / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def project_file(self, name: str) -> ProjectFile:
        return self.tree().named(name).read()

    def note(self, title: str = IDEA) -> None:
        NoteCreation(self.folders, title).apply()
