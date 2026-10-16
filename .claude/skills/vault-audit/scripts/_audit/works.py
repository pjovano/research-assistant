from __future__ import annotations

import re
from pathlib import Path

from _audit.scope import ENCODING, REPOSITORY_ROOT, RepositoryPath

WORK_BASENAME = re.compile(r"[^\s`\"'(\[][^\n`\"']{0,60}? - (?:1[5-9]|20)\d{2}[a-z]? - [^\n`\"']{1,80}")
FINDING_NAMED_WORK = "work-named"


class NamedWorks:
    def __init__(self, paths: list[Path], root: Path = REPOSITORY_ROOT) -> None:
        self._paths = paths
        self._root = root

    def findings(self) -> list[dict]:
        return [finding for path in self._paths for finding in self._of_file(path)]

    def _of_file(self, path: Path) -> list[dict]:
        numbered = enumerate(path.read_text(encoding=ENCODING).splitlines(), start=1)
        return [self._finding(path, number, match.group(0).strip())
                for number, line in numbered for match in WORK_BASENAME.finditer(line)]

    def _finding(self, path: Path, line: int, detail: str) -> dict:
        return {"file": RepositoryPath(path, self._root).label(), "line": line, "finding": FINDING_NAMED_WORK,
                "detail": detail}
