from __future__ import annotations


class PageRanges:
    def parse(self, raw: str | None) -> list[int]:
        pages: set[int] = set()
        for part in (raw or "").split(","):
            if part.strip():
                pages.update(self._range(part))
        return sorted(pages)

    def _range(self, part: str) -> range:
        first, _, last = part.partition("-")
        return range(int(first), int(last or first) + 1)

    def compact(self, pages: list[int]) -> str:
        runs: list[list[int]] = []
        for page in sorted(set(pages)):
            if runs and page == runs[-1][-1] + 1:
                runs[-1].append(page)
            else:
                runs.append([page])
        return ",".join(self._span(run) for run in runs)

    @staticmethod
    def _span(run: list[int]) -> str:
        return str(run[0]) if len(run) == 1 else f"{run[0]}-{run[-1]}"
