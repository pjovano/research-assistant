from __future__ import annotations

import os

import vault
from engine_slots import PARALLEL_VARIABLE, EngineSlots

MPS_FALLBACK = ("PYTORCH_ENABLE_MPS_FALLBACK", "1")
QUIET_GRPC = ("GRPC_VERBOSITY", "ERROR")
KEEP_SERVERS_ALIVE = ("SURYA_INFERENCE_KEEP_ALIVE", "1")
NO_PROMPT_CACHE = ("LLAMA_CPP_EXTRA_ARGS", "--cache-ram 0")
NO_LOGPROBS = ("SURYA_INFERENCE_LOGPROBS", "0")


class EngineEnvironment:
    VARIABLES = (MPS_FALLBACK, QUIET_GRPC, KEEP_SERVERS_ALIVE, NO_PROMPT_CACHE, NO_LOGPROBS)

    def __init__(self, machine: dict | None = None) -> None:
        self._slots = EngineSlots(vault.MACHINE if machine is None else machine)

    def apply(self) -> None:
        for name, value in self.VARIABLES:
            os.environ.setdefault(name, value)
        configured = self._slots.configured()
        if configured is not None:
            os.environ.setdefault(PARALLEL_VARIABLE, str(configured))
