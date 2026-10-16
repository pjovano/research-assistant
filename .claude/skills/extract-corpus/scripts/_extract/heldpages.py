from __future__ import annotations

from _extract.blocks import page_payloads

DOCUMENT_KIND = "Document"
_CHILDREN_KEY = "children"
_KIND_KEY = "block_type"


class HeldPages:
    def __init__(self, payloads_by_page: dict[int, dict]) -> None:
        self._payloads_by_page = payloads_by_page

    @property
    def file_pages(self) -> list[int]:
        return sorted(self._payloads_by_page)

    def missing(self, file_pages: list[int]) -> list[int]:
        return [file_page for file_page in file_pages if file_page not in self._payloads_by_page]

    def payload(self, file_pages: list[int]) -> dict | None:
        if self.missing(file_pages):
            return None
        pages = [self._payloads_by_page[file_page] for file_page in file_pages]
        return {_CHILDREN_KEY: pages, _KIND_KEY: DOCUMENT_KIND}

    def merged_over(self, earlier: HeldConversion) -> HeldConversion:
        return HeldPages({**earlier.paged_payloads(), **self._payloads_by_page})

    def paged_payloads(self) -> dict[int, dict]:
        return dict(self._payloads_by_page)


class WholeConversion:
    def __init__(self, file_pages: list[int], payload: dict) -> None:
        self._file_pages = list(file_pages)
        self._payload = payload

    @property
    def file_pages(self) -> list[int]:
        return list(self._file_pages)

    def missing(self, file_pages: list[int]) -> list[int]:
        return [] if file_pages == self._file_pages else list(file_pages)

    def payload(self, file_pages: list[int]) -> dict | None:
        return self._payload if file_pages == self._file_pages else None

    def merged_over(self, _earlier: HeldConversion) -> HeldConversion:
        return self

    def paged_payloads(self) -> dict[int, dict]:
        return {}


HeldConversion = HeldPages | WholeConversion


def held_conversion(file_pages: list[int], payload: dict) -> HeldConversion:
    pages = page_payloads(payload)
    if len(pages) == len(file_pages):
        return HeldPages(dict(zip(file_pages, pages)))
    return WholeConversion(file_pages, payload)
