"""Finds relevant files and symbols without loading the entire codebase."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult


class SearchAgent(BaseAgent):
    name = "search"
    description = "Finds relevant files and symbols for a given task"

    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        self._log_task(task)
        root_path = context.root_path
        if not root_path:
            return AgentResult(success=True, content="No project root", data={"files": []})

        root = Path(root_path)
        relevant_files = await self._find_relevant_files(task, root)

        return AgentResult(
            success=True,
            content=f"Found {len(relevant_files)} relevant files",
            data={"files": relevant_files},
        )

    async def _find_relevant_files(self, task: str, root: Path) -> list[str]:
        """Heuristic file relevance scoring based on task keywords."""
        task_lower = task.lower()
        keywords = set(task_lower.split())

        # Map keywords to likely file patterns
        patterns: list[str] = []
        if any(k in task_lower for k in ["auth", "login", "signup", "token", "jwt"]):
            patterns.extend(["*auth*", "*login*", "*user*", "*session*"])
        if any(k in task_lower for k in ["nav", "navbar", "navigation", "header"]):
            patterns.extend(["*nav*", "*header*", "*layout*"])
        if any(k in task_lower for k in ["dashboard", "home", "index"]):
            patterns.extend(["*dashboard*", "*home*", "index*"])
        if any(k in task_lower for k in ["api", "fetch", "request", "endpoint"]):
            patterns.extend(["*api*", "*service*", "*http*"])
        if any(k in task_lower for k in ["style", "css", "tailwind", "theme"]):
            patterns.extend(["*.css", "*theme*", "*styles*"])

        found: list[str] = []
        ignore = {"node_modules", "dist", "build", ".cache", ".git", "__pycache__"}

        for path in root.rglob("*"):
            if any(p in path.parts for p in ignore):
                continue
            if not path.is_file():
                continue
            rel = str(path.relative_to(root))
            name_lower = path.name.lower()

            # Check keyword match in path
            if any(kw in name_lower for kw in keywords if len(kw) > 3):
                found.append(rel)
            # Check pattern match
            elif any(path.match(p) for p in patterns):
                found.append(rel)

        # Always include key source files so the editing agent sees actual app code
        source_priority = [
            "src/App.tsx", "src/App.jsx", "src/app.tsx",
            "src/pages/index.tsx", "src/pages/Index.tsx",
            "src/index.tsx", "App.tsx",
        ]
        for p in source_priority:
            full = root / p
            if full.exists():
                rel = str(full.relative_to(root)).replace("\\", "/")
                if rel not in found:
                    found.append(rel)

        # If still very few source files found, add every .tsx/.jsx in src/
        src_dir = root / "src"
        if src_dir.exists() and len([f for f in found if f.endswith((".tsx", ".jsx", ".ts", ".js"))]) < 3:
            for path in sorted(src_dir.rglob("*.tsx")) + sorted(src_dir.rglob("*.jsx")):
                if any(p in path.parts for p in ignore):
                    continue
                rel = str(path.relative_to(root)).replace("\\", "/")
                if rel not in found:
                    found.append(rel)

        return found[:20]  # Limit to 20 most relevant
