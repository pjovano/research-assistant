from __future__ import annotations

RENDER_DPI = 70
VERIFY_SAMPLE_PAGES = 200
MIN_SOURCE_TEXT_CHARS = 500
GUTTED_PAGE_MIN_CHARS = 50
GUTTED_PAGE_RATIO = 0.1
TOTAL_TEXT_RATIO = 0.8
SCAN_DPI = 70
MAX_SCAN_PAGES = 40
MAX_TITLE_CHARS = 200
BOOK_ITEM_TYPE = "book"
ARTICLE_ITEM_TYPE = "journalArticle"
PER_PAGE_ENTRY_RATIO = 0.9
FRONT_MATTER_WORDS = frozenset({
    "cover", "front cover", "half title", "half-title", "title", "title page",
    "copyright", "copyright page", "contents", "table of contents", "toc",
    "front matter", "frontmatter", "dedication", "colophon",
})
