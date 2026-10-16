from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from _support import LiveTree

LiveTree.activate()

from _extract.box import Box
from _extract.engineframes import EngineFrames
from _extract.layer import TextLayer

FILE_PAGE = 1
FONT = "helv"
NOTE_SIZE = 8.0
MEDIA_BOX = (34.0, 34.0, 478.0, 699.0)
CROP_BOX = (0.0, 0.0, 512.0, 733.0)
MEDIA_WIDTH = MEDIA_BOX[2] - MEDIA_BOX[0]
MEDIA_HEIGHT = MEDIA_BOX[3] - MEDIA_BOX[1]
CROP_WIDTH = CROP_BOX[2] - CROP_BOX[0]
CROP_HEIGHT = CROP_BOX[3] - CROP_BOX[1]
NOTE_LEFT = 42.0
NOTE_BASELINE = 540.0
NOTE = "To be more precise, further constraints are imposed on the sorts."
EMPTY_ANNOTATIONS = "[]"


def pdf_box(box: tuple[float, ...]) -> str:
    return "[" + " ".join(f"{value:g}" for value in box) + "]"


class CroppedPagePdf:
    def __init__(self, path: Path, annotated: bool) -> None:
        self._path = path
        self._annotated = annotated

    def write(self) -> Path:
        with pymupdf.open() as document:
            page = document.new_page(width=MEDIA_WIDTH, height=MEDIA_HEIGHT)
            page.insert_text((NOTE_LEFT, NOTE_BASELINE), NOTE, fontname=FONT, fontsize=NOTE_SIZE)
            document.xref_set_key(page.xref, "MediaBox", pdf_box(MEDIA_BOX))
            document.xref_set_key(page.xref, "CropBox", pdf_box(CROP_BOX))
            if self._annotated:
                document.xref_set_key(page.xref, "Annots", EMPTY_ANNOTATIONS)
            document.save(self._path)
        return self._path


def flattened_engine_box(layer_box: Box) -> list[float]:
    crop_left = layer_box.left + MEDIA_BOX[0] - CROP_BOX[0]
    crop_top = layer_box.top + CROP_BOX[3] - MEDIA_BOX[3]
    crop_right = crop_left + layer_box.width
    crop_bottom = crop_top + layer_box.height
    across, down = MEDIA_WIDTH / CROP_WIDTH, MEDIA_HEIGHT / CROP_HEIGHT
    return [crop_left * across, crop_top * down, crop_right * across, crop_bottom * down]


def engine_payload(note_box: list[float]) -> dict:
    note = {"block_type": "Footnote", "html": f"<p>{NOTE}</p>", "bbox": note_box, "id": "/page/0/Footnote/1"}
    return {"children": [{"block_type": "Page", "bbox": list(MEDIA_BOX), "children": [note]}]}


class TestEngineBlocksOfAnnotatedPagesWhoseCropBoxReachesPastTheMediaBox(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self._directory, True)

    def placed_and_printed(self, annotated: bool) -> tuple[Box, Box]:
        pdf_path = CroppedPagePdf(self._directory / f"cropped-{annotated}.pdf", annotated).write()
        layer = TextLayer(pdf_path)
        self.addCleanup(layer.close)
        printed = Box.union([line.box for line in layer.lines(FILE_PAGE)])
        engine_box = flattened_engine_box(printed) if annotated else list(printed)
        placed = EngineFrames(pdf_path).placed(engine_payload(engine_box), [FILE_PAGE]).pages[0].blocks[0]
        return placed.bbox, printed

    def test_a_block_of_an_annotated_page_is_placed_on_the_text_layer_line_it_reads(self) -> None:
        placed, printed = self.placed_and_printed(annotated=True)
        for edge, expected in zip(placed, printed):
            self.assertAlmostEqual(expected, edge, places=1)

    def test_a_block_of_a_page_without_annotations_keeps_the_engines_box(self) -> None:
        placed, printed = self.placed_and_printed(annotated=False)
        self.assertEqual(printed, placed)


if __name__ == "__main__":
    unittest.main()
