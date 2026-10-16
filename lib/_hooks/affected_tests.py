from __future__ import annotations

import ast
import fnmatch
from collections.abc import Iterator
from pathlib import Path

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


class FullSuite:
    def runs_nothing(self) -> bool:
        return False

    def unittest_arguments(self) -> tuple[str, ...]:
        return ("discover", "-s", TESTS_DIR_NAME)

    def search_directories(self) -> tuple[Path, ...]:
        return ()


class AffectedModules:
    def __init__(self, tests_dir: Path, module_names: tuple[str, ...]) -> None:
        self._tests_dir = tests_dir
        self._module_names = module_names

    def runs_nothing(self) -> bool:
        return not self._module_names

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

    @property
    def tests_dir(self) -> Path:
        return self._tests_dir

    def file_named(self, name: str) -> Path | None:
        return self._files_by_name.get(name)

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

    def _modules_under(self, directory: Path, prefix: str) -> Iterator[tuple[str, Path]]:
        for entry in sorted(directory.iterdir()) if directory.is_dir() else ():
            yield from self._modules_of(entry, prefix)

    def _modules_of(self, entry: Path, prefix: str) -> Iterator[tuple[str, Path]]:
        if entry.is_dir() and (entry / PACKAGE_INIT).is_file():
            yield f"{prefix}{entry.name}", entry / PACKAGE_INIT
            yield from self._modules_under(entry, f"{prefix}{entry.name}{MODULE_SEPARATOR}")
        elif entry.suffix == PYTHON_SUFFIX and entry.name != PACKAGE_INIT:
            yield f"{prefix}{entry.stem}", entry


class ImportedNames:
    def __init__(self, module_name: str, path: Path) -> None:
        self._module_name = module_name
        self._path = path

    def names(self) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(self._parsed()):
            names.update(self._names_of(node))
        return names

    def _parsed(self) -> ast.Module:
        try:
            return ast.parse(self._path.read_bytes(), filename=str(self._path))
        except (SyntaxError, ValueError) as error:
            raise UnparsableSource(self._path, error) from error

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
            for imported in self._imported_files(name, path):
                importers.setdefault(imported, set()).add(path)
        return importers

    def _imported_files(self, name: str, path: Path) -> Iterator[Path]:
        for imported_name in ImportedNames(name, path).names():
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
        if not index.holds(edited):
            return FullSuite()
        affected = sorted(path.stem for path in graph.importers_of(edited) if index.is_test_module(path))
        return AffectedModules(index.tests_dir, tuple(affected))
