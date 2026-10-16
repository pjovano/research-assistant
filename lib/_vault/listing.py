from __future__ import annotations

import re
from pathlib import Path

import yaml

from _vault.frontmatter import NoteHeader
from _vault.locating import PDF_SUFFIX

NOTE_SUFFIX = ".md"
CITEKEY_FIELD = "citekey"

_NUMBERED_COPY_RE = re.compile(r"^(?P<original>.+) \d+$")
_CONFLICTED_COPY = "conflicted copy"


class ConflictCopy:
    def __init__(self, path: Path, notes_directory: Path | None = None) -> None:
        self._path = path
        self._notes_directory = notes_directory

    @property
    def is_copy(self) -> bool:
        return self._is_named_conflicted() or self._is_numbered_copy_of_its_original()

    def _is_named_conflicted(self) -> bool:
        return _CONFLICTED_COPY in self._path.stem.lower()

    def _is_numbered_copy_of_its_original(self) -> bool:
        original = self._numbered_original()
        return original is not None and not self._is_distinct_work_beside(original)

    def _numbered_original(self) -> Path | None:
        numbered = _NUMBERED_COPY_RE.match(self._path.stem)
        if not numbered:
            return None
        original = self._path.parent / f"{numbered.group('original')}{self._path.suffix}"
        return original if original.exists() else None

    def _is_distinct_work_beside(self, original: Path) -> bool:
        if self._path.suffix == PDF_SUFFIX:
            return self._has_a_note_of_its_own()
        return NoteRecord(self._path).names_another_record_than(NoteRecord(original))

    def _has_a_note_of_its_own(self) -> bool:
        if self._notes_directory is None:
            return False
        note = self._notes_directory / f"{self._path.stem}{NOTE_SUFFIX}"
        return note.exists() and not ConflictCopy(note).is_copy


class NoteRecord:
    def __init__(self, path: Path) -> None:
        self._path = path

    def names_another_record_than(self, other: NoteRecord) -> bool:
        mine, theirs = self.citekey, other.citekey
        return bool(mine) and bool(theirs) and mine != theirs

    @property
    def citekey(self) -> str | None:
        try:
            frontmatter = NoteHeader(self._path).frontmatter()
        except yaml.YAMLError:
            return None
        return frontmatter.get(CITEKEY_FIELD) if isinstance(frontmatter, dict) else None


class VaultTree:
    def __init__(self, directory: Path, folders_apart: tuple[str, ...] = ()) -> None:
        self._directory = directory
        self._folders_apart = folders_apart

    def markdown(self) -> list[Path]:
        return [path for path in self._all_markdown() if not ConflictCopy(path).is_copy]

    def conflict_copies(self) -> list[Path]:
        return [path for path in self._all_markdown() if ConflictCopy(path).is_copy]

    def _all_markdown(self) -> list[Path]:
        if not self._directory.exists():
            return []
        return [path for path in sorted(self._directory.rglob(f"*{NOTE_SUFFIX}")) if not self._is_apart(path)]

    def _is_apart(self, path: Path) -> bool:
        top_folder = path.relative_to(self._directory).parts[0]
        return top_folder in self._folders_apart


class VaultDirectory:
    def __init__(self, directory: Path, notes_directory: Path | None = None) -> None:
        self._directory = directory
        self._notes_directory = notes_directory

    def markdown(self) -> list[Path]:
        return self._originals(NOTE_SUFFIX)

    def pdfs(self) -> list[Path]:
        return self._originals(PDF_SUFFIX)

    def conflict_copies(self) -> list[Path]:
        held = self._all_with_suffix(NOTE_SUFFIX) + self._all_with_suffix(PDF_SUFFIX)
        return [path for path in held if self._is_copy(path)]

    def _originals(self, suffix: str) -> list[Path]:
        return [path for path in self._all_with_suffix(suffix) if not self._is_copy(path)]

    def _is_copy(self, path: Path) -> bool:
        return ConflictCopy(path, self._notes_directory).is_copy

    def _all_with_suffix(self, suffix: str) -> list[Path]:
        if not self._directory.exists():
            return []
        return sorted(self._directory.glob(f"*{suffix}"))
