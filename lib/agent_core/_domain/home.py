from __future__ import annotations

from pathlib import Path


class HomeRelative:
    def __init__(self, path: Path) -> None:
        self._path = path.expanduser().resolve()

    def text(self) -> str:
        home = Path.home().resolve()
        if self._path.is_relative_to(home):
            return f"~/{self._path.relative_to(home).as_posix()}"
        return self._path.as_posix()
