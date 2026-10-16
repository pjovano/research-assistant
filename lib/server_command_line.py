from __future__ import annotations

import re
from pathlib import Path

SERVER_MODULE = re.compile(r"surya\.[a-z_]+\.server")
MODULE_FLAG = "-m"
MODULE_FLAG_POSITION = 1
MODULE_NAME_POSITION = MODULE_FLAG_POSITION + 1
LLAMA_SERVER_PROGRAM = "llama-server"
ALIAS_FLAG = "--alias"


class ServerCommandLine:
    def __init__(self, recorded_models: frozenset[str] = frozenset(),
                 module: re.Pattern[str] = SERVER_MODULE) -> None:
        self._recorded_models = recorded_models
        self._module = module

    def matches(self, arguments: list[str]) -> bool:
        return self._runs_a_server_module(arguments) or self._serves_a_recorded_model(arguments)

    def _runs_a_server_module(self, arguments: list[str]) -> bool:
        return self._runs_a_module(arguments) and bool(self._module.fullmatch(arguments[MODULE_NAME_POSITION]))

    @staticmethod
    def _runs_a_module(arguments: list[str]) -> bool:
        return len(arguments) > MODULE_NAME_POSITION and arguments[MODULE_FLAG_POSITION] == MODULE_FLAG

    def _serves_a_recorded_model(self, arguments: list[str]) -> bool:
        return self._runs_llama_server(arguments) and self._alias(arguments) in self._recorded_models

    @staticmethod
    def _runs_llama_server(arguments: list[str]) -> bool:
        return bool(arguments) and Path(arguments[0]).name == LLAMA_SERVER_PROGRAM

    @staticmethod
    def _alias(arguments: list[str]) -> str | None:
        value_at = arguments.index(ALIAS_FLAG) + 1 if ALIAS_FLAG in arguments else len(arguments)
        return arguments[value_at] if value_at < len(arguments) else None
