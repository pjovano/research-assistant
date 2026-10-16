from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from _extract.correctionanchors import AnchorUnmatched, CorrectionContext, CorrectionRefused, CorrectionStale
from _extract.correctionnotes import Pair, Restore, ToNote
from _extract.correctionops import ROLE_HEADING, ROLES, Drop, Join, Move, Role, Split
from _extract.correctiontext import TrialText, Unit, letters_of
from _extract.failures import UsageFailure

APPLIED = "applied"
STALE = "stale"
UNMATCHED = "unmatched"
REFUSED = "refused"
OUTCOMES = (APPLIED, STALE, UNMATCHED, REFUSED)
FAMILIES = ("footnotes", "headings", "entry lists", "tables", "columns", "furniture", "paragraphs")
MAX_HEADING_LEVEL = 6
OP_KEY = "op"
FAMILY_KEY = "family"
CLASS_KEY = "defect_class"


class MalformedCorrections(UsageFailure, ValueError):
    pass


class _Fields:
    def __init__(self, raw: dict, position: int) -> None:
        self._raw = raw
        self._position = position

    def page(self, key: str = "page") -> int:
        value = self._raw.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise self.malformed(f"{key} must be a file page")
        return value

    def text(self, key: str, required: bool = True) -> str | None:
        value = self._raw.get(key)
        if value is None and not required:
            return None
        if not isinstance(value, (str, int)) or isinstance(value, bool) or not str(value).strip():
            raise self.malformed(f"{key} must be text")
        return str(value)

    def flag(self, key: str) -> bool:
        return self._raw.get(key) is True

    def level(self) -> int:
        value = self._raw.get("level")
        if not isinstance(value, int) or not 1 <= value <= MAX_HEADING_LEVEL:
            raise self.malformed(f"a heading takes a level from 1 to {MAX_HEADING_LEVEL}")
        return value

    def lines(self) -> tuple[int, int]:
        value = self._raw.get("lines")
        if not (isinstance(value, list) and len(value) == 2 and all(isinstance(line, int) for line in value)):
            raise self.malformed("lines must be [first, last]")
        return value[0], value[1]

    def malformed(self, reason: str) -> MalformedCorrections:
        return MalformedCorrections(f"correction {self._position}: {reason}: {self._raw!r}")


def _role(fields: _Fields) -> Role:
    to = fields.text("to")
    if to not in ROLES:
        raise fields.malformed(f"to must be one of {', '.join(ROLES)}")
    return Role(fields.page(), fields.text("anchor"), to, fields.level() if to == ROLE_HEADING else None)


OPERATIONS = {
    "split": lambda fields: Split(fields.page(), fields.text("anchor")),
    "join": lambda fields: Join(fields.page(), fields.text("anchor"), fields.flag("dehyphenate")),
    "move": lambda fields: Move(fields.page(), fields.text("anchor"), fields.page("target_page"),
                                fields.text("target_anchor", required=False)),
    "drop": lambda fields: Drop(fields.page(), fields.text("text")),
    "role": _role,
    "to-note": lambda fields: ToNote(fields.page(), fields.text("anchor"), fields.text("mark", required=False)),
    "pair": lambda fields: Pair(fields.page(), fields.text("mark"), fields.text("anchor")),
    "restore": lambda fields: Restore(fields.page(), *fields.lines(), fields.text("anchor", required=False)),
}


@dataclass(frozen=True)
class Correction:
    raw: dict
    operation: object

    @classmethod
    def parsed(cls, raw: object, position: int) -> Correction:
        if not isinstance(raw, dict):
            raise MalformedCorrections(f"correction {position} is not an object: {raw!r}")
        fields = _Fields(raw, position)
        if raw.get(OP_KEY) not in OPERATIONS:
            raise fields.malformed(f"op must be one of {', '.join(OPERATIONS)}")
        if raw.get(FAMILY_KEY) not in FAMILIES:
            raise fields.malformed(f"family must be one of {', '.join(FAMILIES)}")
        fields.text(CLASS_KEY)
        return cls(raw, OPERATIONS[raw[OP_KEY]](fields))


def parsed_corrections(raw: object) -> list[Correction]:
    if not isinstance(raw, list):
        raise MalformedCorrections("the corrections file must hold a JSON list of corrections")
    return [Correction.parsed(item, position) for position, item in enumerate(raw, start=1)]


@dataclass
class PassResult:
    text: TrialText
    outcomes: list[dict] = field(default_factory=list)
    applied: list[dict] = field(default_factory=list)

    def counts(self) -> dict:
        tally = Counter(outcome["outcome"] for outcome in self.outcomes)
        return {outcome: tally[outcome] for outcome in OUTCOMES}


class CorrectionPass:
    def __init__(self, context: CorrectionContext) -> None:
        self._context = context

    def run(self, text: TrialText, corrections: list[Correction]) -> PassResult:
        result = PassResult(text)
        for position, correction in enumerate(corrections, start=1):
            verdict = self._applied(text, correction)
            result.outcomes.append(self._entry(position, correction.raw, verdict))
            if verdict[0] == APPLIED:
                result.applied.append(correction.raw)
        return result

    def _applied(self, text: TrialText, correction: Correction) -> tuple[str, str | None]:
        before = list(text.units)
        try:
            effect = correction.operation.apply(text, self._context)
            LetterBalance(before, text.units).require(effect.dropped, effect.restored)
            return APPLIED, None
        except (CorrectionStale, CorrectionRefused) as outcome:
            text.units[:] = before
            return self._outcome_of(outcome), str(outcome)

    @staticmethod
    def _outcome_of(outcome: Exception) -> str:
        if isinstance(outcome, CorrectionStale):
            return STALE
        return UNMATCHED if isinstance(outcome, AnchorUnmatched) else REFUSED

    @staticmethod
    def _entry(position: int, raw: dict, verdict: tuple[str, str | None]) -> dict:
        outcome, reason = verdict
        entry = {"correction": position, OP_KEY: raw.get(OP_KEY), "page": raw.get("page"), "outcome": outcome}
        return {**entry, "reason": reason} if reason else entry


class LetterBalance:
    def __init__(self, before: list[Unit], after: list[Unit]) -> None:
        kept = {id(unit) for unit in before} & {id(unit) for unit in after}
        self._removed = letters_of("\n".join(unit.text for unit in before if id(unit) not in kept))
        self._added = letters_of("\n".join(unit.text for unit in after if id(unit) not in kept))

    def require(self, dropped: Counter, restored: Counter) -> None:
        expected = self._removed.copy()
        expected.subtract(dropped)
        expected.update(restored)
        if +expected != +self._added or any(count < 0 for count in expected.values()):
            raise CorrectionRefused("the correction would change the work's letters")
