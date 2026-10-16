from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .claims import ACCEPTED_MARK, REVIEW_MARK, ClaimsBlock
from .linked_note import LinkedNote
from .project_file import LINE_BREAK, joined

REFERENCES = "References"
TASKS = "Tasks"
PARTS = (REFERENCES, TASKS)
TEMPLATE_FILE = Path(__file__).resolve().parents[2] / ".claude" / "skills" / "take-notes" / "reference" / "atomic-note.md"
NOTE_RELATIONS = ("extends", "supports", "contradicts", "example of", "presupposes", "descends from")
RELATION_RE = re.compile(rf"(?P<kind>{'|'.join(NOTE_RELATIONS)}) \[\[(?P<target>[^\]|#]+)")
PART_HEADING_RE = re.compile(r"^# ", re.MULTILINE)
BLOCK_BREAK_RE = re.compile(r"\n\s*\n")
GROUP_MARK = "### "
SOURCE_OF_BLOCK_RE = re.compile(r"^> \t\[\[(?P<source>[^\]|#]+)\]\]", re.MULTILINE)
PAGE_OF_BLOCK_RE = re.compile(r"[?&]page=(?P<page>\d+)")
UNGROUPED = ""
REVIEW_MARK_AT_LINE_END_RE = re.compile(rf"{re.escape(REVIEW_MARK)}$", re.MULTILINE)


def part_pattern(heading: str) -> re.Pattern:
    return re.compile(rf"(^# {re.escape(heading)}\n)(.*?)(?=^# |\Z)", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class Relation:
    kind: str
    target: str


def source_of(block: str) -> str:
    hit = SOURCE_OF_BLOCK_RE.search(block)
    return hit.group("source").strip() if hit else ""


def page_of(block: str) -> int:
    hit = PAGE_OF_BLOCK_RE.search(block)
    return int(hit.group("page")) if hit else 0


@dataclass(frozen=True)
class ReferencePlace:
    group: str = UNGROUPED
    after: int | None = None
    before: str = UNGROUPED


class ReferenceGroups:
    def __init__(self, groups: list[tuple[str, list[str]]]) -> None:
        self._groups = groups

    @classmethod
    def read(cls, lines: str) -> "ReferenceGroups":
        groups: list[tuple[str, list[str]]] = [(UNGROUPED, [])]
        for block in (each.strip() for each in BLOCK_BREAK_RE.split(lines)):
            heading, _, rest = block.partition("\n") if block.startswith(GROUP_MARK) else ("", "", block)
            if heading:
                groups.append((heading[len(GROUP_MARK):].strip(), []))
            if rest.strip():
                groups[-1][1].append(rest.strip())
        return cls(groups)

    @property
    def text(self) -> str:
        parts = [part for name, blocks in self._groups for part in ([GROUP_MARK + name] if name else []) + blocks]
        return "\n\n".join(parts)

    def blocks(self) -> list[str]:
        return [block for _, blocks in self._groups for block in blocks]

    def ungrouped(self) -> list[str]:
        return list(self._groups[0][1])

    def by_work(self) -> "ReferenceGroups":
        return ReferenceGroups([(name, self._gathered(blocks)) for name, blocks in self._groups])

    def parted_works(self) -> list[str]:
        return [source for _, blocks in self._groups for source in dict.fromkeys(map(source_of, blocks))
                if self._is_parted(source, blocks)]

    @staticmethod
    def _gathered(blocks: list[str]) -> list[str]:
        works = dict.fromkeys(source_of(block) for block in blocks)
        return [block for work in works for block in sorted((each for each in blocks if source_of(each) == work), key=page_of)]

    @staticmethod
    def _is_parted(source: str, blocks: list[str]) -> bool:
        places = [index for index, block in enumerate(blocks) if source_of(block) == source]
        return bool(places) and places[-1] - places[0] + 1 != len(places)

    def with_block(self, block: str, place: ReferencePlace) -> "ReferenceGroups":
        groups = [(name, list(blocks)) for name, blocks in self._groups]
        if place.after is None:
            self._group_placed(groups, place).append(block.strip())
        else:
            self._insert_after(groups, place.after, block.strip())
        return ReferenceGroups(groups).by_work()

    def _group_placed(self, groups: list[tuple[str, list[str]]], place: ReferencePlace) -> list[str]:
        names = [name for name, _ in groups]
        name, before = place.group.strip(), place.before.strip()
        if name in names:
            self._refuse_moving(name, before)
        else:
            groups.insert(self._position_of_new_group(names, before), (name, []))
        return next(blocks for each, blocks in groups if each == name)

    @staticmethod
    def _refuse_moving(name: str, before: str) -> None:
        if before:
            raise ValueError(f"the note holds the group {name!r} already, and a held group is never moved: "
                             "write the reference without --before")

    @staticmethod
    def _position_of_new_group(names: list[str], before: str) -> int:
        if not before:
            return len(names)
        if before not in names:
            raise ValueError(f"the note holds no group {before!r} to write a new group before: "
                             f"its groups are {[name for name in names if name]}")
        return names.index(before)

    def _insert_after(self, groups: list[tuple[str, list[str]]], after: int, block: str) -> None:
        places = [(blocks, index + 1) for _, blocks in groups for index in range(len(blocks))]
        if not 0 <= after <= len(places):
            raise ValueError(f"the note holds {len(places)} references: none is number {after}")
        blocks, position = places[after - 1] if after else (places[0][0] if places else groups[0][1], 0)
        blocks.insert(position, block)


class AtomicNote:
    def __init__(self, text: str) -> None:
        self._note = LinkedNote.parsed(text)

    @classmethod
    def blank(cls) -> "AtomicNote":
        return cls(TEMPLATE_FILE.read_text(encoding="utf-8"))

    @property
    def text(self) -> str:
        return self._note.text

    @property
    def claims_block(self) -> str:
        return self._note.body[:self._claims_end()].strip("\n")

    def claims(self) -> list[str]:
        return ClaimsBlock(self.claims_block).claims()

    def reference_blocks(self) -> list[str]:
        return self.reference_groups().blocks()

    def reference_groups(self) -> ReferenceGroups:
        return ReferenceGroups.read(self.lines(REFERENCES))

    def links(self, field: str) -> list[str]:
        return self._note.links(field)

    def headings(self) -> list[str]:
        return [line[2:].strip() for line in self._note.body.splitlines() if PART_HEADING_RE.match(line)]

    def lines(self, heading: str) -> str:
        hit = part_pattern(heading).search(self._note.body)
        return hit.group(2).strip() if hit else ""

    def relations(self) -> list[Relation]:
        related = f"{self.claims_block}\n{self.lines(REFERENCES)}"
        return [Relation(hit.group("kind"), hit.group("target").strip()) for hit in RELATION_RE.finditer(related)]

    def proposed_relations(self) -> list[Relation]:
        marked = [*self.claims_block.splitlines(), *self.reference_blocks()]
        return [Relation(hit.group("kind"), hit.group("target").strip()) for each in marked
                if each.splitlines()[:1] and each.splitlines()[0].rstrip().endswith(REVIEW_MARK.strip())
                for hit in RELATION_RE.finditer(each)]

    def awaits_review(self) -> bool:
        return REVIEW_MARK.strip() in self._note.body

    def review_marks(self) -> int:
        return len(REVIEW_MARK_AT_LINE_END_RE.findall(self._note.body))

    def with_review_marks_accepted(self) -> "AtomicNote":
        body = REVIEW_MARK_AT_LINE_END_RE.sub(ACCEPTED_MARK, self._note.body)
        return AtomicNote(self._note.with_body(body).text)

    def without_relation(self, relation: Relation) -> "AtomicNote":
        line = re.compile(rf"^\t- {re.escape(relation.kind)} \[\[{re.escape(relation.target)}\]\](: .*)?( #review)?$")
        kept = [each for each in self.claims_block.splitlines() if not line.match(each)]
        return self.with_claims(ClaimsBlock("\n".join(kept)))

    def with_links(self, field: str, targets: list[str]) -> "AtomicNote":
        if targets:
            return AtomicNote(self._note.with_links(field, targets).text)
        meta = {key: value for key, value in self._note.meta.items() if key != field}
        return AtomicNote(LinkedNote(meta, self._note.body).text)

    def with_explication(self, line: str) -> "AtomicNote":
        claims = ClaimsBlock(self.claims_block)
        return self.with_claims(claims.with_explication(len(claims.claims()), line))

    def with_claims(self, claims: ClaimsBlock) -> "AtomicNote":
        rest = self._note.body[self._claims_end():]
        return AtomicNote(self._note.with_body(f"{claims.text}\n\n{rest}").text)

    def with_reference(self, block: str, place: ReferencePlace) -> "AtomicNote":
        return self.with_lines(REFERENCES, self.reference_groups().with_block(block, place).text)

    def with_line_last(self, heading: str, line: str) -> "AtomicNote":
        return self.with_lines(heading, joined(self.lines(heading), line, LINE_BREAK))

    def with_lines(self, heading: str, lines: str) -> "AtomicNote":
        rendered = f"# {heading}\n\n{lines}\n\n"
        pattern = part_pattern(heading)
        if pattern.search(self._note.body):
            body = pattern.sub(lambda _: rendered, self._note.body, count=1)
        else:
            body = self._with_part_inserted(heading, rendered)
        return AtomicNote(self._note.with_body(body).text)

    def _claims_end(self) -> int:
        first_part = PART_HEADING_RE.search(self._note.body)
        return first_part.start() if first_part else len(self._note.body)

    def _with_part_inserted(self, heading: str, rendered: str) -> str:
        later = PARTS[PARTS.index(heading) + 1:]
        following = [hit for part in later if (hit := part_pattern(part).search(self._note.body))]
        if not following:
            return f"{self._note.body.rstrip()}\n\n{rendered}"
        start = min(hit.start() for hit in following)
        return f"{self._note.body[:start]}{rendered}{self._note.body[start:]}"
