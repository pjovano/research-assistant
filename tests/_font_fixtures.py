from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import pikepdf
from _clean.cleaning import TEMPORARY_SUFFIX
from _clean.cmap import ToUnicodeCMap
from _clean.fonts import FontRecord
from _clean.glyphs import IdentityResolver, IdentityTable
from _clean.pixels import PixelResult
from _clean.textlayer import SuspectOccurrence
from _vaults import PATCHED_DIRS, TempVault

LASY9 = "LASY9"
SYMBOL_INTO_PRIVATE_USE = (
    "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
    "1 beginbfchar\n<0005> <F022>\nendbfchar\n"
)
SYMBOL_CODE = "0005"
SYMBOL_PRIVATE_USE_CHAR = ""
FIRST_PAGE_INDEX = 0
NO_BBOX = (0.0, 0.0, 0.0, 0.0)
PIXEL_SAMPLES = 2
FIRST_CODE = 1
GLYPH_WIDTH = 600
PAGE_SIZE = (612, 792)
TEXT_SIZE = 11
TEXT_ORIGIN = "72 700"
PROSE_BEFORE = "the symbol "
PROSE_AFTER = " stands in the formula"


@dataclass(frozen=True)
class FontFace:
    basefont: str = "ABCDEF+Symbol"
    encoding: str | None = None


def symbol_record(xref: int, cmap_text: str = SYMBOL_INTO_PRIVATE_USE, face: FontFace = FontFace()) -> FontRecord:
    return FontRecord(xref, face.basefont, frozenset({FIRST_PAGE_INDEX}), {}, ToUnicodeCMap(cmap_text), None, None,
                      face.encoding)


def occurrence_in(font: str, char: str = SYMBOL_PRIVATE_USE_CHAR) -> SuspectOccurrence:
    return SuspectOccurrence(FIRST_PAGE_INDEX, font, char, NO_BBOX, "")


class ScratchDirectory:
    def __init__(self, case: unittest.TestCase | None = None) -> None:
        self.path = Path(tempfile.mkdtemp())
        if case is not None:
            case.addCleanup(self.discard)

    def discard(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)

    def table(self, entries: dict) -> IdentityTable:
        path = self.path / "identities.json"
        path.write_text(json.dumps(entries), encoding="utf-8")
        return IdentityTable(path)

    def resolver(self, entries: dict) -> IdentityResolver:
        return IdentityResolver(self.table(entries))


class SilentCommand:
    def __init__(self, command) -> None:
        self._command = command

    def run(self, **arguments) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            self._command(argparse.Namespace(**arguments))
        return buffer.getvalue()


class NoPixelChecks:
    def result(self, pdf_path: Path, digest) -> PixelResult:
        return PixelResult.empty()


@dataclass(frozen=True)
class MisreadFont:
    basefont: str
    glyph_names: tuple[str, ...]
    targets: tuple[str, ...]

    @property
    def codes(self) -> list[str]:
        return [f"{number:02X}" for number in range(FIRST_CODE, FIRST_CODE + len(self.targets))]

    def dictionary(self, pdf: pikepdf.Pdf) -> pikepdf.Dictionary:
        font = pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                                  BaseFont=pikepdf.Name(f"/{self.basefont}"), FirstChar=FIRST_CODE,
                                  LastChar=FIRST_CODE + len(self.targets) - 1,
                                  Widths=[GLYPH_WIDTH] * len(self.targets),
                                  ToUnicode=pdf.make_stream(self._tounicode().encode("ascii")))
        if self.glyph_names:
            font.Encoding = pikepdf.Dictionary(Differences=self._differences())
        return pdf.make_indirect(font)

    def _differences(self) -> pikepdf.Array:
        return pikepdf.Array([FIRST_CODE, *(pikepdf.Name(f"/{name}") for name in self.glyph_names)])

    def _tounicode(self) -> str:
        rows = "".join(f"<{code}> <{ord(target):04X}>\n" for code, target in zip(self.codes, self.targets))
        return (f"1 begincodespacerange <00> <FF> endcodespacerange\n"
                f"{len(self.targets)} beginbfchar\n{rows}endbfchar\n")


class MisreadFontPdf:
    def __init__(self, fonts: tuple[MisreadFont, ...]) -> None:
        self._fonts = fonts

    def write(self, path: Path) -> Path:
        with pikepdf.new() as pdf:
            prose = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1,
                                                         BaseFont=pikepdf.Name.Helvetica,
                                                         Encoding=pikepdf.Name.WinAnsiEncoding))
            for font in self._fonts:
                pdf.pages.append(self._page(pdf, prose, font))
            pdf.save(path)
        return path

    @staticmethod
    def _page(pdf: pikepdf.Pdf, prose: pikepdf.Dictionary, font: MisreadFont) -> pikepdf.Page:
        fonts = pikepdf.Dictionary(P=prose, S=font.dictionary(pdf))
        page = pikepdf.Page(pikepdf.Dictionary(Type=pikepdf.Name.Page, MediaBox=[0, 0, *PAGE_SIZE],
                                               Resources=pikepdf.Dictionary(Font=fonts)))
        shown = "".join(font.codes)
        page.obj.Contents = pdf.make_stream(
            f"BT /P {TEXT_SIZE} Tf {TEXT_ORIGIN} Td ({PROSE_BEFORE}) Tj /S {TEXT_SIZE} Tf <{shown}> Tj "
            f"/P {TEXT_SIZE} Tf ({PROSE_AFTER}) Tj ET".encode("ascii"))
        return page


class VaultTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault(*PATCHED_DIRS).activate()
        self.addCleanup(self.vault.discard)

    def temporary_of(self, pdf_path: Path) -> Path:
        return pdf_path.with_suffix(TEMPORARY_SUFFIX)
