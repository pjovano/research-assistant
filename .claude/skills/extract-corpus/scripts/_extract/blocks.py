from __future__ import annotations

import dataclasses
import html
import re
from dataclasses import dataclass

from _extract.box import EMPTY_BOX, Box

PAGE_KIND = "Page"
FOOTER_KIND = "PageFooter"
FURNITURE_KINDS = ("PageHeader", FOOTER_KIND)
FOOTNOTE_KIND = "Footnote"
EQUATION_KIND = "Equation"
INLINE_MATH_KIND = "TextInlineMath"
NOTATION_KINDS = (EQUATION_KIND, INLINE_MATH_KIND)
HEADING_KIND = "SectionHeader"
IMAGE_KINDS = ("Figure", "Picture", "Diagram")
TABLE_KIND = "Table"
CODE_KIND = "Code"
LIST_ITEM_KIND = "ListItem"
LIST_GROUP_KIND = "ListGroup"
TEXT_KIND = "Text"
CAPTION_KIND = "Caption"
BODY_KINDS = (TEXT_KIND, TABLE_KIND)
_CONTINUATION_CLASS = "has-continuation"
TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
UNPRINTED_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u2028\u2029\u202a-\u202e\ufeff]")


@dataclass(frozen=True)
class Block:
    file_page: int
    kind: str
    html: str
    bbox: Box
    images: dict
    identifier: str
    continued: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "bbox", Box.of(self.bbox))

    @property
    def plain_text(self) -> str:
        printed = UNPRINTED_RE.sub("", html.unescape(TAG_RE.sub(" ", self.html)))
        return _WHITESPACE_RE.sub(" ", printed).strip()

    @property
    def continues(self) -> bool:
        return self.continued or _CONTINUATION_CLASS in self.html

    def without_continuation(self) -> Block:
        return dataclasses.replace(self, html=self.html.replace(_CONTINUATION_CLASS, ""), continued=False)

    @property
    def is_furniture(self) -> bool:
        return self.kind in FURNITURE_KINDS

    @property
    def is_image(self) -> bool:
        return self.kind in IMAGE_KINDS


@dataclass(frozen=True)
class PageBlocks:
    file_page: int
    blocks: list[Block]

    def of_kind(self, kind: str) -> list[Block]:
        return [block for block in self.blocks if block.kind == kind]

    @property
    def content(self) -> list[Block]:
        return [block for block in self.blocks if not block.is_furniture]

    @property
    def furniture_texts(self) -> list[str]:
        return [block.plain_text for block in self.blocks if block.is_furniture]

    def stands_between_body_blocks(self, block: Block) -> bool:
        middle_x = block.bbox.center[0]
        column = [other for other in self.blocks
                  if other.kind in BODY_KINDS and other.bbox.left <= middle_x <= other.bbox.right]
        return _stands_between(block, column)

    def ending_its_text(self) -> PageBlocks:
        texts = [index for index, block in enumerate(self.blocks) if block.kind == TEXT_KIND]
        if not texts:
            return self
        last = texts[-1]
        ended = self.blocks[last].without_continuation()
        return PageBlocks(self.file_page, [*self.blocks[:last], ended, *self.blocks[last + 1:]])

    def stands_inside_the_text(self, block: Block) -> bool:
        printed = [other for other in self.content
                   if other is not block and other.kind != FOOTNOTE_KIND and not other.is_image]
        return _stands_between(block, printed)


def _stands_between(block: Block, others: list[Block]) -> bool:
    middle_y = block.bbox.center[1]
    return any(other.bbox.bottom <= middle_y for other in others) and any(other.bbox.top >= middle_y for other in others)


class DocumentBlocks:
    def __init__(self, pages: list[PageBlocks]) -> None:
        self._pages = pages

    @classmethod
    def from_json(cls, payload: dict, file_pages: list[int]) -> DocumentBlocks:
        pages = [PageBlocks(file_page, _LeafBlocks(file_page).of(page))
                 for file_page, page in zip(file_pages, page_payloads(payload))]
        return cls(pages)

    @property
    def pages(self) -> list[PageBlocks]:
        return list(self._pages)

    @property
    def furniture_texts(self) -> list[str]:
        return [text for page in self._pages for text in page.furniture_texts]

    def kind_counts(self, kinds: tuple[str, ...]) -> dict[int, dict[str, int]]:
        counted = {page.file_page: {kind: len(page.of_kind(kind)) for kind in kinds} for page in self._pages}
        return {file_page: counts for file_page, counts in counted.items() if any(counts.values())}

    def replaced(self, pages: list[PageBlocks]) -> DocumentBlocks:
        replacements = {page.file_page: page for page in pages}
        seams = {file_page: page.ending_its_text() for file_page, page in replacements.items()
                 if file_page + 1 not in replacements}
        return DocumentBlocks([seams.get(page.file_page, replacements.get(page.file_page, page))
                               for page in self._pages])


def engine_page_boxes(payload: dict, file_pages: list[int]) -> dict[int, Box]:
    return {file_page: Box.of(page["bbox"]) for file_page, page in zip(file_pages, page_payloads(payload))
            if page.get("bbox")}


def page_payloads(payload: dict) -> list[dict]:
    return [page for page in payload.get("children") or [] if page.get("block_type") == PAGE_KIND]


class _LeafBlocks:
    def __init__(self, file_page: int) -> None:
        self._file_page = file_page

    def of(self, page_payload: dict) -> list[Block]:
        leaves: list[Block] = []
        for child in page_payload.get("children") or []:
            self._collect(child, leaves)
        return leaves

    def _collect(self, payload: dict, leaves: list[Block]) -> None:
        children = payload.get("children") or []
        if children:
            for child in children:
                self._collect(child, leaves)
            return
        leaves.append(self._leaf(payload))

    def _leaf(self, payload: dict) -> Block:
        return Block(self._file_page, str(payload.get("block_type") or ""), payload.get("html") or "",
                     payload.get("bbox") or EMPTY_BOX,
                     payload.get("images") or {}, str(payload.get("id") or ""))
