"""ZIP extraction and project analysis service."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

IGNORE_DIRS = {"node_modules", "dist", "build", ".cache", ".git", "__pycache__", ".next"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB per file


def extract_zip(zip_path: Path, target_dir: Path) -> Path:
    """Extract a ZIP archive, skipping ignored directories. Returns root of extracted project."""
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.infolist()

        # Detect common prefix (if everything is inside one top-level folder)
        prefixes = set()
        for m in members:
            parts = Path(m.filename).parts
            if parts:
                prefixes.add(parts[0])

        single_root = len(prefixes) == 1 and not next(iter(prefixes)).endswith("/")

        for member in members:
            parts = Path(member.filename).parts
            # Skip ignored directories
            if any(p in IGNORE_DIRS for p in parts):
                continue
            if member.file_size > MAX_FILE_SIZE:
                continue
            if member.filename.endswith("/"):
                continue

            # Strip the common root prefix
            rel_parts = parts[1:] if single_root and len(parts) > 1 else parts
            if not rel_parts:
                continue

            target_path = target_dir.joinpath(*rel_parts)
            target_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                with zf.open(member) as src, open(target_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            except Exception:
                pass

    return target_dir
