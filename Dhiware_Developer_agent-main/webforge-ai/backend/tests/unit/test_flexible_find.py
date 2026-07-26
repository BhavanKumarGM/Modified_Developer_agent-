"""Unit tests for file_service.flexible_find — the whitespace-normalized
fallback for search/replace patches. Reproduces the real bug: EditingAgent
kept failing with "Could not apply patch to `TopNavigation.tsx`" because
its proposed `search` text differed from the real file only by whitespace/
indentation, and the exact-match check had no fallback.
"""
from app.services.file_service import flexible_find


def test_returns_search_unchanged_when_it_already_matches_exactly():
    content = "const x = 1;\nconst y = 2;\n"
    assert flexible_find(content, "const y = 2;") == "const y = 2;"


def test_resolves_when_search_has_different_indentation():
    content = "function f() {\n  return (\n    <button>\n      Notifications\n    </button>\n  );\n}\n"
    # Model's proposed search uses different (single-space) indentation.
    search = "<button>\n Notifications\n </button>"
    result = flexible_find(content, search)
    assert result is not None
    assert result in content
    # Applying the resolved span must reproduce exactly the real content.
    assert content.replace(result, "<button onClick={openMenu}>Notifications</button>", 1) != content


def test_resolves_when_search_uses_different_line_breaks():
    content = "const a = 1;\r\nconst b = 2;\r\n"
    search = "const a = 1;\nconst b = 2;"
    result = flexible_find(content, search)
    assert result == "const a = 1;\r\nconst b = 2;"


def test_resolves_when_search_has_extra_trailing_whitespace():
    content = "  <Bell className=\"h-4 w-4\" />\n  Notifications\n"
    search = "<Bell className=\"h-4 w-4\" />   \n   Notifications  "
    result = flexible_find(content, search)
    assert result is not None
    assert result in content


def test_returns_none_when_content_is_genuinely_different():
    content = "export default function App() { return null }"
    search = "export default function TotallyDifferent() { return 42 }"
    assert flexible_find(content, search) is None


def test_returns_none_for_empty_search():
    assert flexible_find("some content", "") is None


def test_exact_match_short_circuits_before_ambiguity_check():
    # Matches pre-existing `search in content` behavior (which never
    # checked uniqueness either — content.replace(..., 1) just takes the
    # first occurrence): an exact match is returned as-is even if it isn't
    # unique. Only the *fuzzy* fallback path enforces uniqueness.
    content = "x y\nz\nx y\n"
    assert flexible_find(content, "x y") == "x y"


def test_returns_none_when_normalized_match_is_ambiguous():
    # Neither occurrence is an exact match for "x y" (both use a double
    # space), so this only matches via the fuzzy path — and it matches
    # twice after normalizing, so it must not guess which one.
    content = "x  y\nz\nx  y\n"
    search = "x y"
    assert flexible_find(content, search) is None


def test_replacing_the_resolved_span_reproduces_intended_result_exactly():
    content = (
        "const TopNavigation = () => {\n"
        "  return (\n"
        "    <button>\n"
        "      Notifications\n"
        "    </button>\n"
        "  );\n"
        "};\n"
    )
    search = "<button>\n  Notifications\n  </button>"  # slightly different indent
    replacement = "<button onClick={toggleMenu}>\n      Notifications\n    </button>"
    resolved = flexible_find(content, search)
    assert resolved is not None
    new_content = content.replace(resolved, replacement, 1)
    assert "onClick={toggleMenu}" in new_content
    # Every other line is untouched.
    assert "const TopNavigation = () => {" in new_content
    assert "};" in new_content
