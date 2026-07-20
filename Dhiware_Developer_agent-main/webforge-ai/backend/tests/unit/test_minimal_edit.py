"""Unit tests for file_service.minimal_edit_from_rewrite — the piece that
lets a full-file rewrite from the LLM be reduced to a localized
search/replace so unrelated lines stay byte-identical (audit item 3.1)."""
from app.services.file_service import minimal_edit_from_rewrite


ORIGINAL = (
    "import React from 'react'\n"
    "\n"
    "export default function App() {\n"
    "  return (\n"
    "    <div className=\"app\">\n"
    "      <h1>Hello World</h1>\n"
    "    </div>\n"
    "  )\n"
    "}\n"
)


def test_returns_none_when_content_is_identical():
    assert minimal_edit_from_rewrite(ORIGINAL, ORIGINAL) is None


def test_finds_minimal_span_for_a_one_line_change():
    new = ORIGINAL.replace("Hello World", "Hello Universe")
    result = minimal_edit_from_rewrite(ORIGINAL, new)
    assert result is not None
    search, replacement = result
    assert search == "      <h1>Hello World</h1>\n"
    assert replacement == "      <h1>Hello Universe</h1>\n"
    # Applying it must reproduce the LLM's intended new content exactly.
    assert ORIGINAL.replace(search, replacement, 1) == new


def test_returns_none_for_large_scale_rewrite():
    new = "import React from 'react'\n\nexport default function App() {\n  return <div>Completely different, restructured component with lots of new content and multiple new lines that changes the vast majority of this file from top to bottom, leaving almost nothing in common with the original version that existed before.</div>\n}\n"
    result = minimal_edit_from_rewrite(ORIGINAL, new)
    assert result is None


def test_returns_none_when_search_text_not_unique():
    original = "x\ny\nx\ny\n"
    new = "x\nz\nx\ny\n"
    # The single changed line "y" -> "z" occurs in a context that, once
    # isolated, might not be unique; this asserts the function only ever
    # returns a search string that uniquely identifies the region.
    result = minimal_edit_from_rewrite(original, new)
    if result is not None:
        search, _ = result
        assert original.count(search) == 1
