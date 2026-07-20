"""Shared path-containment utility.

This is the single source of truth for keeping filesystem operations inside a
project root. Every router/service that touches a user-supplied relative path
(files read/write/delete, ZIP extraction, etc.) must route through
``resolve_safe`` instead of re-implementing containment checks.
"""
from __future__ import annotations

from pathlib import Path


def resolve_safe(root: Path, rel_path: str) -> Path:
    """Resolve ``rel_path`` against ``root`` and return the absolute path.

    Raises ``ValueError`` if the resolved path would escape ``root`` — via
    ``..`` traversal, an absolute/rooted path, a null byte, or a symlink that
    points outside of ``root``. The target does not need to exist yet (safe
    to use for paths about to be created).
    """
    if rel_path is None:
        raise ValueError("Path must not be None")
    if "\x00" in rel_path:
        raise ValueError("Path contains a null byte")

    candidate = Path(rel_path)

    # `Path.is_absolute()` misses Windows drive-relative paths like "\\Windows"
    # (rooted but driveless). Checking `.root`/`.drive` catches those too, on
    # every platform, without needing an OS-specific branch.
    if candidate.is_absolute() or candidate.root or candidate.drive:
        raise ValueError(f"Absolute or rooted paths are not allowed: {rel_path!r}")

    root_resolved = root.resolve()
    # `resolve()` normalizes ".." segments and follows symlinks for any path
    # component that already exists, which is what catches a symlink planted
    # inside root that points outside of it.
    resolved = (root_resolved / candidate).resolve()

    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise ValueError(f"Path escapes project root: {rel_path!r}") from None

    return resolved
