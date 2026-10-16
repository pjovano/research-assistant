from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CitedWork:
    title: str
    authors: list[str]
    year: int | None


@dataclass(frozen=True)
class Sighting:
    source: str
    seen_at: str
    citations: int | None = None
    obtain: dict | None = None


def candidate(work: CitedWork, sighting: Sighting) -> dict:
    return {"title": work.title, "authors": work.authors, "year": work.year, "container": "",
            "comment": "About the beginning.", "seen_at": sighting.seen_at, "citations": sighting.citations,
            "obtain": sighting.obtain, "query": "q", "source": sighting.source}


def report(source: str, candidates: list[dict], **extra) -> dict:
    return {"source": source, "queries_run": ["q"], "candidates": candidates, **extra}
