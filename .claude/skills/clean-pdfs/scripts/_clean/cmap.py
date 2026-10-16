from __future__ import annotations

import re

STREAM_ENCODING = "latin-1"
UTF16 = "utf-16-be"
SURROGATE_PASSTHROUGH = "surrogatepass"
TOKEN_RE = re.compile(r"<[0-9A-Fa-f\s]*>|\[|\]|/[^\s/<>\[\]()]*|[^\s<>\[\]/]+")
CODESPACE_RE = re.compile(r"\d+\s+begincodespacerange.*?endcodespacerange", re.DOTALL)
USECMAP_RE = re.compile(r"/[^\s/<>\[\]()]+\s+usecmap")
WHITESPACE_RE = re.compile(r"\s")
BEGIN_BFCHAR = "beginbfchar"
END_BFCHAR = "endbfchar"
BEGIN_BFRANGE = "beginbfrange"
END_BFRANGE = "endbfrange"
ARRAY_OPEN = "["
ARRAY_CLOSE = "]"
HEX_STRING_OPEN = "<"
HEX_RADIX = 16
ONE_BYTE_HEX_WIDTH = 2
TWO_BYTE_HEX_WIDTH = 4
MAX_ENTRIES_PER_BLOCK = 100
ZERO_WIDTH_SPACE = "\u200b"
ONE_BYTE_CODESPACE = "1 begincodespacerange <00> <FF> endcodespacerange"
TWO_BYTE_CODESPACE = "1 begincodespacerange <0000> <FFFF> endcodespacerange"
HEADER = (
    "/CIDInit /ProcSet findresource begin\n"
    "12 dict begin\n"
    "begincmap\n"
    "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
    "/CMapName /Adobe-Identity-UCS def\n"
    "/CMapType 2 def\n"
)
TRAILER = "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"


class CMapError(ValueError):
    pass


def hex_code(value: int, width: int) -> str:
    return format(value, f"0{width}X")


def hex_body(token: str) -> str:
    if not token.startswith(HEX_STRING_OPEN):
        raise CMapError(f"expected a hex string in the ToUnicode CMap, found {token}")
    return WHITESPACE_RE.sub("", token[1:-1]).upper()


def decode_target(hex_text: str) -> str:
    try:
        return bytes.fromhex(hex_text).decode(UTF16)
    except (ValueError, UnicodeDecodeError):
        return _decode_as_code_point(hex_text)


def _decode_as_code_point(hex_text: str) -> str:
    try:
        return chr(int(hex_text, HEX_RADIX))
    except (ValueError, OverflowError) as failure:
        raise CMapError(f"ToUnicode target <{hex_text}> is not a Unicode string") from failure


def encode_target(text: str) -> str:
    return text.encode(UTF16, SURROGATE_PASSTHROUGH).hex().upper()


class _Tokens:
    def __init__(self, text: str) -> None:
        self._tokens = TOKEN_RE.findall(text)
        self._position = 0

    def has_more(self) -> bool:
        return self._position < len(self._tokens)

    def take(self) -> str:
        self._require_more()
        token = self._tokens[self._position]
        self._position += 1
        return token

    def take_hex(self) -> str:
        return hex_body(self.take())

    def take_targets(self) -> list[str]:
        token = self.take()
        if token != ARRAY_OPEN:
            return [hex_body(token)]
        return self._hex_until(ARRAY_CLOSE)

    def _hex_until(self, end: str) -> list[str]:
        collected = []
        while (token := self.take()) != end:
            collected.append(hex_body(token))
        return collected

    def _require_more(self) -> None:
        if not self.has_more():
            raise CMapError("the ToUnicode CMap ends inside a block")


class ToUnicodeCMap:
    def __init__(self, text: str) -> None:
        self._text = text
        self._mappings: dict[str, str] = {}
        self._parse()

    @classmethod
    def from_bytes(cls, data: bytes) -> ToUnicodeCMap:
        return cls(data.decode(STREAM_ENCODING))

    @classmethod
    def from_mappings(cls, mappings: dict[str, str]) -> ToUnicodeCMap:
        return cls(_bfchar_blocks(mappings))

    def mappings(self) -> dict[str, str]:
        return dict(self._mappings)

    def codespace_lines(self) -> str:
        found = CODESPACE_RE.findall(self._text)
        return "\n".join(found) if found else self._default_codespace()

    def inherited_lines(self) -> str:
        return "".join(f"{line}\n" for line in USECMAP_RE.findall(self._text)) + self.codespace_lines()

    def patched(self, overrides: dict[str, str]) -> str:
        replacements = {code: target or ZERO_WIDTH_SPACE for code, target in overrides.items()}
        body = _bfchar_blocks({**self._mappings, **replacements})
        return HEADER + self.inherited_lines() + "\n" + body + TRAILER

    def _default_codespace(self) -> str:
        widest = max((len(code) for code in self._mappings), default=ONE_BYTE_HEX_WIDTH)
        return TWO_BYTE_CODESPACE if widest == TWO_BYTE_HEX_WIDTH else ONE_BYTE_CODESPACE

    def _parse(self) -> None:
        tokens = _Tokens(self._text)
        while tokens.has_more():
            self._parse_block(tokens, tokens.take())

    def _parse_block(self, tokens: _Tokens, keyword: str) -> None:
        if keyword == BEGIN_BFCHAR:
            self._parse_bfchar(tokens)
        elif keyword == BEGIN_BFRANGE:
            self._parse_bfrange(tokens)

    def _parse_bfchar(self, tokens: _Tokens) -> None:
        while (code := tokens.take()) != END_BFCHAR:
            self._mappings[hex_body(code)] = decode_target(tokens.take_hex())

    def _parse_bfrange(self, tokens: _Tokens) -> None:
        while (low := tokens.take()) != END_BFRANGE:
            self._add_range(hex_body(low), tokens.take_hex(), tokens.take_targets())

    def _add_range(self, low: str, high: str, targets: list[str]) -> None:
        for offset, value in enumerate(range(int(low, HEX_RADIX), int(high, HEX_RADIX) + 1)):
            self._mappings[hex_code(value, len(low))] = _range_target(targets, offset)


def _range_target(targets: list[str], offset: int) -> str:
    if len(targets) > 1:
        return _array_target(targets, offset)
    return _incremented(decode_target(targets[0]), offset)


def _array_target(targets: list[str], offset: int) -> str:
    try:
        return decode_target(targets[offset])
    except IndexError as failure:
        raise CMapError("a bfrange array names fewer targets than the range has codes") from failure


def _incremented(target: str, offset: int) -> str:
    if not target:
        return target
    return target[:-1] + chr(ord(target[-1]) + offset)


def _bfchar_blocks(mappings: dict[str, str]) -> str:
    entries = [f"<{code}> <{encode_target(target)}>" for code, target in sorted(mappings.items(), key=_code_order)]
    starts = range(0, len(entries), MAX_ENTRIES_PER_BLOCK)
    return "".join(_bfchar_block(entries[start:start + MAX_ENTRIES_PER_BLOCK]) for start in starts)


def _bfchar_block(entries: list[str]) -> str:
    return f"{len(entries)} {BEGIN_BFCHAR}\n" + "\n".join(entries) + f"\n{END_BFCHAR}\n"


def _code_order(item: tuple[str, str]) -> tuple[int, str]:
    return len(item[0]), item[0]
