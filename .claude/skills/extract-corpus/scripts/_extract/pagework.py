from __future__ import annotations

from dataclasses import dataclass

from _extract.blocktexts import PageBlockTexts
from _extract.entryblocks import EntryBlocks
from _extract.headings import HeadingMatch
from _extract.pageoutput import PageOutput
from _extract.policy import SectionPolicy


@dataclass(frozen=True)
class PageWork:
    texts: PageBlockTexts
    output: PageOutput
    entries: EntryBlocks
    policy: SectionPolicy
    match: HeadingMatch
    sublevel: int | None
