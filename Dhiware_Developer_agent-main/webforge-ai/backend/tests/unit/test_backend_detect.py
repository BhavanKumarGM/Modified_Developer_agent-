"""detect_backend must correctly identify Flask/Django/FastAPI projects
from real on-disk layouts, and return None for a plain React/Vite project
(the majority case) so PreviewAgent never mistakes a frontend for a backend."""
from __future__ import annotations

from pathlib import Path

from app.services.backend_detect import detect_backend


def test_detects_django_via_manage_py(tmp_path: Path):
    (tmp_path / "manage.py").write_text("#!/usr/bin/env python\nimport django\n", encoding="utf-8")
    info = detect_backend(tmp_path)
    assert info is not None
    assert info.framework == "django"
    assert info.entry_file == "manage.py"


def test_detects_flask_app_py(tmp_path: Path):
    (tmp_path / "app.py").write_text(
        "from flask import Flask\n\napp = Flask(__name__)\n\n"
        "@app.route('/')\ndef home():\n    return 'hi'\n\n"
        "if __name__ == '__main__':\n    app.run(debug=True)\n",
        encoding="utf-8",
    )
    info = detect_backend(tmp_path)
    assert info is not None
    assert info.framework == "flask"
    assert info.entry_file == "app.py"
    assert info.app_module == "app"
    assert info.app_var == "app"


def test_detects_flask_with_nonstandard_app_var(tmp_path: Path):
    (tmp_path / "server.py").write_text(
        "from flask import Flask\n\nmy_app = Flask(__name__)\n\n"
        "if __name__ == '__main__':\n    my_app.run()\n",
        encoding="utf-8",
    )
    info = detect_backend(tmp_path)
    assert info is not None
    assert info.framework == "flask"
    assert info.app_var == "my_app"


def test_detects_fastapi_main_py(tmp_path: Path):
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\n\napp = FastAPI()\n\n"
        "@app.get('/')\ndef root():\n    return {}\n",
        encoding="utf-8",
    )
    info = detect_backend(tmp_path)
    assert info is not None
    assert info.framework == "fastapi"
    assert info.entry_file == "main.py"
    assert info.app_module == "main"
    assert info.app_var == "app"


def test_detects_fastapi_nested_module(tmp_path: Path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "backend" / "api.py").write_text(
        "from fastapi import FastAPI\n\nservice = FastAPI()\n",
        encoding="utf-8",
    )
    info = detect_backend(tmp_path)
    assert info is not None
    assert info.framework == "fastapi"
    assert info.entry_file == "backend/api.py"
    assert info.app_module == "backend.api"
    assert info.app_var == "service"


def test_returns_none_for_react_project(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.tsx").write_text("export default function App() { return null }", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert detect_backend(tmp_path) is None


def test_returns_none_for_empty_project(tmp_path: Path):
    assert detect_backend(tmp_path) is None


def test_ignores_venv_directory(tmp_path: Path):
    venv_site = tmp_path / ".venv" / "Lib" / "site-packages" / "flask_thing"
    venv_site.mkdir(parents=True)
    (venv_site / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")
    assert detect_backend(tmp_path) is None
