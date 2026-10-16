from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from engine_environment import NO_LOGPROBS, EngineEnvironment
from PIL import Image
from surya.inference.backends.openai_client import chat_completions_batch
from surya.inference.schema import PROMPT_TYPE_HIGH_ACCURACY_BBOX, BatchInputItem
from surya.settings import Settings

LOGPROBS_VARIABLE = NO_LOGPROBS[0]
PAGE_SIZE = (40, 40)
WHITE = "white"
ANSWER = "<div>read</div>"
MODEL = "surya"
LOGPROBS_ARGUMENT = "logprobs"


class RecordingCompletions:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def create(self, **request) -> SimpleNamespace:
        self.requests.append(request)
        choice = SimpleNamespace(message=SimpleNamespace(content=ANSWER), logprobs=None)
        return SimpleNamespace(choices=[choice], usage=SimpleNamespace(completion_tokens=1))


class TestEngineRequestsWithoutLogprobs(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(LOGPROBS_VARIABLE, None)

    def _settings(self) -> Settings:
        EngineEnvironment().apply()
        return Settings()

    def test_the_engine_asks_the_server_for_no_token_logprobs(self) -> None:
        self.assertFalse(self._settings().SURYA_INFERENCE_LOGPROBS)

    def test_a_page_request_carries_no_logprobs_argument(self) -> None:
        completions = RecordingCompletions()
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        page = BatchInputItem(image=Image.new("RGB", PAGE_SIZE, WHITE), prompt_type=PROMPT_TYPE_HIGH_ACCURACY_BBOX)
        chat_completions_batch([page], client, MODEL,
                               request_logprobs_default=self._settings().SURYA_INFERENCE_LOGPROBS)
        self.assertNotIn(LOGPROBS_ARGUMENT, completions.requests[0])

    def test_a_setting_already_in_the_environment_is_kept(self) -> None:
        os.environ[LOGPROBS_VARIABLE] = "1"
        self.assertTrue(self._settings().SURYA_INFERENCE_LOGPROBS)


if __name__ == "__main__":
    unittest.main()
