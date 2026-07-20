"""Generates new files, components, pages, and APIs from structured plans."""
from __future__ import annotations

from typing import Any, AsyncIterator

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.core.llm_service import LLMService

SYSTEM_PROMPT = """You are the Code Generation Agent for WebForge AI.

Your job: generate the APPLICATION SOURCE CODE for a React + Vite + TypeScript + Tailwind project.

IMPORTANT: The build system (vite.config, tsconfig, postcss, tailwind config, package.json, index.html, src/main.tsx, src/index.css) is handled separately. Do NOT generate those files. Focus exclusively on the app source code.

Output ONLY valid JSON — no markdown, no explanation, nothing outside the JSON:
{
  "files": [
    {"path": "src/App.tsx", "content": "..."},
    {"path": "src/components/Hero.tsx", "content": "..."},
    {"path": "src/components/Navbar.tsx", "content": "..."},
    ... (all other src/ files needed)
  ],
  "framework": "react",
  "description": "Brief description of what was generated"
}

RULES:
1. Only generate files under src/ — no config files, no package.json, no index.html.
2. src/App.tsx MUST be the root component. It is the entry point.
3. Use Tailwind CSS classes for ALL styling. No inline styles. No separate .css files.
4. Generate COMPLETE, WORKING TypeScript/React code. No TODOs, no placeholders.
5. Every component must have proper TypeScript types and props interfaces.
6. Do NOT import from 'react-router-dom', 'framer-motion', or any library not in the base package.json unless it is a standard React pattern.
7. Keep imports to: react, react-dom, and built-in browser APIs only (unless user asks for specific libs).
8. Output ONLY the JSON object. Start with { and end with }.
"""


class CodeGenerationAgent(BaseAgent):
    name = "codegen"
    description = "Generates new files, components, pages, and complete projects"

    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        self._log_task(task)
        plan_data = kwargs.get("plan", {})
        memory_section = self._format_memory(context.metadata)

        prompt = f"""Generate the React source code for:

"{task}"

Requirements:
- Beautiful, modern, responsive UI using Tailwind CSS
- Dark theme preferred unless specified otherwise
- Generate ALL necessary src/ components, pages, hooks, and utilities
- src/App.tsx is the root — it must render the full application
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

            # Post-process: ensure critical files exist
            data["files"] = self._ensure_critical_files(files)

            paths = [f["path"] for f in data["files"]]
            return AgentResult(
                success=True,
                content=f"Generated {len(data['files'])} files",
                data=data,
                files_modified=paths,
            )
        except Exception as e:
            self.logger.error(f"JSON parse error: {e}\nRaw: {response.content[:500]}")
            return AgentResult(success=False, error=str(e), content=response.content)

    async def stream(self, task: str, context: AgentContext, **kwargs: Any) -> AsyncIterator[str]:
        """Stream a brief description of what will be built."""
        summary_prompt = f"""The user wants to build: "{task}"

Write 2-3 sentences describing what you will generate (components, pages, features).
Be specific. Then write "⚡ Generating files now…" on a new line."""

        request = self._build_request(
            system="You are a helpful AI coding assistant. Be concise and specific.",
            user=summary_prompt,
            temperature=0.5,
        )
        async for token in self.llm.stream(request):
            yield token

    def _ensure_critical_files(self, files: list[dict]) -> list[dict]:
        """
        Keep only src/ files — config files are written by PreviewAgent.
        Ensure App.tsx exists as a fallback.
        """
        # Strip any config files the LLM might have generated anyway
        CONFIG_FILES = {
            "package.json", "index.html", "vite.config.ts", "vite.config.js",
            "tsconfig.json", "tsconfig.node.json", "tailwind.config.ts",
            "tailwind.config.js", "postcss.config.js", "postcss.config.cjs",
        }
        files = [f for f in files if f["path"] not in CONFIG_FILES]

        # Ensure App.tsx exists
        has_app = any(f["path"] in {"src/App.tsx", "src/App.jsx"} for f in files)
        if not has_app:
            files.insert(0, {"path": "src/App.tsx", "content": (
                "import React from 'react'\n\n"
                "export default function App() {\n"
                "  return (\n"
                "    <div className=\"min-h-screen bg-gray-950 flex items-center justify-center\">\n"
                "      <h1 className=\"text-3xl font-bold text-white\">WebForge App</h1>\n"
                "    </div>\n"
                "  )\n"
                "}\n"
            )})

        return files
