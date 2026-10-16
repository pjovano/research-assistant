from __future__ import annotations

import shutil
from pathlib import Path

from .board_file import BoardFile, BoardState
from .board_sync import BoardSync
from .drafts import MARKDOWN_SUFFIX
from .names import NoteName
from .project_file import ProjectFile
from .tree import Project, ProjectTree
from .saved import save_board


class ProjectCreation:
    def __init__(self, tree: ProjectTree, name: str, parent: str | None) -> None:
        self._tree = tree
        self._name = NoteName(name).checked()
        self._parent = tree.named(parent) if parent else None
        self._file = tree.folders.project_file(self._name)
        if tree.holds(self._name) or self._file.exists():
            raise ValueError(f"a project file named {self._name!r} exists: choose another name")

    def plan(self) -> dict:
        return {"project": self._name, "file": str(self._file),
                "parent": self._parent.name if self._parent else None}

    def apply(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        board = BoardFile(self._blank().text).written([], BoardState())
        save_board(self._file, board)
        folders = self._tree.folders
        BoardSync(ProjectTree(folders).named(self._name), folders).apply()
        if self._parent:
            self._parent.list_child(self._name)

    def _blank(self) -> ProjectFile:
        blank = ProjectFile.blank(self._name)
        return blank.with_parent(self._parent.name) if self._parent else blank


class ProjectLink:
    def __init__(self, tree: ProjectTree, parent: str, child: str) -> None:
        if parent == child:
            raise ValueError(f"{parent!r} is never its own parent")
        self._parent = tree.named(parent)
        self._child = tree.named(child)

    def plan(self) -> dict:
        return {"parent": self._parent.name, "child": self._child.name}

    def apply(self) -> None:
        self._parent.list_child(self._child.name)
        self._child.list_parent(self._parent.name)


class DraftCut:
    def __init__(self, project: Project, section: str | None) -> None:
        self._project = project
        self._source = project.drafts.latest(section)
        self._target = project.drafts.next(section)

    def plan(self) -> dict:
        source = str(self._project.drafts.path(self._source)) if self._source else None
        return {"project": self._project.name, "draft": str(self._project.drafts.path(self._target)),
                "copied_from": source}

    def apply(self) -> None:
        self._write(self._project.drafts.path(self._target))
        self._project.list_first_under_drafts(self._target.basename)

    def _write(self, target: Path) -> None:
        if target.exists():
            raise ValueError(f"{target} exists: a draft is never overwritten")
        target.parent.mkdir(parents=True, exist_ok=True)
        if self._source:
            shutil.copyfile(self._project.drafts.path(self._source), target)
        else:
            target.write_text("", encoding="utf-8")


class Publication:
    def __init__(self, tree: ProjectTree, project: str, title: str) -> None:
        self._project = tree.named(project)
        self._title = NoteName(title).checked()
        self._source = self._project.drafts.latest(None)
        self._target = tree.folders.published / f"{self._title}{MARKDOWN_SUFFIX}"
        PublicationChecks(tree, self._source, self._target).run()

    def plan(self) -> dict:
        return {"project": self._project.name, "published": str(self._target),
                "copied_from": str(self._project.drafts.path(self._source))}

    def apply(self) -> None:
        self._target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._project.drafts.path(self._source), self._target)
        self._project.list_first_under_drafts(self._title)


class PublicationChecks:
    def __init__(self, tree: ProjectTree, source, target: Path) -> None:
        self._tree = tree
        self._source = source
        self._target = target

    def run(self) -> None:
        if self._source is None:
            raise ValueError("the project has no whole draft: cut one before publishing")
        if self._tree.holds(self._target.stem):
            raise ValueError(f"{self._target.stem!r} names a project file: a published piece takes its own title")
        if self._target.exists():
            raise ValueError(f"{self._target} exists: a published piece is never overwritten")
