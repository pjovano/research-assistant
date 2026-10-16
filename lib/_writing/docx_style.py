from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

NORMAL = "Normal"
BODY_TEXT = "Body Text"
UNINDENTED_STYLES = ("First Paragraph", "Compact")
BLOCK_TEXT = "Block Text"
FOOTNOTE_TEXT = "Footnote Text"
HEADING_LEVELS = range(1, 10)
FONT_ATTRIBUTES = ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs")
THEME_FONT_ATTRIBUTES = ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme")
BLACK = RGBColor(0, 0, 0)
PAGE_NUMBER_FIELD = "PAGE"


@dataclass(frozen=True)
class DocxStyle:
    name: str
    font: str
    body_points: float
    quotation_points: float
    note_points: float
    heading_points: tuple[float, ...]
    line_spacing: float
    note_line_spacing: float
    margin_inches: float
    first_line_indent_inches: float
    quotation_indent_inches: float

    def heading_points_at(self, level: int) -> float:
        sized = self.heading_points[level - 1:level]
        return sized[0] if sized else self.body_points


SUBMISSION = DocxStyle(
    name="submission", font="Times New Roman", body_points=12, quotation_points=12, note_points=10,
    heading_points=(12, 12, 12), line_spacing=2.0, note_line_spacing=1.0, margin_inches=1.0,
    first_line_indent_inches=0.5, quotation_indent_inches=0.5)
READING = DocxStyle(
    name="reading", font="Palatino", body_points=11, quotation_points=10, note_points=9,
    heading_points=(16, 13, 11), line_spacing=1.15, note_line_spacing=1.0, margin_inches=1.25,
    first_line_indent_inches=0.25, quotation_indent_inches=0.4)
DEFAULT_STYLE = SUBMISSION
STYLES = {style.name: style for style in (SUBMISSION, READING)}


class ReferenceDocument:
    def __init__(self, default_reference: bytes, style: DocxStyle) -> None:
        self._document = Document(io.BytesIO(default_reference))
        self._style = style

    def save(self, path: Path) -> None:
        self._set_font()
        self._set_body()
        self._set_quotations()
        self._set_notes()
        self._set_headings()
        self._set_pages()
        self._document.save(str(path))

    def _set_font(self) -> None:
        for fonts in self._document.styles.element.iter(qn("w:rFonts")):
            self._clear_theme(fonts)
        normal = self._document.styles[NORMAL]
        normal.font.size = Pt(self._style.body_points)
        fonts = normal.element.get_or_add_rPr().get_or_add_rFonts()
        for attribute in FONT_ATTRIBUTES:
            fonts.set(qn(attribute), self._style.font)

    @staticmethod
    def _clear_theme(fonts) -> None:
        for attribute in THEME_FONT_ATTRIBUTES:
            fonts.attrib.pop(qn(attribute), None)

    def _set_body(self) -> None:
        body = self._document.styles[BODY_TEXT].paragraph_format
        body.line_spacing = self._style.line_spacing
        body.space_before = Pt(0)
        body.space_after = Pt(0)
        body.first_line_indent = Inches(self._style.first_line_indent_inches)
        for name in UNINDENTED_STYLES:
            self._document.styles[name].paragraph_format.first_line_indent = Inches(0)

    def _set_quotations(self) -> None:
        quotation = self._document.styles[BLOCK_TEXT]
        quotation.font.size = Pt(self._style.quotation_points)
        quotation.paragraph_format.left_indent = Inches(self._style.quotation_indent_inches)
        quotation.paragraph_format.first_line_indent = Inches(0)

    def _set_notes(self) -> None:
        note = self._document.styles[FOOTNOTE_TEXT]
        note.font.size = Pt(self._style.note_points)
        note.paragraph_format.line_spacing = self._style.note_line_spacing

    def _set_headings(self) -> None:
        for level in HEADING_LEVELS:
            heading = self._document.styles[f"Heading {level}"].font
            heading.size = Pt(self._style.heading_points_at(level))
            heading.bold = True
            heading.color.rgb = BLACK

    def _set_pages(self) -> None:
        margin = Inches(self._style.margin_inches)
        for section in self._document.sections:
            section.left_margin = section.right_margin = section.top_margin = section.bottom_margin = margin
            self._number(section.footer.paragraphs[0])

    @staticmethod
    def _number(paragraph) -> None:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), PAGE_NUMBER_FIELD)
        field.append(OxmlElement("w:r"))
        paragraph._p.append(field)
