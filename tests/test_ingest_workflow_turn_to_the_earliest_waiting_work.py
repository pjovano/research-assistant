from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource


class TurnOrder:
    def __init__(self, runtime: JsRuntime) -> None:
        self._runtime = runtime
        self._source = WorkflowSource.ingest().declarations("limit", "enqueueByRank", "rankOrder")

    def of(self, waiters: list[tuple[str, int | None]]) -> list[str]:
        program = (f"{self._source}\n"
                   f"const order = []\n"
                   f"const lock = limit(1)\n"
                   f"let release\n"
                   f"const held = lock(() => new Promise(done => {{ release = done }}))\n"
                   f"const turns = {json.dumps(waiters)}.map(([name, rank]) =>\n"
                   f"  rank === null ? lock(async () => order.push(name)) : lock(async () => order.push(name), rank))\n"
                   f"release()\n"
                   f"Promise.all([held, ...turns]).then(() => console.log(JSON.stringify(order)))")
        return json.loads(self._runtime.printed(program))


class TestTurnToTheEarliestWaitingWork(unittest.TestCase):
    def setUp(self) -> None:
        runtime = JsRuntime()
        runtime.require(self)
        self.turns = TurnOrder(runtime)

    def test_a_lower_ranked_waiter_takes_the_turn_before_a_higher_ranked_one_that_waited_longer(self) -> None:
        self.assertEqual(["work 2", "work 5", "work 9"],
                         self.turns.of([("work 5", 5), ("work 9", 9), ("work 2", 2)]))

    def test_waiters_of_one_rank_take_their_turns_in_arrival_order(self) -> None:
        self.assertEqual(["first", "second", "third"],
                         self.turns.of([("first", 3), ("second", 3), ("third", 3)]))

    def test_unranked_waiters_take_their_turns_in_arrival_order(self) -> None:
        self.assertEqual(["first", "second", "third"],
                         self.turns.of([("first", None), ("second", None), ("third", None)]))


if __name__ == "__main__":
    unittest.main()
