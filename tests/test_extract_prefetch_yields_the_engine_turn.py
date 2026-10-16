from __future__ import annotations

import contextlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from engine_guard import FailedInferenceRequests
from engine_reach import NO_METAL, EngineUnreachable
from engine_turn import EngineTurn, TurnClock, YieldingEngineTurn
from surya_servers import EngineRun, IdleClock, IdleReaper

from _extract.cache import MarkerCache
from _extract.engine import MODE_FORCED_OCR, MODE_TEXT_LAYER
from _extract.enginecost import UNKNOWN_COST, CheapestFirst, EngineCost, FontRecord
from _extract.prefetch import SKIP_BODY, SKIP_CACHED, SKIP_FONTS_UNSETTLED, BackfillPrefetch, PrefetchConversion
from _vaults import LinedPdf, TempVault

DEAD_PID = 999999
BASENAME = "Doe - 2020 - A Work"
NOTE_TEXT = "---\ntitle: A Work\ntype: journalArticle\n---\n\n[Doe - 2020 - A Work.pdf](zotero://open-pdf/x)\n"
PAGES = [["The argument of the work runs on across this page,", "and the next line carries it further."]] * 3
QUEUED = ["A - 2001 - First.pdf", "B - 2002 - Second.pdf", "C - 2003 - Third.pdf"]
FONTS_CHECKED_STATE = '{"fonts_checked": true}'
PIXELS_ONLY_STATE = '{"pixels_only": true}'


class ReleasingClock(TurnClock):
    def __init__(self, release, polls_before_release: int = 2) -> None:
        self._release = release
        self._polls_left = polls_before_release
        self.polls = 0

    def sleep(self, seconds: float) -> None:
        self.polls += 1
        self._polls_left -= 1
        if self._polls_left == 0:
            self._release()


class TurnCase(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.lock_path = root / "engine-turn.lock"
        self.waiting_dir = root / "engine-waiting"

    def turn(self) -> EngineTurn:
        return EngineTurn(self.lock_path, self.waiting_dir)

    def yielding(self, clock: TurnClock) -> YieldingEngineTurn:
        return YieldingEngineTurn(self.lock_path, self.waiting_dir, clock, poll_seconds=0)

    def mark_waiting(self, pid: int) -> Path:
        self.waiting_dir.mkdir(parents=True, exist_ok=True)
        marker = self.waiting_dir / str(pid)
        marker.touch()
        return marker


class TestTheYieldingTurn(TurnCase):
    def test_a_yielding_taker_waits_while_another_holds_the_turn(self) -> None:
        holder = self.turn()
        holder.take()
        clock = ReleasingClock(holder.give_back)
        self.yielding(clock).take()
        self.assertEqual(2, clock.polls)

    def test_a_yielding_taker_waits_while_another_process_waits_for_the_turn(self) -> None:
        marker = self.mark_waiting(os.getppid())
        clock = ReleasingClock(marker.unlink, polls_before_release=3)
        self.yielding(clock).take()
        self.assertEqual(3, clock.polls)

    def test_a_waiting_marker_of_a_dead_process_is_no_wait(self) -> None:
        self.mark_waiting(DEAD_PID)
        clock = ReleasingClock(lambda: None)
        self.yielding(clock).take()
        self.assertEqual(0, clock.polls)

    def test_a_free_turn_is_taken_at_once(self) -> None:
        clock = ReleasingClock(lambda: None)
        self.yielding(clock).take()
        self.assertEqual(0, clock.polls)


class TestAnEngineRunHoldsTheTurn(TurnCase):
    def test_a_started_run_holds_the_turn(self) -> None:
        run = EngineRun(self.lock_path.with_name("engine-run.json"), self.turn())
        run.started()
        self.addCleanup(run.finished)
        self.assertFalse(self.turn().try_take())

    def test_a_finished_run_gives_the_turn_back(self) -> None:
        run = EngineRun(self.lock_path.with_name("engine-run.json"), self.turn())
        run.started()
        run.finished()
        self.assertTrue(self.turn().try_take())

    def test_a_started_run_leaves_no_waiting_marker(self) -> None:
        run = EngineRun(self.lock_path.with_name("engine-run.json"), self.turn())
        run.started()
        self.addCleanup(run.finished)
        self.assertEqual([], list(self.waiting_dir.iterdir()))


class TestTheTurnBesideTheRunsRecord(TurnCase):
    def test_a_run_without_a_turn_takes_the_one_beside_its_record(self) -> None:
        run = EngineRun(self.lock_path.with_name("engine-run.json"))
        run.started()
        self.addCleanup(run.finished)
        self.assertFalse(self.turn().try_take())


class FakeRun:
    def __init__(self, in_progress: bool) -> None:
        self._in_progress = in_progress

    def in_progress(self) -> bool:
        return self._in_progress


class FakeLogs:
    def last_active(self) -> float:
        return 0.0


class TestTheReaperAndAPrefetchConversion(unittest.TestCase):
    def test_a_prefetch_conversion_in_progress_keeps_the_servers_up(self) -> None:
        reaper = IdleReaper(IdleClock(0.0, FakeLogs()), run=FakeRun(False), prefetch=FakeRun(True))
        self.assertFalse(reaper.is_due(1.0))

    def test_no_conversion_in_progress_lets_idle_servers_stop(self) -> None:
        reaper = IdleReaper(IdleClock(0.0, FakeLogs()), run=FakeRun(False), prefetch=FakeRun(False))
        self.assertTrue(reaper.is_due(1.0))


class FakeConversion:
    reasons: dict[str, str] = {}
    converted: list[str] = []
    read_from_pixels: list[str] = []
    pages_from_pixels: dict[str, str] = {}
    failing_requests: list[str] = []
    unready = False

    def __init__(self, pdf: str, record: FontRecord) -> None:
        self._pdf = pdf
        if record.scan_reading(False).reads_every_page_from_pixels:
            FakeConversion.read_from_pixels.append(pdf)
        if record.pixel_pages_listing:
            FakeConversion.pages_from_pixels[pdf] = record.pixel_pages_listing

    def skip_reason(self) -> str | None:
        return self.reasons.get(self._pdf)

    def convert(self) -> None:
        if FakeConversion.unready:
            raise EngineUnreachable(NO_METAL)
        if self._pdf in FakeConversion.failing_requests:
            raise FailedInferenceRequests(len(PAGES))
        FakeConversion.converted.append(self._pdf)


class FakeCosts:
    def __init__(self, costs: dict[str, EngineCost]) -> None:
        self._costs = costs

    def of(self, pdf_path: Path, _record: FontRecord) -> EngineCost:
        return self._costs.get(pdf_path.name, UNKNOWN_COST)


def cheapest_first(costs: dict[str, EngineCost] | None = None) -> CheapestFirst:
    return CheapestFirst(FakeCosts(costs or {}), Path, lambda _path: FontRecord({}))


def text_layer(pages: int) -> EngineCost:
    return EngineCost(0, pages)


class PrefetchWalkCase(unittest.TestCase):
    def setUp(self) -> None:
        self.backfill = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (self.backfill / "queue.txt").write_text("\n".join(QUEUED) + "\n", encoding="utf-8")
        FakeConversion.reasons = {}
        FakeConversion.converted = []
        FakeConversion.read_from_pixels = []
        FakeConversion.pages_from_pixels = {}
        FakeConversion.failing_requests = []
        FakeConversion.unready = False
        for pdf in QUEUED:
            self.record_state(pdf, FONTS_CHECKED_STATE)

    def record_state(self, pdf: str, state: str) -> None:
        work = self.backfill / "works" / Path(pdf).stem
        work.mkdir(parents=True, exist_ok=True)
        (work / "state.json").write_text(state, encoding="utf-8")

    def unsettle(self, pdf: str) -> None:
        (self.backfill / "works" / Path(pdf).stem / "state.json").unlink()

    def walked(self, limit: int | None = None, costs: dict[str, EngineCost] | None = None,
               keys: tuple[int, ...] = ()) -> BackfillPrefetch:
        prefetch = BackfillPrefetch(self.backfill, FakeConversion, cheapest_first(costs))
        prefetch.run(limit, keys)
        return prefetch


class TestThePrefetchWalk(PrefetchWalkCase):
    def test_works_of_one_cost_are_converted_in_queue_order(self) -> None:
        costs = dict.fromkeys(QUEUED, text_layer(40))
        self.assertEqual(QUEUED, self.walked(costs=costs).converted)

    def test_the_work_of_the_fewest_pages_is_converted_first(self) -> None:
        costs = {QUEUED[0]: text_layer(1100), QUEUED[1]: text_layer(30), QUEUED[2]: text_layer(200)}
        self.assertEqual([QUEUED[1], QUEUED[2], QUEUED[0]], self.walked(costs=costs).converted)

    def test_a_long_work_read_from_its_text_layer_is_converted_before_a_short_work_read_from_pixels(self) -> None:
        costs = {QUEUED[0]: EngineCost(30, 30), QUEUED[1]: text_layer(900)}
        self.assertEqual([QUEUED[1], QUEUED[0]], self.walked(costs=costs).converted[:2])

    def test_a_long_text_layer_work_is_converted_after_a_shorter_work_with_a_few_pixel_pages(self) -> None:
        costs = {QUEUED[0]: EngineCost(30, 30), QUEUED[1]: text_layer(900), QUEUED[2]: EngineCost(2, 400)}
        self.assertEqual([QUEUED[2], QUEUED[1], QUEUED[0]], self.walked(costs=costs).converted)

    def test_a_work_whose_cost_is_unknown_is_converted_after_every_costed_work(self) -> None:
        costs = {QUEUED[1]: text_layer(900), QUEUED[2]: text_layer(20)}
        self.assertEqual([QUEUED[2], QUEUED[1], QUEUED[0]], self.walked(costs=costs).converted)

    def test_a_work_whose_state_reads_pixels_only_is_converted_from_pixels(self) -> None:
        self.record_state(QUEUED[2], PIXELS_ONLY_STATE)
        self.walked()
        self.assertEqual([QUEUED[2]], FakeConversion.read_from_pixels)

    def test_a_work_whose_state_names_pixel_pages_is_converted_reading_those_pages_from_pixels(self) -> None:
        self.record_state(QUEUED[1], '{"fonts_checked": true, "pixel_pages": "3,9-11"}')
        self.walked()
        self.assertEqual({QUEUED[1]: "3,9-11"}, FakeConversion.pages_from_pixels)

    def test_a_work_its_conversion_skips_is_not_converted(self) -> None:
        FakeConversion.reasons = {QUEUED[0]: "cached"}
        self.assertEqual(QUEUED[1:], self.walked().converted)

    def test_the_keys_bound_the_walk_to_the_works_listed_under_them(self) -> None:
        self.assertEqual([QUEUED[0], QUEUED[2]], self.walked(keys=(1, 3)).converted)

    def test_the_works_count_bounds_the_conversions(self) -> None:
        FakeConversion.reasons = {QUEUED[0]: "reviewed"}
        self.assertEqual(QUEUED[1:2], self.walked(limit=1).converted)


class SettlingClock(TurnClock):
    def __init__(self, settle) -> None:
        self._settle = settle
        self.sleeps = 0

    def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        self._settle()


class TestAPrefetchOfAWorkWhoseFontRepairIsUnsettled(PrefetchWalkCase):
    def awaited(self, clock: TurnClock) -> BackfillPrefetch:
        prefetch = BackfillPrefetch(self.backfill, FakeConversion, cheapest_first(), clock)
        prefetch.run(None, awaits_fonts=True)
        return prefetch

    def test_the_work_is_not_converted(self) -> None:
        self.unsettle(QUEUED[0])
        self.assertEqual(QUEUED[1:], self.walked().converted)

    def test_the_work_is_skipped_naming_the_unsettled_font_repair(self) -> None:
        self.unsettle(QUEUED[0])
        self.assertIn({"pdf": QUEUED[0], "reason": SKIP_FONTS_UNSETTLED}, self.walked().skipped)

    def test_a_walk_that_awaits_the_font_repair_converts_the_work_once_it_settles(self) -> None:
        self.unsettle(QUEUED[0])
        clock = SettlingClock(lambda: self.record_state(QUEUED[0], PIXELS_ONLY_STATE))
        self.assertEqual(QUEUED[1:] + QUEUED[:1], self.awaited(clock).converted)

    def test_the_work_settled_while_the_walk_awaits_is_converted_as_its_font_repair_settled_it(self) -> None:
        self.unsettle(QUEUED[0])
        self.awaited(SettlingClock(lambda: self.record_state(QUEUED[0], PIXELS_ONLY_STATE)))
        self.assertEqual(QUEUED[:1], FakeConversion.read_from_pixels)

    def test_a_walk_with_every_work_settled_never_waits(self) -> None:
        clock = SettlingClock(lambda: None)
        self.awaited(clock)
        self.assertEqual(0, clock.sleeps)


class TestAPrefetchWhoseEngineRequestsFail(PrefetchWalkCase):
    def test_the_walk_stops_at_the_first_work_whose_requests_failed(self) -> None:
        FakeConversion.failing_requests = [QUEUED[1]]
        self.assertEqual(QUEUED[:1], self.walked().converted)

    def test_the_failure_is_reported_as_the_halt(self) -> None:
        FakeConversion.failing_requests = [QUEUED[0]]
        self.assertIn(f"{QUEUED[0]}: {len(PAGES)} engine requests failed", self.walked().halt)

    def test_an_engine_without_metal_converts_nothing_and_halts_naming_it(self) -> None:
        FakeConversion.unready = True
        prefetch = self.walked()
        self.assertEqual(([], True), (prefetch.converted, NO_METAL in prefetch.halt))

    def test_a_walk_whose_requests_all_answered_reports_no_halt(self) -> None:
        self.assertIsNone(self.walked().halt)


class LibraryWorkCase(unittest.TestCase):
    def setUp(self) -> None:
        self.vault = TempVault("LIBRARY_DIR", "CORPUS_DIR").activate()
        self.addCleanup(self.vault.discard)
        self.pdf = LinedPdf(self.vault.library / f"{BASENAME}.pdf", PAGES).write()
        self.note = self.vault.corpus / f"{BASENAME}.md"
        self.note.write_text(NOTE_TEXT, encoding="utf-8")



class TestWhatAConversionSkips(LibraryWorkCase):
    def reason(self) -> str | None:
        return PrefetchConversion(self.pdf.name).skip_reason()

    def test_an_uncached_work_without_a_body_is_converted(self) -> None:
        self.assertIsNone(self.reason())

    def test_a_work_carrying_a_body_is_skipped(self) -> None:
        self.note.write_text(NOTE_TEXT + "\nThe body.\n", encoding="utf-8")
        self.assertEqual(SKIP_BODY, self.reason())

    def test_a_work_whose_conversion_is_cached_is_skipped(self) -> None:
        for mode in (MODE_TEXT_LAYER, MODE_FORCED_OCR):
            MarkerCache(self.pdf, mode).save(list(range(1, len(PAGES) + 1)), {})
        self.assertEqual(SKIP_CACHED, self.reason())


class UnreachableEngine:
    def require(self) -> None:
        raise EngineUnreachable(NO_METAL)


class TestAConversionOnAnEngineWithoutMetal(LibraryWorkCase):
    def test_the_conversion_is_refused_before_the_engine_runs_and_nothing_is_cached(self) -> None:
        with (mock.patch("_extract.prefetch.EngineSession", lambda _run: contextlib.nullcontext()),
              mock.patch("_extract.prefetch.EngineReach", UnreachableEngine)):
            with self.assertRaises(EngineUnreachable):
                PrefetchConversion(self.pdf.name).convert()
        self.assertFalse(MarkerCache(self.pdf, MODE_TEXT_LAYER).is_current())


if __name__ == "__main__":
    unittest.main()
