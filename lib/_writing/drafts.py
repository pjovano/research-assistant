from __future__ import annotations

import re
from pathlib import Path

VERSION_RE = re.compile(r"^(?:(?P<section>.+) - )?v(?P<version>\d+)$")
FIRST_VERSION = 1
MARKDOWN_SUFFIX = ".md"


class DraftName:
    def __init__(self, project: str, section: str | None, version: int) -> None:
        self.project = project
        self.section = section
        self.version = version

    @classmethod
    def parsed(cls, project: str, filename: str) -> "DraftName | None":
        prefix = f"{project} - "
        stem = filename.removesuffix(MARKDOWN_SUFFIX)
        if not (filename.endswith(MARKDOWN_SUFFIX) and stem.startswith(prefix)):
            return None
        hit = VERSION_RE.match(stem.removeprefix(prefix))
        return cls(project, hit.group("section"), int(hit.group("version"))) if hit else None

    @property
    def basename(self) -> str:
        middle = f"{self.section} - " if self.section else ""
        return f"{self.project} - {middle}v{self.version:02d}"

    @property
    def filename(self) -> str:
        return self.basename + MARKDOWN_SUFFIX

    def following(self) -> "DraftName":
        return DraftName(self.project, self.section, self.version + 1)


class DraftShelf:
    def __init__(self, directory: Path, projects: list[str]) -> None:
        self.directory = directory
        self._projects = sorted(projects, key=len, reverse=True)

    def of(self, project: str) -> list[DraftName]:
        names = [self._owned(path.name) for path in self._files()]
        owned = [name for name in names if name and name.project == project]
        return sorted(owned, key=lambda name: (name.section or "", name.version))

    def path(self, name: DraftName) -> Path:
        return self.directory / name.filename

    def _owned(self, filename: str) -> DraftName | None:
        parsed = (DraftName.parsed(project, filename) for project in self._projects)
        return next((name for name in parsed if name), None)

    def _files(self) -> list[Path]:
        return sorted(self.directory.glob(f"*{MARKDOWN_SUFFIX}")) if self.directory.is_dir() else []


class Drafts:
    def __init__(self, project: str, shelf: DraftShelf) -> None:
        self._project = project
        self._shelf = shelf

    def all(self) -> list[DraftName]:
        return self._shelf.of(self._project)

    def latest(self, section: str | None) -> DraftName | None:
        versions = [name for name in self.all() if name.section == section]
        return versions[-1] if versions else None

    def next(self, section: str | None) -> DraftName:
        latest = self.latest(section)
        return latest.following() if latest else DraftName(self._project, section, FIRST_VERSION)

    def path(self, name: DraftName) -> Path:
        return self._shelf.path(name)
