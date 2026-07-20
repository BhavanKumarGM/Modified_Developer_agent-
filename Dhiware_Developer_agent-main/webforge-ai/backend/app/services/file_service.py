"""File system operations for project files."""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Optional
import mimetypes

from app.core.safe_path import resolve_safe

IGNORE_DIRS = {"node_modules", "dist", "build", ".cache", ".git", "__pycache__", ".next", "coverage"}
IGNORE_EXTENSIONS = {".lock", ".log", ".map"}
TEXT_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".json", ".md",
    ".yaml", ".yml", ".env", ".sh", ".py", ".txt", ".svg", ".xml",
    ".toml", ".ini", ".cfg",
}


def build_file_tree(root: Path) -> list[dict]:
    """Recursively build a file tree structure."""

    def _walk(path: Path, rel_base: Path) -> Optional[dict]:
        rel = path.relative_to(rel_base)
        name = path.name

        if path.is_dir():
            if name in IGNORE_DIRS or name.startswith("."):
                return None
            children = []
            for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name)):
                node = _walk(child, rel_base)
                if node:
                    children.append(node)
            return {
                "id": str(rel),
                "name": name,
                "path": str(rel).replace("\\", "/"),
                "type": "directory",
                "children": children,
                "isExpanded": rel.parts[0:1] == (),
            }
        else:
            if path.suffix in IGNORE_EXTENSIONS:
                return None
            return {
                "id": str(rel),
                "name": name,
                "path": str(rel).replace("\\", "/"),
                "type": "file",
                "language": _detect_language(path.suffix),
                "size": path.stat().st_size,
            }

    result = []
    for child in sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name)):
        node = _walk(child, root)
        if node:
            result.append(node)
    return result


def read_file(root: Path, rel_path: str) -> tuple[str, str]:
    """Read a file and return (content, language). Raises ValueError if
    rel_path escapes root, FileNotFoundError if it doesn't exist."""
    full = resolve_safe(root, rel_path)
    if not full.exists() or not full.is_file():
        raise FileNotFoundError(f"File not found: {rel_path}")

    suffix = full.suffix
    language = _detect_language(suffix)

    if suffix not in TEXT_EXTENSIONS:
        return f"[Binary file: {rel_path}]", "text"

    try:
        content = full.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        content = f"[Error reading file: {e}]"
    return content, language


def write_file(root: Path, rel_path: str, content: str) -> None:
    """Write content to a file, creating directories as needed. Raises
    ValueError if rel_path escapes root."""
    full = resolve_safe(root, rel_path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def delete_file(root: Path, rel_path: str) -> None:
    """Delete a file. Raises ValueError if rel_path escapes root,
    FileNotFoundError if it doesn't exist."""
    full = resolve_safe(root, rel_path)
    if not full.exists() or not full.is_file():
        raise FileNotFoundError(f"File not found: {rel_path}")
    full.unlink()


# Well-known source files the LLM sometimes places directly at the project
# root instead of under src/ — the single place this normalization happens.
# Used for every LLM-generated write (full-project generation, edits, and
# new files from the editing pipeline).
_SRC_FILES = {
    "App.tsx", "App.jsx", "App.ts", "index.css", "global.css",
    "globals.css", "App.css", "main.tsx", "main.jsx",
}


def normalize_generated_path(rel_path: str) -> str:
    """Normalize an LLM-generated file path: strip a leading slash, fix
    backslashes to forward slashes, and add a src/ prefix if a well-known
    source file was generated at the project root without one."""
    rel = rel_path.lstrip("/").replace("\\", "/")
    filename = rel.split("/")[-1]
    if "/" not in rel and filename in _SRC_FILES:
        rel = f"src/{filename}"
    return rel


def write_generated_file(root: Path, rel_path: str, content: str) -> str:
    """Normalize an LLM-generated path and write it. Returns the normalized
    relative path actually written. Raises ValueError if it escapes root."""
    rel = normalize_generated_path(rel_path)
    write_file(root, rel, content)
    return rel


def minimal_edit_from_rewrite(
    original: str, new: str, max_changed_ratio: float = 0.3
) -> Optional[tuple[str, str]]:
    """If `new` differs from `original` by one small, contiguous region,
    return (search, replace) describing just that region, so a caller can
    apply it as `original.replace(search, replace, 1)` and leave every other
    byte of the file untouched — instead of overwriting the whole file for a
    one-line change.

    Returns None when the change is too large or too scattered to treat as
    a single localized edit (the caller should fall back to a full rewrite),
    or when the resulting search text wouldn't uniquely identify the region.
    """
    if original == new:
        return None

    orig_lines = original.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    if not orig_lines:
        return None

    matcher = difflib.SequenceMatcher(a=orig_lines, b=new_lines, autojunk=False)
    opcodes = [op for op in matcher.get_opcodes() if op[0] != "equal"]
    if not opcodes:
        return None

    changed_orig_lines = sum(op[2] - op[1] for op in opcodes)
    if changed_orig_lines / len(orig_lines) > max_changed_ratio:
        return None

    # Collapse every changed opcode into a single contiguous span so a plain
    # string search/replace is well-defined even when difflib reports the
    # change as several small adjacent hunks.
    first, last = opcodes[0], opcodes[-1]
    search = "".join(orig_lines[first[1]:last[2]])
    replacement = "".join(new_lines[first[3]:last[4]])

    if not search or original.count(search) != 1:
        return None

    return search, replacement


def _detect_language(suffix: str) -> str:
    mapping = {
        ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript",
        ".css": "css", ".html": "html", ".json": "json",
        ".py": "python", ".md": "markdown",
        ".yaml": "yaml", ".yml": "yaml",
        ".svg": "xml", ".sh": "shell",
        ".toml": "toml",
    }
    return mapping.get(suffix, "plaintext")
