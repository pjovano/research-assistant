from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

import pymupdf
import vault

ANNOTATION_TEMPORARY_SUFFIX = ".annotate.tmp.pdf"


class IncrementalEdit:
    def __init__(self, path: Path) -> None:
        self._path = path

    def applied(self, edit: Callable, written: Callable[[object], bool]):
        with vault.ReplacementFile(self._path, ANNOTATION_TEMPORARY_SUFFIX) as replacement:
            shutil.copyfile(self._path, replacement.path)
            result = self._saved(replacement.path, edit, written)
            if written(result):
                replacement.commit()
        return result

    def _saved(self, copy: Path, edit: Callable, written: Callable[[object], bool]):
        with pymupdf.open(copy) as document:
            result = edit(document)
            if written(result):
                document.save(copy, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        return result


class HighlightStamp:
    def __init__(self, annotation) -> None:
        self._annotation = annotation

    def recoloured(self, colour: tuple | None) -> "HighlightStamp":
        if colour is not None:
            self._annotation.set_colors(stroke=list(colour))
        return self

    def covering(self, quads: list) -> "HighlightStamp":
        if not quads:
            return self
        page = self._annotation.parent
        corners = [corner for quad in quads for corner in (quad.ul, quad.ur, quad.ll, quad.lr)]
        points = [corner * ~page.transformation_matrix for corner in corners]
        across, up = [point.x for point in points], [point.y for point in points]
        self._set("QuadPoints", [value for point in points for value in (point.x, point.y)])
        self._set("Rect", [min(across), min(up), max(across), max(up)])
        return self

    def _set(self, key: str, values: list[float]) -> None:
        written = " ".join(f"{value:g}" for value in values)
        self._annotation.parent.parent.xref_set_key(self._annotation.xref, key, f"[{written}]")

    def stamped(self, author: str, content: str, subject: str) -> "HighlightStamp":
        self._annotation.set_info(title=author, content=content, subject=subject)
        self._annotation.update()
        return self
