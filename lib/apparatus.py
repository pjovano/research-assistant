from __future__ import annotations

import re

DROPPED_HEADING_RE = re.compile(
    r"^(contents|table of contents|inhalt|inhaltsverzeichnis|table des matières|acknowledge?ments?|copyright( page)?"
    r"|(front )?cover|endorsements?|dedication|title|about the authors?|of related interest"
    r"|also by .*|other books by .*"
    r"|list of (illustrations|figures|tables|plates)|series editors?'? (preface|foreword)|half[- ]title|title page)$",
    re.IGNORECASE)
INDEX_NAME_PATTERN = (r"(?:subject|name|names|author|general|analytical|citation|scripture) index|index(?:es)?"
                      r"|indices|namenregister|sachregister|personenregister|register")
INDEX_HEADING_RE = re.compile(rf"^({INDEX_NAME_PATTERN}|index of \S.*)$", re.IGNORECASE)
_NOTE_TO_THE_READER_RE = re.compile(
    r"^(note[s]? (to|for) the reader|preface to the .*edition|translator'?s? note|editor'?s? note"
    r"|abbreviations|abkürzungen|sigla|frontispiece|list of contributors|notes on contributors)$", re.IGNORECASE)


class Apparatus:
    def is_front_matter(self, title: str) -> bool:
        stripped = title.strip()
        return bool(DROPPED_HEADING_RE.match(stripped)) or bool(_NOTE_TO_THE_READER_RE.match(stripped))

    def is_index(self, title: str) -> bool:
        return bool(INDEX_HEADING_RE.match(title.strip()))

    def is_apparatus(self, title: str) -> bool:
        return self.is_front_matter(title) or self.is_index(title)
