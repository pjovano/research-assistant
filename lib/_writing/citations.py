from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

FRONTMATTER_FENCE = "---"
CITEKEY_FIELD = "citekey"
KEY = r"@(?P<key>[A-Za-z0-9_](?:[\w:.#$%&+?<>~/-]*\w)?)"
BRACKETED_RE = re.compile(r"\[(?P<inside>[^\[\]]*@[^\[\]]*)\]")
KEY_RE = re.compile(rf"(?<![\w@]){KEY}")
IN_TEXT_RE = re.compile(rf"(?<![\w@\[]){KEY}(?: \[(?P<locator>[^\[\]@]*)\])?")
PART_BREAK = ";"


@dataclass(frozen=True)
class Citation:
    line: int
    key: str
    locator: str

    def as_json(self, held: dict[str, str]) -> dict:
        return {"line": self.line, "citekey": self.key, "locator": self.locator, "held_as": held.get(self.key)}


class DraftCitations:
    def __init__(self, text: str) -> None:
        self._lines = text.splitlines()

    def cited(self) -> list[Citation]:
        return [citation for number, line in enumerate(self._lines, start=1) for citation in self._of(number, line)]

    def keys(self) -> list[str]:
        return list(dict.fromkeys(citation.key for citation in self.cited()))

    def _of(self, number: int, line: str) -> list[Citation]:
        bracketed = [Citation(number, hit.group("key"), part[hit.end():].strip(" ,"))
                     for group in BRACKETED_RE.finditer(line) for part in group.group("inside").split(PART_BREAK)
                     if (hit := KEY_RE.search(part))]
        in_text = [Citation(number, hit.group("key"), (hit.group("locator") or "").strip())
                   for hit in IN_TEXT_RE.finditer(BRACKETED_RE.sub("", line))]
        return [*bracketed, *in_text]


class HeldCitekeys:
    def __init__(self, corpus_files: list[Path]) -> None:
        self._files = corpus_files

    def by_key(self) -> dict[str, str]:
        keyed = ((self._citekey(file), file.stem) for file in self._files)
        return {key: basename for key, basename in keyed if key}

    @staticmethod
    def _citekey(file: Path) -> str | None:
        with file.open(encoding="utf-8") as handle:
            if handle.readline().strip() != FRONTMATTER_FENCE:
                return None
            header = []
            for line in handle:
                if line.strip() == FRONTMATTER_FENCE:
                    break
                header.append(line)
        return (yaml.safe_load("".join(header)) or {}).get(CITEKEY_FIELD)


class CitationReport:
    def __init__(self, draft: Path, held: dict[str, str]) -> None:
        self._draft = draft
        self._citations = DraftCitations(draft.read_text(encoding="utf-8"))
        self._held = held

    def as_json(self) -> dict:
        keys = self._citations.keys()
        return {"draft": self._draft.stem, "citations": [each.as_json(self._held) for each in self._citations.cited()],
                "held": [key for key in keys if key in self._held],
                "not_held": [key for key in keys if key not in self._held]}
