from __future__ import annotations

from pathlib import Path

import vault
from engine_guard import FailedInferenceRequests
from engine_slots import SlotsAgreement
from engine_reach import EngineReach, EngineUnreachable
from engine_turn import TURN_NAME, WAITING_NAME, TurnClock, YieldingEngineTurn
from surya_servers import PREFETCH_RUN_NAME, EngineRun

from _drive.work import QUEUE_NAME
from _extract.build import ConversionPlan
from _extract.enginecost import CheapestFirst, FontRecord
from _extract.layer import TextLayer
from _extract.paths import PdfLocator
from _extract.report import ProbeReport
from _extract.scanlayer import LayerCoverage
from _extract.request import ExtractionRequest
from _extract.stage import EngineSession, StageCommands

SKIP_REVIEWED = "reviewed"
SKIP_BODY = "carries a body"
SKIP_CACHED = "cached"
SKIP_FONTS_UNSETTLED = "font repair unsettled"
SKIP_LAYER_UNSAMPLED = "text layer not yet sampled"
FIRST_KEY = 1
FONT_REPAIR_POLL_SECONDS = 30


class PrefetchConversion:
    def __init__(self, pdf: str, record: FontRecord | None = None) -> None:
        record = record or FontRecord({})
        self._pdf_path, self._note = PdfLocator().with_note(pdf)
        self._probe = ProbeReport(self._pdf_path, self._note).as_dict()
        self._reading = record.scan_reading(bool(self._probe["scanned"]))
        request = ExtractionRequest((), self._reading.reads_every_page_from_pixels, record.pixel_pages_listing, False)
        self._plan = ConversionPlan(self._pdf_path, StageCommands.options_for(self._pdf_path, request))
        self._page_count = TextLayer(self._pdf_path).page_count()

    def skip_reason(self) -> str | None:
        if self._probe.get("reviewed"):
            return SKIP_REVIEWED
        if self._probe.get("body_exists"):
            return SKIP_BODY
        if self._reading.awaits_layer_sample(LayerCoverage.of_probe(self._probe)):
            return SKIP_LAYER_UNSAMPLED
        return SKIP_CACHED if self._plan.is_cached(self._page_count) else None

    def convert(self) -> None:
        scratch = vault.SCRATCH_DIR
        turn = YieldingEngineTurn(scratch / TURN_NAME, scratch / WAITING_NAME)
        with EngineSession(EngineRun(scratch / PREFETCH_RUN_NAME, turn, SlotsAgreement.on_this_machine())):
            EngineReach().require()
            self._plan.blocks(self._page_count)


class BackfillPrefetch:
    def __init__(self, backfill_dir: Path, conversion_of=PrefetchConversion,
                 order: CheapestFirst | None = None, clock: TurnClock | None = None) -> None:
        self._backfill_dir = backfill_dir
        self._conversion_of = conversion_of
        self._cheapest_first = order or CheapestFirst.for_backfill(backfill_dir)
        self._clock = clock or TurnClock()
        self.converted: list[str] = []
        self.skipped: list[dict] = []
        self.failed: list[dict] = []
        self.halt: str | None = None

    def run(self, limit: int | None, keys: tuple[int, ...] = (), awaits_fonts: bool = False) -> None:
        unsettled = self._walked(self._queued(keys), limit)
        while unsettled and awaits_fonts and not self._is_done(limit):
            self._clock.sleep(FONT_REPAIR_POLL_SECONDS)
            unsettled = self._walked(unsettled, limit)
        if not self._is_done(limit):
            self._skip_each(unsettled, SKIP_FONTS_UNSETTLED)

    def _walked(self, pdfs: list[str], limit: int | None) -> list[str]:
        unsettled = []
        for pdf in pdfs:
            if self._is_done(limit):
                break
            if self._font_state(pdf).is_settled:
                self._carry(pdf)
            else:
                unsettled.append(pdf)
        return unsettled

    def _skip_each(self, pdfs: list[str], reason: str) -> None:
        for pdf in pdfs:
            self._skip(pdf, reason)

    def _is_done(self, limit: int | None) -> bool:
        return self.halt is not None or (limit is not None and len(self.converted) >= limit)

    def as_dict(self) -> dict:
        return {"converted": self.converted, "skipped": self.skipped, "failed": self.failed, "halt": self.halt}

    def _queued(self, keys: tuple[int, ...]) -> list[str]:
        lines = (self._backfill_dir / QUEUE_NAME).read_text(encoding="utf-8").splitlines()
        listed = enumerate((line.strip() for line in lines if line.strip()), start=FIRST_KEY)
        return self._cheapest_first.ordered([pdf for key, pdf in listed if not keys or key in keys])

    def _carry(self, pdf: str) -> None:
        try:
            self._prefetched(pdf)
        except (FailedInferenceRequests, EngineUnreachable) as failure:
            self.halt = f"{pdf}: {failure}"
        except Exception as failure:
            self.failed.append({"pdf": pdf, "failure": f"{type(failure).__name__}: {failure}"})

    def _prefetched(self, pdf: str) -> None:
        font_state = self._font_state(pdf)
        conversion = self._conversion_of(pdf, font_state)
        reason = conversion.skip_reason()
        if reason:
            self._skip(pdf, reason)
            return
        conversion.convert()
        self.converted.append(pdf)

    def _skip(self, pdf: str, reason: str) -> None:
        self.skipped.append({"pdf": pdf, "reason": reason})

    def _font_state(self, pdf: str) -> FontRecord:
        return FontRecord.of_backfill_work(self._backfill_dir, Path(pdf))
