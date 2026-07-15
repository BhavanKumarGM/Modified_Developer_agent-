"""File system operations for project files."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import mimetypes

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
    """Read a file and return (content, language)."""
    full = root / rel_path
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
    """Write content to a file, creating directories as needed."""
    full = root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


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
