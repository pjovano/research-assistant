from __future__ import annotations

import re

import pymupdf

TRACED_FONT_MARK = "Bezier"
DESCENDANT_FONTS_KEY = "DescendantFonts"
BASE_FONT_KEY = "BaseFont"
ABSENT = "null"
_REFERENCE_RE = re.compile(r"(\d+) 0 R")
_SUBSET_TAG_RE = re.compile(r"^[A-Z]{6}\+")


class ScanTracedFonts:
    def set_most_text_of(self, page: pymupdf.Page) -> bool:
        traced_names = self._traced_names(page)
        spans = [(span["font"] in traced_names, len(span["chars"])) for span in page.get_texttrace()]
        traced_chars = sum(count for is_traced, count in spans if is_traced)
        all_chars = sum(count for _is_traced, count in spans)
        return traced_chars > all_chars / 2

    def _traced_names(self, page: pymupdf.Page) -> set[str]:
        document = page.parent
        font_xrefs = [font[0] for font in page.get_fonts(full=True)]
        return {self._drawing_name(document, xref) for xref in font_xrefs if self._is_traced(document, xref)}

    @staticmethod
    def _is_traced(document: pymupdf.Document, xref: int) -> bool:
        kind, _value = document.xref_get_key(xref, TRACED_FONT_MARK)
        return kind != ABSENT

    @staticmethod
    def _drawing_name(document: pymupdf.Document, xref: int) -> str:
        _kind, descendants = document.xref_get_key(xref, DESCENDANT_FONTS_KEY)
        reference = _REFERENCE_RE.search(descendants)
        drawing_xref = int(reference.group(1)) if reference else xref
        _kind, base_font = document.xref_get_key(drawing_xref, BASE_FONT_KEY)
        return _SUBSET_TAG_RE.sub("", base_font.lstrip("/"))
