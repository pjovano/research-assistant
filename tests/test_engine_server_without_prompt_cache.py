from __future__ import annotations

import os
import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _extract.engine import MarkerEngine
from engine_environment import NO_PROMPT_CACHE, EngineEnvironment
from surya.settings import Settings

EXTRA_ARGS = NO_PROMPT_CACHE[0]
PROMPT_CACHE_FLAG = "--cache-ram"
DISABLED_SIZE = "0"
OWN_EXTRA_ARGS = "--threads 4"


class TestEngineServerWithoutPromptCache(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(EXTRA_ARGS, None)

    def _server_arguments(self) -> list[str]:
        EngineEnvironment().apply()
        return Settings().LLAMA_CPP_EXTRA_ARGS.split()

    def test_the_llama_server_is_started_with_its_prompt_cache_disabled(self) -> None:
        arguments = self._server_arguments()
        flag_at = arguments.index(PROMPT_CACHE_FLAG)
        self.assertEqual(DISABLED_SIZE, arguments[flag_at + 1])

    def test_extra_arguments_already_in_the_environment_are_kept(self) -> None:
        os.environ[EXTRA_ARGS] = OWN_EXTRA_ARGS
        self.assertEqual(OWN_EXTRA_ARGS.split(), self._server_arguments())

    def test_the_setting_is_in_place_once_the_engine_is_built_before_any_model_loads(self) -> None:
        MarkerEngine()
        self.assertEqual(NO_PROMPT_CACHE[1], os.environ.get(EXTRA_ARGS))


if __name__ == "__main__":
    unittest.main()
