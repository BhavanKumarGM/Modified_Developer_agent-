"""Unit tests for app.core.safe_path.resolve_safe — the single source of
truth for filesystem path containment."""
from pathlib import Path

import pytest

from app.core.safe_path import resolve_safe


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    r = tmp_path / "project_root"
    r.mkdir()
    return r


def test_resolves_normal_relative_path(root: Path):
    resolved = resolve_safe(root, "src/App.tsx")
    assert resolved == (root / "src" / "App.tsx").resolve()


def test_rejects_dotdot_traversal(root: Path):
    with pytest.raises(ValueError):
        resolve_safe(root, "../../evil.txt")


def test_rejects_dotdot_traversal_embedded(root: Path):
    with pytest.raises(ValueError):
        resolve_safe(root, "src/../../evil.txt")


def test_rejects_absolute_posix_path(root: Path):
    with pytest.raises(ValueError):
        resolve_safe(root, "/etc/passwd")


def test_rejects_windows_drive_absolute_path(root: Path):
    with pytest.raises(ValueError):
        resolve_safe(root, "C:\\Windows\\System32\\config")


def test_rejects_windows_rooted_driveless_path(root: Path):
    with pytest.raises(ValueError):
        resolve_safe(root, "\\Windows\\System32")


def test_rejects_null_byte(root: Path):
    with pytest.raises(ValueError):
        resolve_safe(root, "src/App.tsx\x00.png")


def test_rejects_symlink_escape(root: Path, tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")

    link = root / "escape_link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported/permitted on this platform")

    with pytest.raises(ValueError):
        resolve_safe(root, "escape_link/secret.txt")


def test_allows_path_that_does_not_exist_yet(root: Path):
    resolved = resolve_safe(root, "new/nested/file.txt")
    assert not resolved.exists()
    assert resolved.parent.parent.parent == root.resolve()
