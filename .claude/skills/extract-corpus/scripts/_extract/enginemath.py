from __future__ import annotations

import html
import re

from notation import latex_span

MATH_ELEMENT_RE = re.compile(r"<math(?P<attributes>[^>]*)>(?P<latex>.*?)</math>", re.DOTALL)
_DISPLAY_ATTRIBUTE_RE = re.compile(r"display\s*=\s*[\"']?block", re.IGNORECASE)


class EngineNotation:
    def replaced(self, html_text: str) -> str:
        return MATH_ELEMENT_RE.sub(self._span, html_text)

    @staticmethod
    def _span(element: re.Match) -> str:
        displayed = _DISPLAY_ATTRIBUTE_RE.search(element.group("attributes")) is not None
        latex = html.unescape(element.group("latex"))
        return html.escape(latex_span(latex, displayed), quote=False)
