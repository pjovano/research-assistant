from __future__ import annotations

import json
import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import vault

from _extract.engine import MODE_FORCED_OCR
from _extract.paths import CorpusFile
from _extract.records import MODE_KEY, ExtractionRecords
from _extract.trial import TRIALS_DIR_NAME

SAMPLE_SET_NAME = "regress-sample.json"
PER_PROPERTY = 3
PER_WEIGHTED_PROPERTY = 5
RANDOM_EXTRA = 10
DEFAULT_SEED = 0
LONG_WORK_PAGES = 200
ENGLISH_STOPWORD_SHARE = 0.04
SAMPLED_CHARS = 200_000
_ENGLISH_STOPWORDS = frozenset({"the", "and", "of", "to", "in", "is", "that", "it", "which", "as"})
_WORD_RE = re.compile(r"[^\W\d_]+")
_HEADING_RE = re.compile(r"^#{1,6} (?P<title>.+)$", re.MULTILINE)
_TABLE_RE = re.compile(r"^\|.*\|[ \t]*\n\|[-:| ]+\|[ \t]*$", re.MULTILINE)
_MARKER_RE = re.compile(r"%% (?:p\. \S+ \()?file p\. \d+\)? %%")
_COLLECTED_NOTES = "\n# Notes\n\n[^"


@dataclass(frozen=True)
class WorkSample:
    meta: dict
    body: str
    record: dict

    def headings(self) -> list[str]:
        return [match.group("title").strip() for match in _HEADING_RE.finditer(self.body)]

    def english_share(self) -> float:
        words = [word.casefold() for word in _WORD_RE.findall(self.body[:SAMPLED_CHARS])]
        return sum(word in _ENGLISH_STOPWORDS for word in words) / max(len(words), 1)


PROPERTIES: dict[str, Callable[[WorkSample], bool]] = {
    "article": lambda work: work.meta.get("type") == "journalArticle",
    "chapter": lambda work: work.meta.get("type") == "bookSection",
    "book": lambda work: work.meta.get("type") == "book",
    "long work": lambda work: len(_MARKER_RE.findall(work.body)) >= LONG_WORK_PAGES,
    "read from pixels": lambda work: work.record.get(MODE_KEY) == MODE_FORCED_OCR,
    "notation": lambda work: "$" in work.body,
    "footnotes": lambda work: _COLLECTED_NOTES in work.body,
    "endnotes": lambda work: any(vault.is_notes_heading(title) for title in work.headings()),
    "entry list": lambda work: any(vault.is_bibliography_heading(title) for title in work.headings()),
    "table": lambda work: bool(_TABLE_RE.search(work.body)),
    "not in English": lambda work: work.english_share() < ENGLISH_STOPWORD_SHARE,
}
WEIGHTED_PROPERTIES = frozenset({"footnotes", "endnotes", "entry list"})


def properties_of(pdf_path: Path) -> set[str]:
    note = CorpusFile(pdf_path)
    record = ExtractionRecords().entry(note.basename) or {}
    work = WorkSample(note.frontmatter(), note.body(), record)
    return {name for name, holds in PROPERTIES.items() if holds(work)}


class SampleSet:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or vault.SCRATCH_DIR / TRIALS_DIR_NAME / SAMPLE_SET_NAME

    def basenames(self) -> list[str]:
        if not self.path.is_file():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))["works"]

    def save(self, chosen: dict[str, list[str]], works: list[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"works": works, "by_property": chosen}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class SampleSetChooser:
    def __init__(self, properties: dict[str, set[str]], cached: set[str], seed: int = DEFAULT_SEED) -> None:
        self._properties = properties
        self._cached = cached
        self._random = random.Random(seed)

    def chosen(self) -> tuple[dict[str, list[str]], list[str]]:
        taken: list[str] = []
        by_property = {name: self._take(name, taken) for name in PROPERTIES}
        rest = sorted(set(self._properties) - set(taken))
        taken += self._preferring_cached(rest, RANDOM_EXTRA)
        return by_property, taken

    def _take(self, name: str, taken: list[str]) -> list[str]:
        quota = PER_WEIGHTED_PROPERTY if name in WEIGHTED_PROPERTIES else PER_PROPERTY
        holders = sorted(work for work, held in self._properties.items() if name in held)
        already = [work for work in holders if work in taken][:quota]
        added = self._preferring_cached([work for work in holders if work not in taken], quota - len(already))
        taken += added
        return already + added

    def _preferring_cached(self, works: list[str], count: int) -> list[str]:
        cached = [work for work in works if work in self._cached]
        uncached = [work for work in works if work not in self._cached]
        first = self._random.sample(cached, min(count, len(cached)))
        return first + self._random.sample(uncached, min(count - len(first), len(uncached)))
