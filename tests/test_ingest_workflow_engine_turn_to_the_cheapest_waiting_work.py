from __future__ import annotations

import json
import unittest
from dataclasses import asdict, dataclass, field

from _workflow_source import JsRuntime, WorkflowSource

DECLARATIONS = ("CONVERTING_STEPS", "CONVERTED_TIER", "UNCONVERTED_TIER", "limit", "enqueueByRank", "rankOrder",
                "workCosts", "UNKNOWN_COST", "engineRank")
HARNESS = """
const order = []
const pending = []
const lock = limit(1)
let release
const held = lock(() => new Promise(done => { release = done }))
function request(waiter) {
  const turn = async () => {
    order.push(waiter.name)
    waiter.arrivals.forEach(arrival => pending.push(request(arrival)))
  }
  return lock(turn, engineRank(waiter.step, waiter.key, waiter.forced_pages))
}
async function settled() {
  await held
  while (pending.length) await pending.shift()
}
"""
LONG_BOOK_PAGES = 1100
ARTICLE_PAGES = 24
SHORT_ARRIVALS = 5
NO_PIXEL_PAGES = 0


@dataclass
class Waiter:
    name: str
    step: str
    key: int
    forced_pages: int = 0
    arrivals: list[Waiter] = field(default_factory=list)


def conversion(name: str, key: int, arrivals: list[Waiter] | None = None) -> Waiter:
    return Waiter(name, "drive-prep", key, arrivals=arrivals or [])


def trial(name: str, key: int, forced_pages: int = 0) -> Waiter:
    return Waiter(name, "drive-trial", key, forced_pages)


def arriving_one_per_turn(count: int, first_key: int) -> list[Waiter]:
    later: list[Waiter] = []
    for key in range(first_key + count - 1, first_key - 1, -1):
        later = [conversion(f"article {key}", key, later)]
    return later


class EngineTurns:
    def __init__(self, runtime: JsRuntime) -> None:
        self._runtime = runtime
        self._source = WorkflowSource.ingest().declarations(*DECLARATIONS) + HARNESS

    def order(self, pages: dict[int, int | list[int]], waiters: list[Waiter]) -> list[str]:
        costs = {key: cost if isinstance(cost, list) else [NO_PIXEL_PAGES, cost] for key, cost in pages.items()}
        program = (f"{self._source}\n"
                   f"Object.entries({json.dumps(costs)}).forEach(([key, cost]) => workCosts.set(key, cost))\n"
                   f"const waiters = {json.dumps([asdict(waiter) for waiter in waiters])}\n"
                   f"waiters.forEach(waiter => pending.push(request(waiter)))\n"
                   f"release()\n"
                   f"settled().then(() => console.log(JSON.stringify(order)))")
        return json.loads(self._runtime.printed(program))


class TestTheEngineTurnGoesToTheCheapestWaitingWork(unittest.TestCase):
    def setUp(self) -> None:
        runtime = JsRuntime()
        runtime.require(self)
        self.turns = EngineTurns(runtime)

    def test_a_short_work_arriving_while_a_long_one_waits_takes_the_turn_first(self) -> None:
        order = self.turns.order({1: LONG_BOOK_PAGES, 2: ARTICLE_PAGES},
                                 [conversion("long book", 1), conversion("article", 2)])
        self.assertEqual(["article", "long book"], order)

    def test_works_of_one_length_take_their_turns_by_the_lowest_key(self) -> None:
        order = self.turns.order({3: ARTICLE_PAGES, 2: ARTICLE_PAGES},
                                 [conversion("work 3", 3), conversion("work 2", 2)])
        self.assertEqual(["work 2", "work 3"], order)

    def test_a_work_whose_pages_were_not_counted_waits_behind_every_counted_work(self) -> None:
        order = self.turns.order({2: LONG_BOOK_PAGES}, [conversion("uncounted", 1), conversion("long book", 2)])
        self.assertEqual(["long book", "uncounted"], order)

    def test_a_long_work_read_from_its_text_layer_takes_the_turn_before_a_short_work_read_from_pixels(self) -> None:
        order = self.turns.order({1: [ARTICLE_PAGES, ARTICLE_PAGES], 2: [NO_PIXEL_PAGES, LONG_BOOK_PAGES]},
                                 [conversion("article from pixels", 1), conversion("long text-layer book", 2)])
        self.assertEqual(["long text-layer book", "article from pixels"], order)

    def test_the_font_scan_ranks_by_the_works_pages_as_its_conversion_does(self) -> None:
        order = self.turns.order({1: LONG_BOOK_PAGES, 2: ARTICLE_PAGES},
                                 [conversion("long book", 1), Waiter("article font scan", "drive-fonts", 2)])
        self.assertEqual(["article font scan", "long book"], order)


class TestAConvertedWorkTakesTheTurnAheadOfAnUnconvertedOne(unittest.TestCase):
    def setUp(self) -> None:
        runtime = JsRuntime()
        runtime.require(self)
        self.turns = EngineTurns(runtime)

    def test_a_long_works_trial_takes_the_turn_before_a_short_works_conversion(self) -> None:
        order = self.turns.order({1: LONG_BOOK_PAGES, 2: ARTICLE_PAGES},
                                 [conversion("article", 2), trial("long book trial", 1)])
        self.assertEqual(["long book trial", "article"], order)

    def test_a_retrial_takes_the_turn_before_a_short_works_conversion(self) -> None:
        order = self.turns.order({1: LONG_BOOK_PAGES, 2: ARTICLE_PAGES},
                                 [conversion("article", 2), Waiter("long book retrial", "drive-retrial", 1)])
        self.assertEqual(["long book retrial", "article"], order)

    def test_among_converted_works_the_trial_forcing_fewer_pages_goes_first(self) -> None:
        order = self.turns.order({}, [trial("forcing a chapter", 1, forced_pages=40), trial("forcing nothing", 2)])
        self.assertEqual(["forcing nothing", "forcing a chapter"], order)


class TestALongWorkIsNotStarved(unittest.TestCase):
    def setUp(self) -> None:
        runtime = JsRuntime()
        runtime.require(self)
        self.turns = EngineTurns(runtime)
        self.pages = {1: LONG_BOOK_PAGES} | {key: ARTICLE_PAGES for key in range(2, 2 + SHORT_ARRIVALS)}

    def test_a_long_work_takes_the_turn_once_no_shorter_work_waits(self) -> None:
        order = self.turns.order(self.pages, [conversion("long book", 1), *arriving_one_per_turn(SHORT_ARRIVALS, 2)])
        self.assertEqual("long book", order[-1])

    def test_a_long_works_trial_is_not_overtaken_by_short_works_arriving_one_per_turn(self) -> None:
        [first_article] = arriving_one_per_turn(SHORT_ARRIVALS, 2)
        first_article.arrivals.append(trial("long book trial", 1))
        order = self.turns.order(self.pages, [first_article])
        self.assertEqual(["article 2", "long book trial"], order[:2])


if __name__ == "__main__":
    unittest.main()
