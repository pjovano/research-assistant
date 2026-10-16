from __future__ import annotations

from dataclasses import dataclass

MIN_LAYER_SHARE = 0.8
READS_LAYER = "layer"
READS_PIXELS = "pixels"
PAGES_WITH_TEXT_FIELD = "pages_with_text"
PAGE_COUNT_FIELD = "page_count"


@dataclass(frozen=True)
class LayerCoverage:
    pages_with_text: int
    page_count: int

    @classmethod
    def of_probe(cls, probe: dict) -> LayerCoverage:
        return cls(int(probe.get(PAGES_WITH_TEXT_FIELD) or 0), int(probe.get(PAGE_COUNT_FIELD) or 0))

    @classmethod
    def of_layer(cls, layer) -> LayerCoverage:
        page_count = layer.page_count()
        return cls(sum(layer.has_text(page) for page in range(1, page_count + 1)), page_count)

    @property
    def suffices(self) -> bool:
        return self.page_count > 0 and self.pages_with_text / self.page_count >= MIN_LAYER_SHARE
