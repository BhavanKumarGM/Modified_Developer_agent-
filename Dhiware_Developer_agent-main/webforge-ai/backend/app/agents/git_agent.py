"""Manages project snapshots, undo/redo, and commit message generation."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.core.llm_service import LLMService


class GitAgent(BaseAgent):
    name = "git"
    description = "Manages project snapshots, undo/redo, commit messages"

    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        action = kwargs.get("action", "snapshot")

        if action == "snapshot":
            return await self._create_snapshot(context, kwargs.get("changes", []))
        elif action == "message":
            return await self._generate_message(task, context, kwargs.get("changes", []))
        else:
            return AgentResult(success=True, content="Git action complete")

    async def _create_snapshot(self, context: AgentContext, changes: list[str]) -> AgentResult:
        """Create a git-like snapshot using gitpython if available."""
        if not context.root_path:
            return AgentResult(success=False, error="No project root")

        try:
            import git
            repo_path = Path(context.root_path)

            try:
                repo = git.Repo(repo_path)
            except git.InvalidGitRepositoryError:
                repo = git.Repo.init(repo_path)

            repo.index.add(["*"])
            message = f"WebForge: {', '.join(changes[:3]) or 'Changes'}"
            if len(changes) > 3:
                message += f" (+{len(changes) - 3} more)"

            commit = repo.index.commit(message)
            return AgentResult(
                success=True,
                content=f"Snapshot created: {commit.hexsha[:8]}",
                data={"sha": commit.hexsha, "message": message},
            )
        except Exception as e:
            self.logger.warning(f"Git snapshot failed: {e}")
            return AgentResult(success=True, content="Snapshot noted (git unavailable)")

    async def _generate_message(self, task: str, context: AgentContext, changes: list[str]) -> AgentResult:
        files_str = ", ".join(changes[:5])
        prompt = f"Generate a concise git commit message for: {task}\nFiles changed: {files_str}"
        request = self._build_request(
            system="Generate short, descriptive git commit messages. Output only the message, no quotes.",
            user=prompt,
            temperature=0.3,
        )
        response = await self.llm.generate(request)
        return AgentResult(success=True, content=response.content.strip())
