from __future__ import annotations

import re
from dataclasses import dataclass

import vault
from page_marker import PageMarker

PREFATORY_HEADING_RE = re.compile(
    r"\b(preface|foreword|introduction|einleitung|vorwort|avant-propos|introduzione|prefazione|prólogo|proemium)\b",
    re.IGNORECASE)
MAX_WORDS = 4000
CLASSIFICATION_FIELDS = ("source_type", "source_role", "field")
STAGE_FOUR_FIELDS = ("source_type", "source_role")


@dataclass(frozen=True)
class HeadedSection:
    level: int
    title: str
    lines: list[str]

    @property
    def is_prefatory(self) -> bool:
        return bool(PREFATORY_HEADING_RE.search(self.title))

    @property
    def word_count(self) -> int:
        return len(self.text().split())

    def text(self) -> str:
        return "\n".join(self.lines).strip()


class NoteSections:
    def __init__(self, body: str) -> None:
        self._body = vault.body_after_source_link(body)

    def all(self) -> list[HeadedSection]:
        sections: list[HeadedSection] = [HeadedSection(0, "", [])]
        for line in self._body.split("\n"):
            match = vault.HEADING_RE.match(line)
            if match:
                sections.append(HeadedSection(len(match.group(1)), match.group(2), []))
            elif PageMarker.parsed(line) is None:
                sections[-1].lines.append(line)
        return [section for section in sections if section.title or section.text()]


class Classification:
    def __init__(self, meta: dict) -> None:
        self._values = {field: meta.get(field) for field in CLASSIFICATION_FIELDS}

    @property
    def is_written(self) -> bool:
        return any(self._values[field] for field in STAGE_FOUR_FIELDS)

    def as_dict(self) -> dict:
        return dict(self._values)


class Opening:
    def __init__(self, basename: str) -> None:
        self._basename = basename
        self._meta, self._body = vault.read_frontmatter(vault.held_note_path(basename))

    @property
    def classification(self) -> Classification:
        return Classification(self._meta)

    def report(self) -> dict:
        sections = NoteSections(self._body).all()
        chosen = self._chosen([section for section in sections if section.word_count])
        return {"basename": self._basename, **self.classification.as_dict(),
                "headings": [self._heading(section) for section in sections],
                "prefatory": [section.title for section in chosen], "text": self._budgeted(chosen)}

    def _chosen(self, sections_with_text: list[HeadedSection]) -> list[HeadedSection]:
        prefatory = [section for section in sections_with_text if section.is_prefatory]
        return prefatory or self._leading(sections_with_text)

    @staticmethod
    def _leading(sections_with_text: list[HeadedSection]) -> list[HeadedSection]:
        leading, words = [], 0
        for section in sections_with_text:
            if words >= MAX_WORDS:
                break
            leading.append(section)
            words += section.word_count
        return leading

    def _heading(self, section: HeadedSection) -> str:
        return f"{'#' * section.level} {section.title}".strip()

    def _budgeted(self, sections: list[HeadedSection]) -> str:
        words = " ".join(section.text() for section in sections).split()
        clipped = " ".join(words[:MAX_WORDS])
        return clipped if len(words) <= MAX_WORDS else f"{clipped} […]"
