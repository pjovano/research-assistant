from __future__ import annotations

import shutil
import time
from pathlib import Path

import vault

PARTIAL_SUFFIX = ".writing.tmp"
ENCODING = "utf-8"
BACKUPS_FOLDER = ".board-backups"
BACKUPS_KEPT = 30
STAMP = "%Y-%m-%d %H%M%S"


def save_text(path: Path, text: str) -> None:
    encoded = text.encode(ENCODING)
    with vault.ReplacementFile(path, PARTIAL_SUFFIX) as replacement:
        replacement.path.write_bytes(encoded)
        replacement.commit()


def save_board(path: Path, text: str) -> None:
    BoardBackups(path).keep()
    save_text(path, text)


class BoardBackups:
    def __init__(self, board: Path) -> None:
        self._board = board
        self._folder = board.parent / BACKUPS_FOLDER

    def held(self) -> list[Path]:
        return sorted(self._folder.glob(f"{self._board.stem} *{self._board.suffix}"))

    def keep(self) -> None:
        if not self._board.is_file() or not self._board.read_bytes().strip():
            return
        self._folder.mkdir(exist_ok=True)
        stamp = f"{time.strftime(STAMP)} {time.time_ns() % 10**9:09d}"
        shutil.copyfile(self._board, self._folder / f"{self._board.stem} {stamp}{self._board.suffix}")
        for old in self.held()[:-BACKUPS_KEPT]:
            old.unlink()
