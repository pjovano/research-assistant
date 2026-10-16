from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import vault

from _audit.scope import ENCODING, REPOSITORY_ROOT, ROOT_FILES, RepositoryPath

BACKTICKED = re.compile(r"`([^`\n]+)`")
DATED = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
PATH_PREFIXES = (".claude/", "lib/", "tests/", "skills/", "agents/", "library/", "research vault/", "~/")
PLACEHOLDER_MARKS = ("<", ">", "*", "?", "|")
VAULT_DIRECTORY_WITH_SPACE = "research vault/"
VAULT_PREFIXES = ("library/", VAULT_DIRECTORY_WITH_SPACE)
HOME_PREFIX = "~/"
FINDING_MISSING_PATH = "path-does-not-exist"
FINDING_FUTURE_DATE = "date-in-the-future"


class InstructionPointers:
    def __init__(self, paths: list[Path], today: date | None = None, root: Path = REPOSITORY_ROOT) -> None:
        self._paths = paths
        self._today = date.today() if today is None else today
        self._root = root

    def findings(self) -> list[dict]:
        return [finding for path in self._paths for finding in FilePointers(path, self._today, self._root).findings()]


class FilePointers:
    def __init__(self, path: Path, today: date, root: Path) -> None:
        self._path = path
        self._today = today
        self._root = root

    def findings(self) -> list[dict]:
        numbered = list(enumerate(self._path.read_text(encoding=ENCODING).splitlines(), start=1))
        return self._missing_paths(numbered) + self._future_dates(numbered)

    def _missing_paths(self, numbered: list[tuple[int, str]]) -> list[dict]:
        return [self._finding(number, FINDING_MISSING_PATH, token)
                for number, line in numbered for token in BACKTICKED.findall(line)
                if NamedPath(token, self._root).is_missing()]

    def _future_dates(self, numbered: list[tuple[int, str]]) -> list[dict]:
        return [self._finding(number, FINDING_FUTURE_DATE, match.group(0))
                for number, line in numbered for match in DATED.finditer(line)
                if self._is_future(match.group(0))]

    def _is_future(self, stamp: str) -> bool:
        try:
            return date.fromisoformat(stamp) > self._today
        except ValueError:
            return False

    def _finding(self, line: int, finding: str, detail: str) -> dict:
        return {"file": RepositoryPath(self._path, self._root).label(), "line": line, "finding": finding,
                "detail": detail}


class NamedPath:
    def __init__(self, token: str, root: Path = REPOSITORY_ROOT) -> None:
        self._token = self._first_field(token.strip())
        self._root = root

    @staticmethod
    def _first_field(token: str) -> str:
        return token if token.startswith(VAULT_DIRECTORY_WITH_SPACE) else token.split(" ")[0]

    def is_missing(self) -> bool:
        return self._names_a_path() and not self._exists()

    def _names_a_path(self) -> bool:
        if any(mark in self._token for mark in PLACEHOLDER_MARKS):
            return False
        return self._token in ROOT_FILES or self._token.startswith(PATH_PREFIXES)

    def _exists(self) -> bool:
        return self._path().exists()

    def _path(self) -> Path:
        if self._token.startswith(HOME_PREFIX):
            return Path(self._token).expanduser()
        if self._token.startswith(VAULT_PREFIXES):
            return vault.VAULT_ROOT / self._token
        return self._root / self._token
