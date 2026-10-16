from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
import types
import unittest
from typing import Sequence

SPAWN_MODULE = "surya.inference.backends.spawn"
ENTRY_POINT = "attach_or_spawn"
BACKEND_ARGUMENT = "backend"
UNNAMED_TEST = "a test"
UNNAMED_BACKEND = "model"


class EngineServerRefused(BaseException):
    pass


class RunningTest:
    def name(self) -> str:
        case = self._case()
        return case.id() if case else UNNAMED_TEST

    def _case(self) -> unittest.TestCase | None:
        frame = sys._getframe()
        while frame is not None:
            candidate = frame.f_locals.get("self")
            if isinstance(candidate, unittest.TestCase):
                return candidate
            frame = frame.f_back
        return None


class RefusedServer:
    def __init__(self, arguments: tuple, options: dict) -> None:
        self._arguments = arguments
        self._options = options

    def backend(self) -> str:
        named = self._options.get(BACKEND_ARGUMENT, UNNAMED_BACKEND)
        return str(self._arguments[0]) if self._arguments else str(named)

    def refusal(self) -> EngineServerRefused:
        return EngineServerRefused(
            f"{RunningTest().name()} reached the engine's {self.backend()} server: an engine stub of the test "
            "no longer applies to the code it runs. The suite attaches to no model server and starts none."
        )


class RefusingEntryPoint:
    def __call__(self, *arguments: object, **options: object) -> None:
        raise RefusedServer(arguments, options).refusal()


class RefusingLoader(importlib.abc.Loader):
    def __init__(self, loader: importlib.abc.Loader) -> None:
        self._loader = loader

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType | None:
        return self._loader.create_module(spec)

    def exec_module(self, module: types.ModuleType) -> None:
        self._loader.exec_module(module)
        setattr(module, ENTRY_POINT, RefusingEntryPoint())


class EngineServerRefusal(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path: Sequence[str] | None,
                  target: types.ModuleType | None = None) -> importlib.machinery.ModuleSpec | None:
        if fullname != SPAWN_MODULE:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is not None:
            spec.loader = RefusingLoader(spec.loader)
        return spec

    @classmethod
    def install(cls) -> None:
        if cls._installed():
            return
        cls._require_engine_not_loaded()
        sys.meta_path.insert(0, cls())

    @classmethod
    def _installed(cls) -> bool:
        return any(isinstance(finder, cls) for finder in sys.meta_path)

    @staticmethod
    def _require_engine_not_loaded() -> None:
        if SPAWN_MODULE in sys.modules:
            raise RuntimeError(f"{SPAWN_MODULE} was imported before LiveTree.activate(): its servers are not refused")
