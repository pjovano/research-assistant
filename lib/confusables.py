from __future__ import annotations

import unicodedata

CONFUSABLES = {
    "◦": "∘", "ϕ": "φ", "ϵ": "ε", "ϑ": "θ", "ϱ": "ρ", "ς": "σ", "−": "-", "–": "-", "—": "-", "′": "'", "’": "'",
    "‘": "'", "“": '"', "”": '"', "⋅": "·", "•": "·", "∙": "·", "∗": "*", "ν": "v", "υ": "v", "∆": "Δ", "⋄": "◊",
    "▪": "■",
}


def canonical(char: str) -> str:
    return CONFUSABLES.get(char, char)


def compatible(text: str) -> str:
    return "".join(canonical(char) for char in unicodedata.normalize("NFKC", text)).casefold()
