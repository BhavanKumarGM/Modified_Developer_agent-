"""Generates a Python backend (Flask) from a structured plan.

Scope note: detection and execution (PreviewAgent/backend_detect.py) support
Flask, Django, and FastAPI, since WebForge must be able to *run* whatever a
user imports. Generation targets Flask only — it's the simplest, most
universal choice for the CRUD-style APIs this agent is asked for, and having
one well-tested template beats three half-tested ones.
"""
from __future__ import annotations

import re
from typing import Any, AsyncIterator

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult

# Matches a module-level (unindented) `db.create_all()` call — the exact
# pattern that crashes at import time with "Working outside of application
# context." An indented call (already inside `with app.app_context():` or a
# function) is left untouched since it won't match at column 0.
_BARE_CREATE_ALL_RE = re.compile(r"^db\.create_all\(\)[ \t]*$", re.MULTILINE)

SYSTEM_PROMPT = """You are the Backend Generation Agent for WebForge AI.

Your job: generate a complete, runnable Python Flask backend.

Output ONLY valid JSON — no markdown, no explanation, nothing outside the JSON:
{
  "files": [
    {"path": "app.py", "content": "..."},
    {"path": "requirements.txt", "content": "..."}
  ],
  "framework": "flask",
  "description": "Brief description of what was generated"
}

RULES:
1. app.py MUST define a module-level Flask app object named `app` (e.g. `app = Flask(__name__)`). This is how the app is discovered and run — do not wrap it in a factory function or hide it inside `if __name__ == '__main__':`.
2. Always include a `requirements.txt` listing every third-party import used (flask, flask-cors, flask-sqlalchemy, etc.), one per line, unpinned or with a minimum version (e.g. `flask>=3.0`).
3. Always add CORS support (`from flask_cors import CORS` + `CORS(app)`) so a separately-served frontend (e.g. a Vite dev server on another port) can call this API during local development. Add `flask-cors` to requirements.txt whenever you do.
4. Generate COMPLETE, WORKING code. No TODOs, no placeholders, no "# implement this".
5. Prefer simple, explicit routes (`@app.route(...)`) with clear JSON request/response bodies. Use in-memory data structures unless the user's request implies persistence, in which case use flask-sqlalchemy with SQLite (a file-based db needs no separate server). If you use flask-sqlalchemy, NEVER call `db.create_all()` at module level — it raises "Working outside of application context" at import time. Wrap it: `with app.app_context():\n    db.create_all()`.
6. Include basic input validation and appropriate HTTP status codes (400/404/etc.) — don't let bad input crash the process.
7. You may split routes/models into extra files (e.g. `models.py`, `routes.py`) imported from app.py if the API is large, but a single `app.py` is preferred for anything simple.
8. Never write frontend files (no .tsx/.jsx/.html templates) unless the user explicitly asks for server-rendered HTML — this agent's output is an API.
9. Output ONLY the JSON object. Start with { and end with }.
"""


class BackendGenerationAgent(BaseAgent):
    name = "backend"
    description = "Generates a Python Flask backend from a structured plan"

    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        self._log_task(task)
        memory_section = self._format_memory(context.metadata)

        prompt = f"""Generate the Flask backend for:

"{task}"

Requirements:
- A complete, runnable Flask API (or server-rendered app if explicitly requested)
- CORS enabled for local development
- requirements.txt listing every dependency actually imported
- Every file must be complete and self-contained
{memory_section}
Output ONLY the JSON object. Start with {{ and end with }}."""

        request = self._build_request(
            system=SYSTEM_PROMPT,
            user=prompt,
            temperature=0.2,
        )
        response = await self.llm.generate(request)

        try:
            data = self._extract_json(response.content)
            files = data.get("files", [])
            files = self._fix_unwrapped_create_all(files)
            data["files"] = self._ensure_critical_files(files)

            paths = [f["path"] for f in data["files"]]
            return AgentResult(
                success=True,
                content=f"Generated {len(data['files'])} backend files",
                data=data,
                files_modified=paths,
            )
        except Exception as e:
            self.logger.error(f"JSON parse error: {e}\nRaw: {response.content[:500]}")
            return AgentResult(success=False, error=str(e), content=response.content)

    async def stream(self, task: str, context: AgentContext, **kwargs: Any) -> AsyncIterator[str]:
        summary_prompt = f"""The user wants a Python backend for: "{task}"

Write 2-3 sentences describing what Flask routes/models you will generate.
Be specific. Then write "⚡ Generating backend now…" on a new line."""

        request = self._build_request(
            system="You are a helpful AI coding assistant. Be concise and specific.",
            user=summary_prompt,
            temperature=0.5,
        )
        async for token in self.llm.stream(request):
            yield token

    def _fix_unwrapped_create_all(self, files: list[dict]) -> list[dict]:
        """Deterministic safety net for a real bug seen live: models still
        sometimes emit a module-level `db.create_all()` despite the system
        prompt rule against it, which crashes the app at import time with
        "Working outside of application context." Rather than trust the
        prompt alone, rewrite the pattern if it slips through."""
        for f in files:
            content = f.get("content", "")
            if content and _BARE_CREATE_ALL_RE.search(content):
                f["content"] = _BARE_CREATE_ALL_RE.sub(
                    "with app.app_context():\n    db.create_all()", content
                )
        return files

    def _ensure_critical_files(self, files: list[dict]) -> list[dict]:
        """Ensure app.py and requirements.txt exist even if the model
        forgot one of them, so PreviewAgent always has something to run."""
        has_app = any(f.get("path") in {"app.py"} for f in files)
        if not has_app:
            files.insert(0, {"path": "app.py", "content": (
                "from flask import Flask, jsonify\n"
                "from flask_cors import CORS\n\n"
                "app = Flask(__name__)\n"
                "CORS(app)\n\n"
                "@app.route('/')\n"
                "def index():\n"
                "    return jsonify({'status': 'ok'})\n\n"
                "if __name__ == '__main__':\n"
                "    app.run(debug=True)\n"
            )})

        has_requirements = any(f.get("path") == "requirements.txt" for f in files)
        if not has_requirements:
            files.append({"path": "requirements.txt", "content": "flask>=3.0\nflask-cors>=4.0\n"})

        return files
