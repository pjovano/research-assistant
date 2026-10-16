from __future__ import annotations

BASE64_KEY = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
BITS_PER_CHARACTER = 6
END_OF_STREAM = 2
NARROW_CHARACTER, WIDE_CHARACTER = 0, 1
NARROW_BITS, WIDE_BITS = 8, 16
FIRST_FREE_CODE = 3


class _BitReader:
    def __init__(self, values: list[int]) -> None:
        self._values = values
        self._index = 1
        self._value = values[0]
        self._mask = 1 << (BITS_PER_CHARACTER - 1)

    def bits(self, count: int) -> int:
        result = 0
        for power in range(count):
            if self._value & self._mask:
                result |= 1 << power
            self._advance()
        return result

    def _advance(self) -> None:
        self._mask >>= 1
        if self._mask == 0:
            self._mask = 1 << (BITS_PER_CHARACTER - 1)
            self._value = self._values[self._index] if self._index < len(self._values) else 0
            self._index += 1


class _Dictionary:
    def __init__(self, reader: _BitReader) -> None:
        self._reader = reader
        self._entries: dict[int, str] = {}
        self._size = FIRST_FREE_CODE
        self._width = 2
        self._until_wider = 1

    def literal(self, code: int) -> str:
        return chr(self._reader.bits(NARROW_BITS if code == NARROW_CHARACTER else WIDE_BITS))

    def next_code(self) -> int:
        return self._reader.bits(self._width)

    def add(self, entry: str) -> int:
        code = self._size
        self._entries[code] = entry
        self._size += 1
        self._until_wider -= 1
        if self._until_wider == 0:
            self._until_wider = 1 << self._width
            self._width += 1
        return code

    def entry(self, code: int, previous: str) -> str:
        return self._entries[code] if code in self._entries else previous + previous[0]


def decompress_from_base64(data: str) -> str:
    if not data:
        return ""
    dictionary = _Dictionary(_BitReader([BASE64_KEY.index(character) for character in data]))
    first = dictionary.next_code()
    if first == END_OF_STREAM:
        return ""
    previous = dictionary.literal(first)
    dictionary.add(previous)
    return "".join(_entries(dictionary, previous))


def _entries(dictionary: _Dictionary, first: str):
    previous = first
    yield first
    while True:
        code = dictionary.next_code()
        if code == END_OF_STREAM:
            return
        if code in (NARROW_CHARACTER, WIDE_CHARACTER):
            code = dictionary.add(dictionary.literal(code))
        entry = dictionary.entry(code, previous)
        yield entry
        dictionary.add(previous + entry[0])
        previous = entry
