from __future__ import annotations

from pathlib import Path

PDF_SUFFIX = ".pdf"


class PdfSearch:
    def __init__(self, given: str, directories: tuple[Path, ...]) -> None:
        self._given = given
        self._directories = directories

    def found(self) -> Path | None:
        return next((candidate for candidate in self._candidates()
                     if self._is_pdf_file(candidate) and self._lies_in_a_directory(candidate)), None)

    def _candidates(self) -> list[Path]:
        return ([Path(self._given)] + [directory / self._given for directory in self._directories]
                + [directory / f"{self._given}{PDF_SUFFIX}" for directory in self._directories])

    def _lies_in_a_directory(self, candidate: Path) -> bool:
        parent = candidate.resolve().parent
        return any(parent == directory.resolve() for directory in self._directories)

    @staticmethod
    def _is_pdf_file(candidate: Path) -> bool:
        return candidate.suffix.lower() == PDF_SUFFIX and candidate.is_file()
