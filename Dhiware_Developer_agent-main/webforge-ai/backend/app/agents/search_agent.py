"""Finds relevant files and symbols without loading the entire codebase."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.services.search_index import SearchIndex


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

        # For renames/refactors, a keyword/pattern search alone silently
        # misses files that import the renamed symbol but don't otherwise
        # mention it by name (e.g. `import { Button as PrimaryAction }`).
        # Callers pass the symbol(s) being renamed via kwargs["symbols"];
        # every file that imports any of them — under any local alias —
        # gets merged into the result.
        symbols = kwargs.get("symbols") or []
        if symbols:
            importing_files = await self._find_files_importing_symbols(symbols, root)
            for f in importing_files:
                if f not in relevant_files:
                    relevant_files.append(f)

        # Real semantic search, merged with (not replacing) the keyword/glob
        # heuristic above — a query phrased differently from any filename
        # or keyword still finds the right file via embedding similarity.
        # Semantic hits are precision-ranked, so they're listed first; if
        # the embedding model isn't available this silently contributes
        # nothing and the keyword results still work.
        semantic_files = await self._semantic_search(task, context, root)
        merged = list(semantic_files)
        for f in relevant_files:
            if f not in merged:
                merged.append(f)

        return AgentResult(
            success=True,
            content=f"Found {len(merged)} relevant files",
            data={"files": merged[:20]},
        )

    async def _semantic_search(self, task: str, context: AgentContext, root: Path) -> list[str]:
        try:
            index = SearchIndex(context.project_id)
            await index.sync(root, self.llm.embed)
            return await index.search(task, self.llm.embed, top_k=8)
        except Exception as e:
            self.logger.warning(f"Semantic search unavailable, falling back to keyword search only: {e}")
            return []

    # ── Import-graph search (for rename/refactor) ────────────────────────────

    _NAMED_IMPORT_RE = re.compile(r"import\s+(?:type\s+)?\{([^}]*)\}")
    _DEFAULT_IMPORT_RE = re.compile(r"import\s+(\w+)\s*(?:,\s*\{[^}]*\})?\s+from")
    _SRC_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}

    async def _find_files_importing_symbols(self, symbols: list[str], root: Path) -> list[str]:
        """Find every source file that imports any of `symbols`, including
        via a different local alias — a plain filename/keyword search
        misses these, which is how multi-file renames silently drop files."""
        ignore = {"node_modules", "dist", "build", ".cache", ".git", "__pycache__"}
        matches: list[str] = []
        for path in root.rglob("*"):
            if any(p in ignore for p in path.parts):
                continue
            if not path.is_file() or path.suffix not in self._SRC_EXTENSIONS:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if any(self._imports_symbol(text, symbol) for symbol in symbols):
                matches.append(str(path.relative_to(root)).replace("\\", "/"))
        return matches

    @classmethod
    def _imports_symbol(cls, text: str, symbol: str) -> bool:
        for line in text.splitlines():
            if "import" not in line or "from" not in line:
                continue

            named = cls._NAMED_IMPORT_RE.search(line)
            if named:
                for spec in named.group(1).split(","):
                    # `{ Foo as Bar }` — what's being renamed is the
                    # EXPORTED name (Foo), which still appears here even
                    # though the file only ever refers to it locally as Bar.
                    exported_name = spec.strip().split(" as ")[0].strip()
                    if exported_name == symbol:
                        return True

            default = cls._DEFAULT_IMPORT_RE.search(line)
            if default and default.group(1) == symbol:
                return True

        return False

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
