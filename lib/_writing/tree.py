from __future__ import annotations

from pathlib import Path

import vault

from .drafts import MARKDOWN_SUFFIX, Drafts, DraftShelf
from .project_file import DRAFTED, DRAFTS, Change, ProjectFile
from .saved import save_board

NOTES_FOLDER = vault.ATOMIC_NOTES_FOLDER
PROJECTS_FOLDER = vault.PROJECT_FILES_FOLDER
DRAFTS_FOLDER = "3 drafts"
PUBLISHED_FOLDER = "4 published"


class WritingFolders:
    def __init__(self, writing_dir: Path) -> None:
        self.notes = writing_dir / NOTES_FOLDER
        self.projects = writing_dir / PROJECTS_FOLDER
        self.drafts = writing_dir / DRAFTS_FOLDER
        self.published = writing_dir / PUBLISHED_FOLDER
        self.reading_lists = writing_dir.parent / vault.BIBLIOGRAPHIES_FOLDER / vault.READING_LISTS_FOLDER
    def note(self, basename: str) -> Path:
        candidates = (folder / f"{basename}{MARKDOWN_SUFFIX}" for folder in (self.drafts, self.published, self.notes))
        found = next((path for path in candidates if path.is_file()), None)
        if found is None:
            raise ValueError(f"no draft, published piece, or note named {basename!r}")
        return found

    def atomic_note(self, title: str) -> Path:
        return self.notes / f"{title}{MARKDOWN_SUFFIX}"

    def project_file(self, name: str) -> Path:
        return self.projects / f"{name}{MARKDOWN_SUFFIX}"


class Project:
    def __init__(self, file: Path, drafts: Drafts) -> None:
        self.file = file
        self.drafts = drafts

    @property
    def name(self) -> str:
        return self.file.stem

    @property
    def status(self) -> str | None:
        return self.read().status

    def read(self) -> ProjectFile:
        return ProjectFile(self.file.read_text(encoding="utf-8"))

    def write(self, project_file: ProjectFile) -> None:
        save_board(self.file, project_file.text)

    def list_first_under_drafts(self, basename: str) -> None:
        listed = self.read().with_line_first(DRAFTS, f"- [[{basename}]]")
        self.write(listed.with_changes([Change.of_note(DRAFTED, basename)]))

    def parent_names(self) -> list[str]:
        return self.read().parents

    def child_names(self) -> list[str]:
        return self.read().children

    def list_parent(self, name: str) -> None:
        self.write(self.read().with_parent(name))

    def list_child(self, name: str) -> None:
        self.write(self.read().with_child(name))


class ProjectTree:
    def __init__(self, folders: WritingFolders) -> None:
        self.folders = folders
        files = self._project_files()
        shelf = DraftShelf(folders.drafts, [file.stem for file in files])
        self._by_name = {file.stem: Project(file, Drafts(file.stem, shelf)) for file in files}

    def all(self) -> list[Project]:
        return list(self._by_name.values())

    def holds(self, name: str) -> bool:
        return name in self._by_name

    def named(self, name: str) -> Project:
        try:
            return self._by_name[name]
        except KeyError:
            raise ValueError(f"no project file named {name!r} in {self.folders.projects}") from None

    def children(self, project: Project) -> list[Project]:
        return self._held(project.child_names())

    def parents(self, project: Project) -> list[Project]:
        return self._held(project.parent_names())

    def one_sided_links(self, project: Project) -> list[str]:
        unlisting_parents = [parent.name for parent in self.parents(project)
                             if project.name not in parent.child_names()]
        unlisting_children = [child.name for child in self.children(project)
                              if project.name not in child.parent_names()]
        return ([f"{name} does not list it among its children" for name in unlisting_parents]
                + [f"{name} does not list it among its parents" for name in unlisting_children])

    def _held(self, names: list[str]) -> list[Project]:
        return [self._by_name[name] for name in names if name in self._by_name]

    def _project_files(self) -> list[Path]:
        if not self.folders.projects.is_dir():
            return []
        return sorted(self.folders.projects.glob(f"*{MARKDOWN_SUFFIX}"))
