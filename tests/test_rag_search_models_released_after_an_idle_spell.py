from __future__ import annotations

import inspect
import unittest

from _support import LiveTree

LiveTree.activate()

import rag
from _rag.chunking import Child
from _rag_fakes import hashed_vector, temp_directory

IDLE_SECONDS = 300.0
BASENAME = "Author - 2000 - Work"
PASSAGE = "being and nothing"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ReleaseCounter:
    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> None:
        self.count += 1


class IdleReleaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.released = ReleaseCounter()
        self.idle = rag.IdleRelease([self.released], IDLE_SECONDS, self.clock)
        self.tool = self.idle.served(lambda: None)

    def idle_for(self, seconds: float) -> None:
        self.clock.advance(seconds)
        self.idle.release_if_idle()


class TestTheModelsAreReleasedOnceTheToolsFallIdle(IdleReleaseTestCase):
    def test_nothing_is_released_before_the_first_tool_call(self) -> None:
        self.idle_for(IDLE_SECONDS * 10)
        self.assertEqual(0, self.released.count)

    def test_nothing_is_released_while_the_tools_are_in_use(self) -> None:
        self.tool()
        self.idle_for(IDLE_SECONDS - 1)
        self.assertEqual(0, self.released.count)

    def test_the_models_are_released_once_the_idle_spell_is_reached(self) -> None:
        self.tool()
        self.idle_for(IDLE_SECONDS)
        self.assertEqual(1, self.released.count)

    def test_released_models_are_not_released_again_until_a_tool_loads_them(self) -> None:
        self.tool()
        self.idle_for(IDLE_SECONDS)
        self.idle_for(IDLE_SECONDS)
        self.assertEqual(1, self.released.count)

    def test_a_tool_call_after_a_release_starts_a_new_idle_spell(self) -> None:
        self.tool()
        self.idle_for(IDLE_SECONDS)
        self.tool()
        self.idle_for(IDLE_SECONDS)
        self.assertEqual(2, self.released.count)


class TestAServedToolKeepsItsSignature(unittest.TestCase):
    def test_the_served_tool_shows_the_signature_its_schema_is_read_from(self) -> None:
        def search(query: str, k: int = 8) -> list[dict]:
            return []
        served = rag.IdleRelease([]).served(search)
        self.assertEqual(inspect.signature(search), inspect.signature(served))

    def test_the_served_tool_returns_what_the_tool_returns(self) -> None:
        served = rag.IdleRelease([]).served(lambda query: [query])
        self.assertEqual(["Hegel"], served("Hegel"))


class TestAReleasedEmbeddingStoreLoadsAgainOnTheNextQuery(unittest.TestCase):
    def setUp(self) -> None:
        self.store = rag.EmbeddingStore(temp_directory(self) / "chroma")
        child = Child(chunk_id="chunk", parent_id="parent", basename=BASENAME, text=PASSAGE, context=BASENAME,
                      embedded_text=PASSAGE, metadata={})
        self.store.add([child], [hashed_vector(PASSAGE)])

    def test_the_store_answers_a_query_after_it_is_released(self) -> None:
        self.store.release()
        self.assertEqual(["chunk"], self.store.nearest(hashed_vector(PASSAGE), 1))


if __name__ == "__main__":
    unittest.main()
