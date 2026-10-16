from __future__ import annotations

from .atomic_note import AtomicNote
from .names import NoteName
from .project_file import HEADINGS_BY_NAME, STATUSES
from .tree import Project, WritingFolders
from .saved import save_text


class NoteCreation:
    def __init__(self, folders: WritingFolders, title: str) -> None:
        self._title = NoteName(title).checked()
        self._file = folders.atomic_note(self._title)
        if self._file.exists():
            raise ValueError(f"a note named {self._title!r} exists: add its lines there, or title the idea apart")

    def plan(self) -> dict:
        return {"note": str(self._file)}

    def apply(self) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        save_text(self._file, AtomicNote.blank().text)


class HeadingLine:
    def __init__(self, project: Project, heading_name: str, line: str) -> None:
        if heading_name not in HEADINGS_BY_NAME:
            raise ValueError(f"a heading is one of {sorted(HEADINGS_BY_NAME)}")
        self._project = project
        self._heading = HEADINGS_BY_NAME[heading_name]
        self._line = line.strip()

    def plan(self) -> dict:
        return {"project": self._project.name, "heading": self._heading, "line": self._line}

    def apply(self) -> None:
        self._project.write(self._project.read().with_line_last(self._heading, self._line))


class StatusChange:
    def __init__(self, project: Project, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(f"a status is one of {list(STATUSES)}")
        self._project = project
        self._status = status

    def plan(self) -> dict:
        return {"project": self._project.name, "status": self._status, "was": self._project.status}

    def apply(self) -> None:
        self._project.write(self._project.read().with_status(self._status))
