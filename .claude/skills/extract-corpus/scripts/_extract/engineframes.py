from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from _extract.blocks import Block, DocumentBlocks, PageBlocks, engine_page_boxes
from _extract.box import Box

FRAME_TOLERANCE_POINTS = 1.0
_ANNOTATIONS_KEY = "Annots"
_ABSENT = "null"


@dataclass(frozen=True)
class FlattenedFrame:
    crop: Box
    visible: Box
    engine_page: Box

    def placed(self, box: Box) -> Box:
        left, top = self._placed_point(box.left, box.top)
        right, bottom = self._placed_point(box.right, box.bottom)
        return Box(left, top, right, bottom)

    def _placed_point(self, x: float, y: float) -> tuple[float, float]:
        across = self.crop.left + x * self.crop.width / self.engine_page.width - self.visible.left
        down = self.crop.top + y * self.crop.height / self.engine_page.height - self.visible.top
        return across, down


class EngineFrames:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def placed(self, payload: dict, file_pages: list[int]) -> DocumentBlocks:
        blocks = DocumentBlocks.from_json(payload, file_pages)
        page_boxes = engine_page_boxes(payload, file_pages)
        with pymupdf.open(self._pdf_path) as document:
            frames = {file_page: _flattened_frame(document, document[file_page - 1], box)
                      for file_page, box in page_boxes.items()}
        return DocumentBlocks([_placed_page(page, frames.get(page.file_page)) for page in blocks.pages])


def _flattened_frame(document: pymupdf.Document, page: pymupdf.Page, engine_page: Box) -> FlattenedFrame | None:
    crop = Box.of(page.cropbox)
    visible = _crop_within_media(crop, page.mediabox)
    is_flattened = document.xref_get_key(page.xref, _ANNOTATIONS_KEY)[0] != _ABSENT
    if page.rotation or not is_flattened or _same_box(crop, visible):
        return None
    return FlattenedFrame(crop, visible, engine_page)


def _crop_within_media(crop: Box, media: pymupdf.Rect) -> Box:
    return Box(max(crop.left, media.x0), max(crop.top, 0.0), min(crop.right, media.x1), min(crop.bottom, media.height))


def _same_box(first: Box, second: Box) -> bool:
    return all(abs(one - other) <= FRAME_TOLERANCE_POINTS for one, other in zip(first, second))


def _placed_page(page: PageBlocks, frame: FlattenedFrame | None) -> PageBlocks:
    if frame is None:
        return page
    return PageBlocks(page.file_page, [_placed_block(block, frame) for block in page.blocks])


def _placed_block(block: Block, frame: FlattenedFrame) -> Block:
    return dataclasses.replace(block, bbox=frame.placed(block.bbox))
