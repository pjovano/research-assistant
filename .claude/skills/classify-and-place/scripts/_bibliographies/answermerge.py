from __future__ import annotations

import json

PLAIN_LISTS = ("link", "unlink", "add")


class Distinct:
    @staticmethod
    def of(items: list) -> list:
        seen: dict[str, object] = {}
        for item in items:
            seen.setdefault(json.dumps(item, sort_keys=True, ensure_ascii=False), item)
        return list(seen.values())


class UnitedCreations:
    def __init__(self, creations: list[dict]) -> None:
        self._creations = creations

    def kept(self) -> list[dict]:
        united: dict[str, dict] = {}
        for creation in self._creations:
            first = united.setdefault(creation.get("name"), {**creation, "works": []})
            first["works"] += [work for work in creation.get("works") or [] if work not in first["works"]]
        return list(united.values())

    def questions(self) -> list[str]:
        return [f"two parts of the listing created '{name}' with different kinds, parents, or authors; the first stands"
                for name, shapes in self._shapes().items() if len(shapes) > 1]

    def _shapes(self) -> dict[str, set[tuple]]:
        shapes: dict[str, set[tuple]] = {}
        for creation in self._creations:
            shape = (creation.get("kind"), creation.get("parent"), creation.get("author"))
            shapes.setdefault(creation.get("name"), set()).add(shape)
        return shapes


class SettledMoves:
    def __init__(self, moves: list[dict]) -> None:
        self._moves = Distinct.of(moves)

    def kept(self) -> list[dict]:
        conflicting = self._conflicting()
        return [move for move in self._moves if self._placement(move) not in conflicting]

    def questions(self) -> list[str]:
        return [f"two parts of the listing moved '{work}' from '{source}' to different bibliographies, "
                f"{' and '.join(repr(target) for target in targets)}; no move was made"
                for (work, source), targets in self._conflicting().items()]

    def _conflicting(self) -> dict[tuple, list[str]]:
        targets: dict[tuple, list[str]] = {}
        for move in self._moves:
            targets.setdefault(self._placement(move), []).append(move.get("to"))
        return {placement: named for placement, named in targets.items() if len(named) > 1}

    @staticmethod
    def _placement(move: dict) -> tuple:
        return move.get("work"), move.get("from")


class SettledFolds:
    def __init__(self, folds: list[dict], named_beside: set[str]) -> None:
        self._folds = self._one_per_target(folds)
        self._named_beside = named_beside | {fold.get("into") for fold in self._folds}

    def kept(self) -> list[dict]:
        dropped = set(self._split()) | set(self._named())
        return [fold for fold in self._folds if fold.get("name") not in dropped]

    def questions(self) -> list[str]:
        split = [f"two parts of the listing folded '{name}' into different bibliographies; no fold was made"
                 for name in self._split()]
        return split + [f"one part of the listing folded '{name}' and another named it in an answer; no fold was made"
                        for name in self._named() if name not in self._split()]

    @staticmethod
    def _one_per_target(folds: list[dict]) -> list[dict]:
        first: dict[tuple, dict] = {}
        for fold in folds:
            first.setdefault((fold.get("name"), fold.get("into")), fold)
        return list(first.values())

    def _split(self) -> list[str]:
        names = [fold.get("name") for fold in self._folds]
        return sorted({name for name in names if names.count(name) > 1})

    def _named(self) -> list[str]:
        return sorted({fold.get("name") for fold in self._folds} & self._named_beside)


class MergedAnswers:
    def __init__(self, parts: list[dict]) -> None:
        self._parts = parts

    def merged(self) -> dict:
        creations = UnitedCreations(self._all("create"))
        moves = SettledMoves(self._all("move"))
        plain = {name: Distinct.of(self._all(name)) for name in PLAIN_LISTS}
        folds = SettledFolds(self._all("fold"), self._named_beside(creations.kept(), moves.kept(), plain))
        questions = self._asked() + creations.questions() + moves.questions() + folds.questions()
        return {"create": creations.kept(), "move": moves.kept(), **plain, "fold": folds.kept(),
                "questions": questions}

    def _all(self, name: str) -> list[dict]:
        return [item for part in self._parts for item in self._listed(part, name) if isinstance(item, dict)]

    def _asked(self) -> list[str]:
        return Distinct.of([str(question) for part in self._parts for question in self._listed(part, "questions")])

    @staticmethod
    def _listed(part: dict, name: str) -> list:
        held = part.get(name)
        return held if isinstance(held, list) else []

    @staticmethod
    def _named_beside(creations: list[dict], moves: list[dict], plain: dict[str, list[dict]]) -> set[str]:
        names = {creation.get("parent") for creation in creations}
        names |= {name for move in moves for name in (move.get("from"), move.get("to"))}
        names |= {name for link in plain["link"] + plain["unlink"] for name in (link.get("name"), link.get("parent"))}
        return names | {addition.get("to") for addition in plain["add"]}
