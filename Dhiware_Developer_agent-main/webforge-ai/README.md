# WebForge AI

A **local-first AI-assisted React + Vite + TypeScript frontend generator**.
Describe what you want to build, and WebForge AI generates a complete React
project — with live preview, file editor, and iterative AI editing. No cloud
AI, no API keys, no cost.

![WebForge AI](https://img.shields.io/badge/AI-Local%20Only-green) ![Ollama](https://img.shields.io/badge/Ollama-qwen2.5--coder%3A7b-blue) ![React](https://img.shields.io/badge/Frontend-React%2018-61DAFB) ![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)

---

## Scope — what this actually does (and doesn't)

WebForge AI generates and edits **React 18 + Vite + TypeScript + Tailwind**
frontend code. That's it, deliberately:

- ✅ Generates full React/Vite/TS frontend projects from a prompt
- ✅ Edits, refactors, and debugs React/TS/JS/CSS files in an existing project
- ✅ Analyzes an *uploaded* project of any framework well enough to describe
  its structure (`RepositoryAgent` can detect Next.js/Vue/Angular, list its
  routing/state-management choices, etc.) — but generation/editing beyond
  that analysis only works on React/Vite/TS code
- ❌ Does **not** generate backend APIs, databases, or authentication
- ❌ Does **not** generate or scaffold Next.js, Vue, or Angular projects
- ❌ Does **not** produce Docker/deployment configuration

If you need any of the ❌ items, that's real, separate future work — not
something silently half-implemented behind this README.

---

## Features

- **Prompt → Website** — describe your app in plain English, get a full React/Vite/TS project
- **ZIP Upload** — upload existing code, AI analyses the structure, continue developing
- **GitHub Import** — paste a public repo URL and it's cloned in (with full commit
  history) instead of uploading a zip
- **Live Preview** — embedded Vite dev server with real-time iframe preview
- **AI Code Editor** — Monaco editor (VS Code engine) with file explorer
- **Iterative Editing** — ask the AI to modify any part of your code
- **Git Snapshots** — automatic checkpoints after every generation
- **100% Local** — all AI inference via Ollama, nothing leaves your machine

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| AI Engine | Ollama + `qwen2.5-coder:7b` |
| Backend | FastAPI + Python 3.11 |
| Database | SQLite (async via aiosqlite) |
| Frontend | React 18 + TypeScript + Vite |
| Styling | Tailwind CSS |
| State | Zustand |
| Code Editor | Monaco Editor |
| Preview | Vite dev server (child process) |
| Real-time | WebSocket |

---

## Prerequisites

- [Python 3.11+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/)
- [Ollama](https://ollama.ai/)

---

## Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/webforge-ai.git
cd webforge-ai
```

### 2. Install Ollama and pull the models

```bash
# Install Ollama from https://ollama.ai
ollama pull qwen2.5-coder:7b
# Optional but recommended: powers semantic (not just keyword) file search.
# Without it, SearchAgent silently falls back to keyword/glob search only.
ollama pull nomic-embed-text
```

### 3. Set up the backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Set up the frontend

```bash
cd frontend
npm install
```

---

## Running the App

You need **3 terminals**:

**Terminal 1 — Ollama**
```bash
ollama serve
```

**Terminal 2 — Backend**
```bash
cd backend
python -m app.main
```
This binds to `127.0.0.1:8000` by default. The backend has **no authentication** —
only set `HOST=0.0.0.0` in `backend/.env` if you understand that exposes full
read/write/delete file access to anyone on your network.

**Terminal 3 — Frontend**
```bash
cd frontend
npm run dev
```

Then open **http://localhost:5173** in your browser.

---

## Project Structure

```
webforge-ai/
├── backend/
│   ├── app/
│   │   ├── agents/          # 11 specialized AI agents
│   │   ├── core/            # LLMService + config
│   │   ├── database/        # SQLAlchemy models
│   │   ├── orchestrator/    # Central routing logic
│   │   ├── routers/         # FastAPI route handlers
│   │   └── services/        # Business logic
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/      # React UI components
│   │   ├── hooks/           # Custom hooks (WebSocket)
│   │   ├── services/        # API + WebSocket clients
│   │   ├── stores/          # Zustand state stores
│   │   └── types/           # TypeScript types
│   ├── package.json
│   └── vite.config.ts
│
└── README.md
```

---

## Architecture Overview

```
Browser (React UI)
    ↕ HTTP + WebSocket
FastAPI Backend
    ↕ LLMService (single abstraction)
Ollama (local AI — port 11434)
```

**11 agents**, all invoked from `Orchestrator` (`backend/app/orchestrator/orchestrator.py`):
`PlannerAgent`, `CodeGenerationAgent`, `EditingAgent`, `ConversationAgent`,
`SearchAgent`, `PreviewAgent`, `RepositoryAgent`, `DebugAgent`, `ReviewAgent`,
`GitAgent`, `MemoryAgent`. Every one of them is wired into a real code path —
none are dead weight.

**4 Workflows**:
1. **Prompt → Website** — AI generates full React project from description
2. **ZIP Upload** — Upload existing code, AI analyses it, you continue
3. **GitHub Import** — Paste a public repo URL, it's cloned in (full history kept), AI analyses it, you continue
4. **Continue Development** — Ask AI to modify any generated project

---

## How It Works

1. User sends a message in the chat.
2. **PlannerAgent** classifies intent (`build` / `edit` / `refactor` / `debug`
   / `conversation`) and, when it can, produces an ordered `tasks[]` plan.
   The orchestrator dispatches each task to its named agent
   (`codegen|editing|refactoring|debug|review|repository|search`) in
   priority order; if the plan is empty or malformed, it falls back to a
   single intent-based branch instead of failing.
3. For **build**: `CodeGenerationAgent` generates all `src/` files as JSON.
4. For **edit/refactor/debug**: `SearchAgent` finds relevant files using a
   local semantic index (chunked + embedded via Ollama's `nomic-embed-text`,
   stored in a per-project `sqlite-vec` index — see `app/services/search_index.py`)
   merged with a keyword/glob heuristic, so a differently-worded request
   still finds the right file even with no literal keyword overlap. The
   index is incremental: unchanged files are never re-read or re-embedded
   on a later search. For refactors, this also includes every file that
   imports the target symbol (including via an aliased import), not just
   keyword matches. `EditingAgent`/`DebugAgent` then proposes changes,
   preferring small `search`/`replace` patches over full-file rewrites for
   localized changes.
5. **Before anything is written**, `ReviewAgent` scores the proposed files.
   Below the configured threshold (`review_score_threshold` in
   `backend/app/core/config.py`), the write is held back and the issues are
   shown to you instead — say "apply anyway" to force it through. Small,
   localized changes are applied as a minimal search/replace patch (even if
   the model handed back a full-file rewrite) so the rest of the file's
   formatting stays byte-identical; "remove this component" deletes the
   file via `/files/delete` instead of emptying it out; refactor/rename
   requests search the *import graph* (including aliased imports), not just
   filenames, so a rename doesn't silently miss a file.
6. Writes go through a single path-safe code path
   (`app/services/file_service.py`, built on `resolve_safe()`), then
   `GitAgent` snapshots the change.
7. `MemoryAgent` extracts theme/naming/library conventions from what just
   changed and persists them onto the project; the *next* turn's
   codegen/editing prompts include that memory so style stays consistent.
8. **PreviewAgent** starts a Vite dev server with canonical configs (never
   trusts LLM config output). Live preview appears in the iframe; file tree
   refreshes automatically.

---

## Reliability

- **Retries**: `LLMService.generate`/`.stream` retry connection errors, timeouts,
  and 5xx responses from Ollama (2 retries, exponential backoff + jitter) —
  a 4xx is never retried, since that means the request itself is bad.
- **Cancellable**: sending `{"type": "stop"}` over the project's WebSocket
  cancels the in-flight generation/edit for that project.
- **Concurrency-safe writes**: an `asyncio.Lock` per project serializes
  `_write_files`/`_apply_edits`, so two concurrent edits to the same project
  can't interleave writes to the same file.
- **Clean shutdown**: closes the shared `httpx` client and terminates every
  still-running `npm run dev` preview process instead of leaving them orphaned.
- **Abuse limits** on `/chat/send`: messages over `max_message_length`
  (20,000 chars by default) are rejected with `400`; a per-project in-memory
  rate limit (`chat_rate_limit_per_minute`, default 30/min) returns `429`.

---

## Security posture

This is a **single-user, local-first, unauthenticated** tool — treat it like a
local dev server, not a multi-tenant service:

- **No authentication** on the API or WebSocket. Anyone who can reach the
  backend port can read, write, and delete files under `projects/`.
- **Binds to `127.0.0.1` by default.** Only set `HOST=0.0.0.0` (in
  `backend/.env`) if you understand that exposes it to your whole network.
  The backend logs a loud warning at startup if you do.
- **Path containment**: every filesystem operation that takes a user- or
  LLM-supplied relative path (`/files/read`, `/files/write`, ZIP extraction)
  is routed through a single `resolve_safe()` utility
  (`backend/app/core/safe_path.py`) that rejects `..` traversal, absolute
  paths, and symlink escapes.
- **No shell interpolation**: all `npm`/`npx` subprocess calls in
  `PreviewAgent` use `shell=False` with an argument list, not a shell string.
- **GitHub import is URL-restricted**: `/api/upload/github` only accepts
  `https://github.com/<owner>/<repo>` — no `git://`, `ssh://`, `file://`, or
  other hosts — so it can't be used to make the backend fetch from an
  internal network address or the local filesystem (`app/services/github_service.py`).
- Run `pytest tests/security/` in `backend/` to exercise these guarantees.

---

## Testing & CI

```bash
cd backend && pytest tests/ -v          # 97 tests: security, orchestration, reliability, search
cd frontend && npm test                 # 27 tests: Zustand stores + api.ts error handling
```

`.github/workflows/ci.yml` runs both suites (plus a frontend typecheck) on
every push/PR. Log lines for one chat turn share a `message_id` correlation
id (see `app/core/logging_context.py`) — `grep <message_id>` in the backend
log traces that turn end-to-end across planner/agents/git/WebSocket events.

## Running with Docker Compose

An alternative to the manual 3-terminal setup above:

```bash
ollama serve                 # still runs on the host, not in a container
docker-compose up --build
```

Brings up `backend` (http://127.0.0.1:8000) and `frontend`
(http://127.0.0.1:5173), talking to the Ollama on your host via
`host.docker.internal`. Both ports are published to `127.0.0.1` only, matching
this app's no-auth security posture. Or use `./start.sh` (macOS/Linux) /
`./start.ps1` (Windows) to run both processes directly without Docker.

---

## Configuration

The default model is `qwen2.5-coder:7b`, and the embedding model for
semantic search is `nomic-embed-text`. To change either, edit:

```python
# backend/app/core/config.py
default_model = "qwen2.5-coder:7b"
embedding_model = "nomic-embed-text"
embedding_dim = 768  # must match the embedding model's output dimension
```

Any Ollama-compatible model can be used for either setting.

---

## License

MIT
