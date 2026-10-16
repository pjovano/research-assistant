from __future__ import annotations

from pathlib import Path

import vault
from page_marker import PageMarker

PAGE_QUERY = "page"


class CorpusBody:
    def __init__(self, basename: str) -> None:
        self._basename = basename
        self._text = self._read(vault.corpus_path(basename))

    def basename(self) -> str:
        return self._basename

    def is_absent(self) -> bool:
        return self._text is None

    def text(self) -> str:
        return self._text or ""

    @staticmethod
    def _read(path: Path) -> str | None:
        if not path.exists():
            return None
        _meta, body = vault.read_frontmatter(path)
        return body


class ZoteroDeepLink:
    def __init__(self, corpus: CorpusBody) -> None:
        self._target, self._absence = self._read(corpus)

    def at(self, file_page: int) -> str | None:
        if self._target is None:
            return None
        return f"{self._target}?{PAGE_QUERY}={file_page}"

    def absence(self) -> str | None:
        return self._absence

    @staticmethod
    def _read(corpus: CorpusBody) -> tuple[str | None, str | None]:
        if corpus.is_absent():
            return None, f"no link: {corpus.basename()} has no corpus file"
        target = vault.pdf_link_of(corpus.text())
        if target is None:
            return None, "no link: the corpus file's body does not begin with the PDF link line"
        return target, None


class CorpusFolios:
    def __init__(self, corpus: CorpusBody) -> None:
        self._by_file_page = {marker.file_page: marker.folio for marker in PageMarker.inline(corpus.text())
                              if marker.file_page is not None and marker.folio}

    def of(self, file_page: int) -> str | None:
        return self._by_file_page.get(file_page)
