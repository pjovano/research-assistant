from __future__ import annotations

CLAIM_MARK = "- "
EXPLICATION_MARK = "\t- "
MAX_CLAIMS = 3
MAX_STATEMENT_LINES = 3
REVIEW_MARK = " #review"
ACCEPTED_MARK = " #accepted"


def marked_for_review(line: str) -> str:
    return line if line.rstrip().endswith(REVIEW_MARK.strip()) else f"{line.rstrip()}{REVIEW_MARK}"


class ClaimsBlock:
    def __init__(self, text: str) -> None:
        self._lines = text.splitlines()

    @property
    def text(self) -> str:
        return "\n".join(self._lines)

    def claims(self) -> list[str]:
        return [self._lines[position][len(CLAIM_MARK):].strip() for position in self._positions()]

    def explications(self) -> list[list[str]]:
        positions = self._positions()
        ends = [*positions[1:], len(self._lines)]
        return [[line[len(EXPLICATION_MARK):].strip() for line in self._lines[start + 1:end]
                 if line.startswith(EXPLICATION_MARK)] for start, end in zip(positions, ends)]

    def with_claim(self, number: int, wording: str) -> "ClaimsBlock":
        claims = self.claims()
        if claims == [""] and number == 1:
            return self._replaced(self._positions()[0], f"{CLAIM_MARK}{wording}")
        if number == len(claims) + 1 and number <= MAX_CLAIMS:
            return ClaimsBlock("\n".join([*self._lines, f"{CLAIM_MARK}{wording}"]))
        return self._reworded(number, wording)

    def _reworded(self, number: int, wording: str) -> "ClaimsBlock":
        position = self._position_of(number)
        if self._lines[position].rstrip().endswith(ACCEPTED_MARK.strip()):
            raise ValueError(f"claim {number} carries the accepted mark: an accepted line is never reworded")
        return self._replaced(position, f"{CLAIM_MARK}{wording}")

    def with_explication(self, number: int, explication: str) -> "ClaimsBlock":
        end = self._end_of(number)
        return ClaimsBlock("\n".join([*self._lines[:end], f"{EXPLICATION_MARK}{explication}", *self._lines[end:]]))

    def _replaced(self, position: int, line: str) -> "ClaimsBlock":
        return ClaimsBlock("\n".join([*self._lines[:position], line, *self._lines[position + 1:]]))

    def _positions(self) -> list[int]:
        return [position for position, line in enumerate(self._lines)
                if line.startswith(CLAIM_MARK) or line == CLAIM_MARK.rstrip()]

    def _position_of(self, number: int) -> int:
        positions = self._positions()
        if not 1 <= number <= len(positions):
            raise ValueError(f"the note holds {len(positions)} claims, and at most {MAX_CLAIMS}: no claim {number}")
        return positions[number - 1]

    def _end_of(self, number: int) -> int:
        start = self._position_of(number)
        later = [position for position in self._positions() if position > start]
        end = later[0] if later else len(self._lines)
        while end > start + 1 and not self._lines[end - 1].strip():
            end -= 1
        return end
