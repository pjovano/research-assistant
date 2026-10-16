from __future__ import annotations

import os
from pathlib import Path

NOTE_TEMPORARY_SUFFIX = ".partial"
_ENCODING = "utf-8"


class ReplacementFile:
    def __init__(self, target: Path, suffix: str) -> None:
        self._target = target
        self._partial = target.with_suffix(suffix)
        self._committed = False

    @property
    def path(self) -> Path:
        return self._partial

    def commit(self) -> None:
        self._flush_to_disk()
        self._partial.replace(self._target)
        self._committed = True

    def _flush_to_disk(self) -> None:
        descriptor = os.open(self._partial, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def __enter__(self) -> ReplacementFile:
        return self

    def __exit__(self, *_exception) -> None:
        if not self._committed:
            self._partial.unlink(missing_ok=True)


class NoteChangedOnDisk(RuntimeError):
    def __init__(self, path: Path, refusal: str) -> None:
        super().__init__(f"{path} {refusal}")
        self.path = path


class GuardedNote:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._snapshot: bytes | None = None

    def text(self) -> str:
        if self._snapshot is None:
            self._snapshot = self._path.read_bytes()
        return self._snapshot.decode(_ENCODING)

    def replace(self, text: str) -> None:
        self._require_unchanged()
        content = text.encode(_ENCODING)
        with ReplacementFile(self._path, NOTE_TEMPORARY_SUFFIX) as replacement:
            replacement.path.write_bytes(content)
            replacement.commit()
        self._snapshot = content

    def remove(self) -> None:
        self.text()
        self._require_unchanged()
        self._path.unlink()

    def _require_unchanged(self) -> None:
        if self._snapshot is not None and self._bytes_on_disk() != self._snapshot:
            raise NoteChangedOnDisk(self._path, "changed on disk after it was read; nothing was written. "
                                                "Run the command again so it reads the current file.")

    def _bytes_on_disk(self) -> bytes | None:
        try:
            return self._path.read_bytes()
        except FileNotFoundError:
            return None
