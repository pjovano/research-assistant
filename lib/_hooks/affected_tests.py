from __future__ import annotations

import ast
import fnmatch
from collections.abc import Iterator
from functools import cached_property
from pathlib import Path, PurePosixPath
from typing import Protocol

TESTS_DIR_NAME = "tests"
LIB_DIR_NAME = "lib"
SKILL_SCRIPTS_GLOB = ".claude/skills/*/scripts"
TEST_MODULE_PATTERN = "test*.py"
PACKAGE_INIT = "__init__.py"
PYTHON_SUFFIX = ".py"
MODULE_SEPARATOR = "."


class UnparsableSource(Exception):
    def __init__(self, path: Path, error: SyntaxError | ValueError) -> None:
        super().__init__(f"{path} cannot be parsed: {error}")


class TestSelection(Protocol):
    def unittest_arguments(self) -> tuple[str, ...]: ...

    def search_directories(self) -> tuple[Path, ...]: ...


class FullSuite:
    def unittest_arguments(self) -> tuple[str, ...]:
        return ("discover", "-s", TESTS_DIR_NAME)

    def search_directories(self) -> tuple[Path, ...]:
        return ()


class AffectedModules:
    def __init__(self, tests_dir: Path, module_names: tuple[str, ...]) -> None:
        self._tests_dir = tests_dir
        self._module_names = module_names

    def unittest_arguments(self) -> tuple[str, ...]:
        return self._module_names

    def search_directories(self) -> tuple[Path, ...]:
        return (self._tests_dir,)


class ModuleIndex:
    def __init__(self, tree_root: Path) -> None:
        resolved_root = tree_root.resolve()
        self._tests_dir = resolved_root / TESTS_DIR_NAME
        self._roots = [self._tests_dir, resolved_root / LIB_DIR_NAME, *sorted(resolved_root.glob(SKILL_SCRIPTS_GLOB))]
        self._files_by_name = self._indexed()
        self._files_by_file_name = self._by_file_name()

    @property
    def tests_dir(self) -> Path:
        return self._tests_dir

    def file_named(self, name: str) -> Path | None:
        return self._files_by_name.get(name)

    def files_called(self, file_name: str) -> set[Path]:
        return self._files_by_file_name.get(file_name, set())

    def names_and_files(self) -> Iterator[tuple[str, Path]]:
        yield from self._files_by_name.items()

    def holds(self, path: Path) -> bool:
        return path in self._files_by_name.values()

    def is_test_module(self, path: Path) -> bool:
        return path.parent == self._tests_dir and fnmatch.fnmatch(path.name, TEST_MODULE_PATTERN)

    def _indexed(self) -> dict[str, Path]:
        files_by_name: dict[str, Path] = {}
        for root in reversed(self._roots):
            files_by_name.update(self._modules_under(root, prefix=""))
        return files_by_name

    def _by_file_name(self) -> dict[str, set[Path]]:
        files_by_file_name: dict[str, set[Path]] = {}
        for path in self._files_by_name.values():
            files_by_file_name.setdefault(path.name, set()).add(path)
        return files_by_file_name

    def _modules_under(self, directory: Path, prefix: str) -> Iterator[tuple[str, Path]]:
        for entry in sorted(directory.iterdir()) if directory.is_dir() else ():
            yield from self._modules_of(entry, prefix)

    def _modules_of(self, entry: Path, prefix: str) -> Iterator[tuple[str, Path]]:
        if entry.is_dir() and (entry / PACKAGE_INIT).is_file():
            yield f"{prefix}{entry.name}", entry / PACKAGE_INIT
            yield from self._modules_under(entry, f"{prefix}{entry.name}{MODULE_SEPARATOR}")
        elif entry.suffix == PYTHON_SUFFIX and entry.name != PACKAGE_INIT:
            yield f"{prefix}{entry.stem}", entry


class SourceReferences:
    def __init__(self, module_name: str, path: Path) -> None:
        self._module_name = module_name
        self._path = path

    def imported_names(self) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(self._parsed):
            names.update(self._names_of(node))
        return names

    def named_file_names(self) -> set[str]:
        return {name for node in ast.walk(self._parsed) for name in self._file_names_in(node)}

    @cached_property
    def _parsed(self) -> ast.Module:
        try:
            return ast.parse(self._path.read_bytes(), filename=str(self._path))
        except (SyntaxError, ValueError) as error:
            raise UnparsableSource(self._path, error) from error

    @staticmethod
    def _file_names_in(node: ast.AST) -> Iterator[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for word in node.value.split():
                file_name = PurePosixPath(word).name
                if file_name.endswith(PYTHON_SUFFIX) and file_name != PACKAGE_INIT:
                    yield file_name

    def _names_of(self, node: ast.AST) -> Iterator[str]:
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield from self._with_parents(alias.name)
        elif isinstance(node, ast.ImportFrom):
            yield from self._names_from(node)

    def _names_from(self, node: ast.ImportFrom) -> Iterator[str]:
        base = self._absolute_base(node)
        yield from self._with_parents(base)
        for alias in node.names:
            yield f"{base}{MODULE_SEPARATOR}{alias.name}"

    def _absolute_base(self, node: ast.ImportFrom) -> str:
        if node.level == 0:
            return node.module or ""
        package_parts = self._package_parts()
        package = package_parts[:len(package_parts) - node.level + 1]
        return MODULE_SEPARATOR.join([*package, *([node.module] if node.module else [])])

    def _package_parts(self) -> list[str]:
        parts = self._module_name.split(MODULE_SEPARATOR)
        return parts if self._path.name == PACKAGE_INIT else parts[:-1]

    @staticmethod
    def _with_parents(name: str) -> Iterator[str]:
        parts = name.split(MODULE_SEPARATOR)
        for length in range(1, len(parts) + 1):
            yield MODULE_SEPARATOR.join(parts[:length])


class ImportGraph:
    def __init__(self, index: ModuleIndex) -> None:
        self._index = index
        self._importers = self._reversed_edges()

    def importers_of(self, path: Path) -> set[Path]:
        reached = {path}
        frontier = [path]
        while frontier:
            fresh = self._importers.get(frontier.pop(), set()) - reached
            reached |= fresh
            frontier.extend(fresh)
        return reached

    def _reversed_edges(self) -> dict[Path, set[Path]]:
        importers: dict[Path, set[Path]] = {}
        for name, path in self._index.names_and_files():
            for loaded in self._loaded_files(SourceReferences(name, path)):
                importers.setdefault(loaded, set()).add(path)
        return importers

    def _loaded_files(self, references: SourceReferences) -> Iterator[Path]:
        yield from self._imported_files(references)
        for file_name in references.named_file_names():
            yield from self._index.files_called(file_name)

    def _imported_files(self, references: SourceReferences) -> Iterator[Path]:
        for imported_name in references.imported_names():
            imported = self._index.file_named(imported_name)
            if imported is not None:
                yield imported


class AffectedTests:
    def __init__(self, tree_root: Path) -> None:
        self._tree_root = tree_root

    def selection(self, edited: Path) -> FullSuite | AffectedModules:
        index = ModuleIndex(self._tree_root)
        try:
            graph = ImportGraph(index)
        except UnparsableSource:
            return FullSuite()
        return self._selection_in(index, graph, edited.resolve())

    @staticmethod
    def _selection_in(index: ModuleIndex, graph: ImportGraph, edited: Path) -> FullSuite | AffectedModules:
        affected = sorted(path.stem for path in graph.importers_of(edited) if index.is_test_module(path))
        if not index.holds(edited) or not affected:
            return FullSuite()
        return AffectedModules(index.tests_dir, tuple(affected))


class EditSelection:
    def __init__(self, tree_root: Path, edited: Path) -> None:
        self._affected_tests = AffectedTests(tree_root)
        self._edited = edited

    def unittest_arguments(self) -> tuple[str, ...]:
        return self._selection.unittest_arguments()

    def search_directories(self) -> tuple[Path, ...]:
        return self._selection.search_directories()

    @cached_property
    def _selection(self) -> FullSuite | AffectedModules:
        return self._affected_tests.selection(self._edited)
