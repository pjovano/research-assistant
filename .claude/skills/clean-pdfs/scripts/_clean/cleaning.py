from __future__ import annotations

from pathlib import Path

import pymupdf
from vault import ReplacementFile

from .repair import QpdfRepair
from .verification import GuttingCheck

DAMAGED_FILE_ERRORS = (pymupdf.FileDataError, pymupdf.mupdf.FzErrorBase, ValueError)
TEMPORARY_SUFFIX = ".clean.tmp.pdf"


class CleanedCopy:
    def __init__(self, src_path: Path, dest: Path) -> None:
        self._original = src_path
        self._dest = dest
        self._read_from = src_path

    def write(self) -> None:
        try:
            self._written_and_checked()
        finally:
            self._discard_repaired_copy()

    def repaired_with_qpdf(self) -> bool:
        return self._read_from != self._original

    def _written_and_checked(self) -> None:
        self._deannotate()
        GuttingCheck(self._read_from, self._dest).run()

    def _discard_repaired_copy(self) -> None:
        if self.repaired_with_qpdf():
            self._read_from.unlink(missing_ok=True)

    def _deannotate(self) -> None:
        try:
            self._deannotate_from(self._original)
        except DAMAGED_FILE_ERRORS:
            self._deannotate_repaired()

    def _deannotate_repaired(self) -> None:
        repair = QpdfRepair(self._original)
        repair.run()
        self._read_from = repair.destination
        self._deannotate_from(repair.destination)

    def _deannotate_from(self, source: Path) -> None:
        with pymupdf.open(source) as doc:
            self._strip_annotations(doc)
            doc.save(self._dest)

    def _strip_annotations(self, doc: pymupdf.Document) -> None:
        for page in doc:
            annot = page.first_annot
            while annot:
                annot = page.delete_annot(annot)


class InPlaceClean:
    def __init__(self, pdf_path: Path) -> None:
        self._replacement = ReplacementFile(pdf_path, TEMPORARY_SUFFIX)
        self._copy = CleanedCopy(pdf_path, self._replacement.path)

    def run(self) -> None:
        with self._replacement as replacement:
            self._copy.write()
            replacement.commit()

    def repaired_with_qpdf(self) -> bool:
        return self._copy.repaired_with_qpdf()
