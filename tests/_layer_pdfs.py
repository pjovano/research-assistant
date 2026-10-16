from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

FIRST_BASELINE = 100.0
LINE_PITCH = 14.0
LEFT_MARGIN = 72.0
FONT_SIZE = 11.0
FONT_NAME = "helv"
FIRST_CODE = 32
LAST_CODE = 126
GLYPH_WIDTH = 556
_CMAP_TEMPLATE = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Remapped def "
                  "1 begincodespacerange <00> <FF> endcodespacerange {count} beginbfchar {pairs} endbfchar "
                  "endcmap CMapName currentdict /CMap defineresource pop end end")


@dataclass(frozen=True)
class StandIn:
    char: str
    zero_width: bool = False


class RemappedTextPdf:
    def __init__(self, path: Path, lines: list[str], stand_ins: dict[str, StandIn]) -> None:
        self._path = path
        self._lines = lines
        self._stand_ins = stand_ins

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page()
            self.draw(page, self._lines)
            self._remap(document, page.get_fonts()[0][0])
            document.save(self._path)
        return self._path

    def draw(self, page, lines: list[str]) -> None:
        for row, line in enumerate(lines):
            page.insert_text((LEFT_MARGIN, FIRST_BASELINE + row * LINE_PITCH), line, fontname=FONT_NAME,
                             fontsize=FONT_SIZE)

    def _remap(self, document, font_xref: int) -> None:
        cmap_xref = document.get_new_xref()
        document.update_object(cmap_xref, "<<>>")
        document.update_stream(cmap_xref, self._cmap().encode("ascii"))
        document.xref_set_key(font_xref, "ToUnicode", f"{cmap_xref} 0 R")
        document.xref_set_key(font_xref, "FirstChar", str(FIRST_CODE))
        document.xref_set_key(font_xref, "LastChar", str(LAST_CODE))
        document.xref_set_key(font_xref, "Widths", f"[{' '.join(map(str, self._widths()))}]")

    def _cmap(self) -> str:
        pairs = " ".join(f"<{ord(code):02X}> <{ord(stand_in.char):04X}>" for code, stand_in in self._stand_ins.items())
        return _CMAP_TEMPLATE.format(count=len(self._stand_ins), pairs=pairs)

    def _widths(self) -> list[int]:
        zero_width = {ord(code) for code, stand_in in self._stand_ins.items() if stand_in.zero_width}
        return [0 if code in zero_width else GLYPH_WIDTH for code in range(FIRST_CODE, LAST_CODE + 1)]


class RemappedPagesPdf(RemappedTextPdf):
    def __init__(self, path: Path, pages: list[list[str]], stand_ins: dict[str, StandIn],
                 chapters: list[tuple[str, int]]) -> None:
        super().__init__(path, [], stand_ins)
        self._pages = pages
        self._chapters = chapters

    def write(self) -> Path:
        with pymupdf.open() as document:
            for lines in self._pages:
                self.draw(document.new_page(), lines)
            for font_xref in {font[0] for page in document for font in page.get_fonts()}:
                self._remap(document, font_xref)
            document.set_toc([[1, title, file_page] for title, file_page in self._chapters])
            document.save(self._path)
        return self._path
