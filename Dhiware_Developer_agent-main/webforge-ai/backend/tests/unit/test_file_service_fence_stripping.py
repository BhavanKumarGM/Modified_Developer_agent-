"""Regression tests for file_service's markdown-fence stripping on
LLM-generated file content.

Before this fix, if the model wrapped a file's "content" JSON value in a
markdown code fence (```tsx\\n...\\n```), that fence was written verbatim
into the source file, breaking the build with a confusing syntax error at
the very first/last line.
"""
from pathlib import Path

from app.services.file_service import _strip_markdown_fence, write_generated_file


CODE = "import React from 'react'\n\nexport default function App() {\n  return null\n}\n"


def test_strips_fence_with_language_tag():
    fenced = f"```tsx\n{CODE}```"
    assert _strip_markdown_fence(fenced) == CODE


def test_strips_fence_without_language_tag():
    fenced = f"```\n{CODE}```"
    assert _strip_markdown_fence(fenced) == CODE


def test_leaves_plain_content_untouched():
    assert _strip_markdown_fence(CODE) == CODE


def test_leaves_content_with_an_embedded_fence_untouched():
    """Only a fence wrapping the WHOLE content is stripped — a fence that's
    part of the actual content (e.g. a generated .md file with a code
    sample in it) must be left alone."""
    md_content = "# Usage\n\n```bash\nnpm install\n```\n\nMore text after.\n"
    assert _strip_markdown_fence(md_content) == md_content


def test_write_generated_file_strips_fence_before_writing_to_disk(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    fenced = f"```tsx\n{CODE}```"

    write_generated_file(root, "src/App.tsx", fenced)

    written = (root / "src" / "App.tsx").read_text(encoding="utf-8")
    assert written == CODE
    assert "```" not in written
