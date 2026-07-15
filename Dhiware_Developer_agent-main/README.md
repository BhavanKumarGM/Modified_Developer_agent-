A production-grade, **local-first** AI Website Development Platform. Describe what you want to build, and WebForge AI generates a complete React + TypeScript project — with live preview, file editor, and iterative AI editing. No cloud AI, no API keys, no cost.

![WebForge AI](https://img.shields.io/badge/AI-Local%20Only-green) ![Ollama](https://img.shields.io/badge/Ollama-qwen2.5--coder%3A7b-blue) ![React](https://img.shields.io/badge/Frontend-React%2018-61DAFB) ![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)

---

## Features

- **Prompt → Website** — describe your app in plain English, get a full React project
- **ZIP Upload** — upload existing code, AI analyses the structure, continue developing
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

### 2. Install Ollama and pull the model

```bash
# Install Ollama from https://ollama.ai
ollama pull qwen2.5-coder:7b
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
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --timeout-keep-alive 300
```

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
│   │   ├── agents/          # 14 specialized AI agents
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

**14 Agents**: Planner → CodeGen / Editing / Conversation / Search / Preview / Repository / Debug / Review / Git / Memory

**3 Workflows**:
1. **Prompt → Website** — AI generates full React project from description
2. **ZIP Upload** — Upload existing code, AI analyses it, you continue
3. **Continue Development** — Ask AI to modify any generated project

---

## How It Works

1. User sends a message in the chat
2. **PlannerAgent** classifies intent (`build` / `edit` / `conversation`)
3. For **build**: CodeGenAgent generates all `src/` files as JSON, written to disk
4. For **edit**: SearchAgent finds relevant files → EditingAgent rewrites them fully
5. **PreviewAgent** starts a Vite dev server with canonical configs (never trusts LLM config output)
6. Live preview appears in the iframe; file tree refreshes automatically

---

## Configuration

The default model is `qwen2.5-coder:7b`. To change it, edit:

```python
# backend/app/core/config.py
default_model = "qwen2.5-coder:7b"
```

Any Ollama-compatible model can be used.

---

## License

MIT
