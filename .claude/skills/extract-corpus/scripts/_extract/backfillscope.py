from __future__ import annotations

from _drive.work import SetAside, WorkDirectory, WorkStops
from _extract.backfillparts import SCOPE_PARTS, PartedDispatch
from _extract.backfillrunner import ExtractScript
from _extract.spans import ScopePoint

MAX_SCOPE_RUNS = 3
STATE_RESCOPE = "rescope"
STATE_REJUDGE = "rejudge"
REJUDGED_RUN_FIELD = "rejudged_run"
EXCLUDE_FLAG = "--exclude"
NAMED_PAGES_FIELD = "named_pages"
DOUBT_PUT_FIELD = "doubt_put"
SCOPE_NOTES_FIELD = "scope_notes"
PAGE_OPTION = "--page"


def page_of(point: str, page_count: int) -> int:
    parsed = ScopePoint.parsed(point)
    return page_count + 1 if parsed.is_end else parsed.file_page


def excluded_spans(scope: list[str]) -> list[tuple[str, str]]:
    flags = [index for index, argument in enumerate(scope) if argument == EXCLUDE_FLAG]
    return [(scope[index + 1], scope[index + 2]) for index in flags]


class ScopeDispatch(PartedDispatch):
    def __init__(self, work: WorkDirectory) -> None:
        super().__init__(work, SCOPE_PARTS)


class VerdictSpan:
    def __init__(self, span: dict, page_count: int) -> None:
        self._span = span
        self._page_count = page_count
        self.pages = [page_of(span["start"], page_count), page_of(span["resume"], page_count)]

    @property
    def is_ambiguous(self) -> bool:
        return bool(self._span.get("ambiguous"))

    @property
    def exclude_arguments(self) -> list[str]:
        return [EXCLUDE_FLAG, self._span["start"], self._span["resume"]]

    @property
    def doubt(self) -> str:
        return f"the span {self._bounds} is flagged ambiguous: {self._span.get('reason')}"

    @property
    def kept_note(self) -> str:
        return f"kept the stretch {self._bounds}, which the section scoper doubted twice: {self._span.get('reason')}"

    def unseen(self, listed: list[int]) -> set[int]:
        first, resume = self.pages
        crossed = set(range(first + 1, resume))
        return (crossed | self._see_pages()) - set(listed)

    def _see_pages(self) -> set[int]:
        named = self._span.get("see") or []
        return {page for page in named if isinstance(page, int) and 1 <= page <= self._page_count}

    @property
    def _bounds(self) -> str:
        return f"{self._span['start']!r} to {self._span['resume']!r}"


class ScopeSettlement:
    def __init__(self, work: WorkDirectory, state: dict, script: ExtractScript) -> None:
        self._work = work
        self._state = state
        self._script = script
        self._dispatch = ScopeDispatch(work)

    def settle(self) -> list[str]:
        listed = self._dispatch.listed()
        verdicts = self._dispatch.merged(self._state["scope_runs"])
        omitted = verdicts.omitted(listed)
        if omitted:
            self._rejudge(omitted)
        page_count = self._work.load("probe.json")["page_count"]
        spans = [VerdictSpan(span, page_count) for span in verdicts.findings]
        self._list_unseen_pages(spans, listed)
        excluded = self._settle_doubts(spans)
        self._state["scope"] = [arg for span in excluded for arg in span.exclude_arguments] or ["--exclude-nothing"]
        self._work.save_state(self._state)
        return self._state["scope"]

    def rescope(self, reason: str) -> None:
        self._state["scope_runs"] += 1
        self._work.save_state(self._state)
        if self._state["scope_runs"] >= MAX_SCOPE_RUNS:
            raise SetAside("the section scoper failed three times: " + reason)
        raise WorkStops(STATE_RESCOPE, note=reason, parts=self._dispatch.dispatch(self._state["scope_runs"]))

    def _rejudge(self, omitted: list[int]) -> None:
        run = self._state["scope_runs"]
        if self._state.get(REJUDGED_RUN_FIELD) == run:
            self.rescope("the verdicts' pages_judged omits listed pages twice")
        self._state[REJUDGED_RUN_FIELD] = run
        self._work.save_state(self._state)
        raise WorkStops(STATE_REJUDGE, parts=self._dispatch.repair(run, omitted))

    def _list_unseen_pages(self, spans: list[VerdictSpan], listed: list[int]) -> None:
        unseen = sorted(set().union(*(span.unseen(listed) for span in spans)))
        if not unseen:
            return
        named = sorted(set(self._state.get(NAMED_PAGES_FIELD, [])) | set(unseen))
        self._state[NAMED_PAGES_FIELD] = named
        options = [arg for page in named for arg in (PAGE_OPTION, str(page))]
        self._dispatch.write(self._script.checked("scope", self._work.pdf, *options).stdout)
        self.rescope("the scope listing now also names file pages " + ", ".join(map(str, unseen)))

    def _settle_doubts(self, spans: list[VerdictSpan]) -> list[VerdictSpan]:
        doubted = [span for span in spans if span.is_ambiguous]
        if doubted and not self._state.get(DOUBT_PUT_FIELD):
            self._state[DOUBT_PUT_FIELD] = True
            self.rescope("; ".join(span.doubt for span in doubted))
        self._state[SCOPE_NOTES_FIELD] = [span.kept_note for span in doubted]
        return [span for span in spans if not span.is_ambiguous]
