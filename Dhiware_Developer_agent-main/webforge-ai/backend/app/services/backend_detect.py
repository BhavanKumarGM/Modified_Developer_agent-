"""Detects an existing Python web backend (Flask/Django/FastAPI) in a
project directory so PreviewAgent can run it without guessing, and so
BackendGenerationAgent knows whether one already exists.

This never executes or imports the target project's code — detection is
pure static inspection (file names + regex over source text) so it is
safe to run against an arbitrary imported repository.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", "site-packages",
}
_MAX_DEPTH = 3  # relative to project root; keeps the scan bounded and shallow

_FASTAPI_APP_RE = re.compile(r"(\w+)\s*=\s*FastAPI\s*\(")
_FLASK_APP_RE = re.compile(r"(\w+)\s*=\s*Flask\s*\(")
_FLASK_RUN_RE = re.compile(r"\.run\s*\(")


@dataclass(frozen=True)
class BackendInfo:
    framework: str  # "flask" | "django" | "fastapi"
    entry_file: str  # project-relative path, forward slashes, e.g. "app.py"
    app_module: str  # dotted import path for entry_file, e.g. "app" or "backend.main"
    app_var: str = "app"  # module-level app/ASGI-callable variable name


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        rel_parts = path.relative_to(root).parts
        if any(part in _IGNORE_DIRS for part in rel_parts):
            continue
        if len(rel_parts) > _MAX_DEPTH:
            continue
        yield path


def _to_module(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    return ".".join(rel.parts)


def detect_backend(root: Path) -> Optional[BackendInfo]:
    """Best-effort detection of a Python web backend under `root`.
    Returns None if nothing recognizable is found. Django (manage.py) is
    checked first since it's unambiguous; Flask/FastAPI are detected by
    scanning shallow .py files for a module-level app object."""
    manage_py = root / "manage.py"
    if manage_py.exists() and manage_py.is_file():
        return BackendInfo(framework="django", entry_file="manage.py", app_module="manage")

    fastapi_candidates: list[tuple[Path, str, str]] = []
    flask_candidates: list[tuple[Path, str, str, bool]] = []

    for path in _iter_python_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        fastapi_match = _FASTAPI_APP_RE.search(text)
        if fastapi_match:
            fastapi_candidates.append((path, _to_module(root, path), fastapi_match.group(1)))
            continue

        flask_match = _FLASK_APP_RE.search(text)
        if flask_match:
            has_run_call = bool(_FLASK_RUN_RE.search(text))
            flask_candidates.append((path, _to_module(root, path), flask_match.group(1), has_run_call))

    if fastapi_candidates:
        # Prefer a file literally named main.py/app.py if present (common convention).
        fastapi_candidates.sort(key=lambda c: (c[0].name not in ("main.py", "app.py"), len(c[0].parts)))
        path, module, app_var = fastapi_candidates[0]
        return BackendInfo(
            framework="fastapi",
            entry_file=str(path.relative_to(root)).replace("\\", "/"),
            app_module=module,
            app_var=app_var,
        )

    if flask_candidates:
        # Prefer the file that actually runs the dev server (app.run(...))
        # and/or is named app.py/main.py — that's almost always the entrypoint.
        flask_candidates.sort(
            key=lambda c: (not c[3], c[0].name not in ("app.py", "main.py"), len(c[0].parts))
        )
        path, module, app_var, _ = flask_candidates[0]
        return BackendInfo(
            framework="flask",
            entry_file=str(path.relative_to(root)).replace("\\", "/"),
            app_module=module,
            app_var=app_var,
        )

    return None


def has_requirements_file(root: Path) -> bool:
    return (root / "requirements.txt").exists()


FRAMEWORK_PACKAGES: dict[str, list[str]] = {
    "flask": ["flask"],
    "django": ["django"],
    "fastapi": ["fastapi", "uvicorn"],
}
