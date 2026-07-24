"""Manages the development server for live preview."""
from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import shutil
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.core.config import settings

IS_WINDOWS = platform.system() == "Windows"


def _require_executable(name: str) -> str:
    """Resolve an executable via PATH, never via a shell. Raises with a
    clear message if it isn't installed rather than silently falling back
    to the shell (which is how this used to "just work" on Windows for
    npm.cmd/npx.cmd)."""
    path = shutil.which(name)
    if not path:
        raise FileNotFoundError(f"'{name}' was not found on PATH. Is Node.js installed?")
    return path

# ── Dependency auto-detection ────────────────────────────────────────────────
# The code generation LLM is allowed to import npm packages beyond react/react-dom
# when the user asks for them, but it never writes package.json. Without this,
# generated code silently imports packages that were never installed, and Vite
# crashes with "could not be resolved" the first time the preview is launched.
# We scan generated source for import specifiers and reconcile them here so the
# package actually gets installed, whether or not the LLM remembered to ask for it.

KNOWN_PACKAGE_VERSIONS: dict[str, str] = {
    "react-router-dom": "^6.22.3",
    "framer-motion": "^11.1.0",
    "zustand": "^4.5.2",
    "clsx": "^2.1.0",
    "lucide-react": "^0.363.0",
    "react-icons": "^5.0.1",
    "@headlessui/react": "^1.7.19",
    "@heroicons/react": "^2.1.3",
    "dayjs": "^1.11.10",
    "date-fns": "^3.6.0",
    "react-day-picker": "^8.10.0",
    "react-datepicker": "^6.9.0",
    "react-hook-form": "^7.51.0",
    "zod": "^3.22.4",
    "recharts": "^2.12.2",
    "chart.js": "^4.4.2",
    "react-chartjs-2": "^5.2.0",
    "@chakra-ui/react": "^2.8.2",
    "axios": "^1.6.8",
    "uuid": "^9.0.1",
    "classnames": "^2.5.1",
    "immer": "^10.0.4",
    "nanoid": "^5.0.6",
    "react-markdown": "^9.0.1",
    "remark-gfm": "^4.0.0",
    "rehype-highlight": "^7.0.0",
    "react-syntax-highlighter": "^15.5.0",
    "@monaco-editor/react": "^4.6.0",
    "monaco-editor": "^0.47.0",
}

_IMPORT_SPEC_RE = re.compile(
    r"""(?:import\s+(?:[\w*\s{},]+\s+from\s+)?|export\s+(?:[\w*\s{},]+\s+from\s+)?|require\(\s*|import\(\s*)"""
    r"""['"]([^'"]+)['"]"""
)
_SRC_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}


def _package_name_from_specifier(spec: str) -> Optional[str]:
    """Extract the installable npm package name from an import specifier,
    e.g. 'react-day-picker/dist/style.css' -> 'react-day-picker'."""
    if not spec or spec.startswith((".", "/")):
        return None
    parts = spec.split("/")
    if spec.startswith("@"):
        return "/".join(parts[:2]) if len(parts) >= 2 else None
    return parts[0]


def _find_imported_packages(root: Path) -> set[str]:
    """Scan generated src/ files for bare-specifier imports (external npm packages)."""
    src = root / "src"
    packages: set[str] = set()
    if not src.exists():
        return packages
    for path in src.rglob("*"):
        if not path.is_file() or path.suffix not in _SRC_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for match in _IMPORT_SPEC_RE.finditer(text):
            name = _package_name_from_specifier(match.group(1))
            if name:
                packages.add(name)
    return packages

# ── Canonical config templates (always written — never patched) ────────────────

def make_vite_config(port: int) -> str:
    return f"""\
import {{ defineConfig }} from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({{
  plugins: [react()],
  server: {{
    port: {port},
    host: true,
    strictPort: true,
    headers: {{
      'X-Frame-Options': 'ALLOWALL',
      'Access-Control-Allow-Origin': '*',
    }},
  }},
}})
"""

CANONICAL_TSCONFIG = """\
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": false,
    "noUnusedLocals": false,
    "noUnusedParameters": false
  },
  "include": ["src"]
}
"""

CANONICAL_PACKAGE_JSON = {
    "name": "webforge-project",
    "private": True,
    "version": "0.1.0",
    "type": "module",
    "scripts": {
        "dev": "vite",
        "build": "vite build",
        "preview": "vite preview"
    },
    "dependencies": {
        "react": "^18.2.0",
        "react-dom": "^18.2.0"
    },
    "devDependencies": {
        "@types/react": "^18.2.66",
        "@types/react-dom": "^18.2.22",
        "@vitejs/plugin-react": "^4.2.1",
        "typescript": "^5.2.2",
        "vite": "^5.2.0",
        "tailwindcss": "^3.4.3",
        "autoprefixer": "^10.4.19",
        "postcss": "^8.4.38"
    }
}

CANONICAL_POSTCSS = """\
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
"""

CANONICAL_TAILWIND = """\
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: { extend: {} },
  plugins: [],
}
"""

CANONICAL_INDEX_HTML = """\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>WebForge App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""

CANONICAL_MAIN_TSX = """\
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
"""

CANONICAL_INDEX_CSS = """\
@tailwind base;
@tailwind components;
@tailwind utilities;
"""

FALLBACK_APP_TSX = """\
import React from 'react'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-white mb-4">WebForge App</h1>
        <p className="text-gray-400">Your generated project is running.</p>
      </div>
    </div>
  )
}
"""


class PreviewAgent(BaseAgent):
    name = "preview"
    description = "Manages development server for live preview"

    _processes: dict[str, subprocess.Popen] = {}
    _ports: dict[str, int] = {}
    _executor = ThreadPoolExecutor(max_workers=4)

    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        action = kwargs.get("action", "start")
        if action == "start":
            return await self._start(context)
        elif action == "stop":
            return await self._stop(context.project_id)
        return AgentResult(success=True, content="Preview action complete")

    async def _start(self, context: AgentContext) -> AgentResult:
        if not context.root_path:
            return AgentResult(success=False, error="No project root")

        project_id = context.project_id
        root = Path(context.root_path)

        await self._stop(project_id)

        port = await self._find_port()
        if not port:
            return AgentResult(success=False, error="No available ports in range")

        # Move any source files the LLM placed in root into src/
        self._migrate_root_sources_to_src(root)

        # Always write canonical config files (no patching, no guessing)
        self._write_canonical_configs(root, port)

        # Run npm install if node_modules is missing or has wrong Vite version
        if self._needs_npm_install(root):
            self.logger.info(f"npm install → {root}")
            try:
                returncode, output = await asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    lambda: self._run_npm_install(root),
                )
                if returncode != 0:
                    return AgentResult(
                        success=False,
                        error=f"npm install failed:\n{output[-1000:]}",
                    )
            except Exception as e:
                return AgentResult(success=False, error=f"npm install error: {e}")

        # Verify the generated code actually resolves/compiles before ever
        # reporting "running" — this is what catches missing dependencies and
        # hallucinated library APIs (wrong exports, wrong props) before the
        # user opens a broken preview.
        try:
            tc_ok, tc_output = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self._run_typecheck(root),
            )
            if not tc_ok:
                return AgentResult(
                    success=False,
                    error=f"Generated code has TypeScript errors:\n\n{tc_output[-2000:]}",
                )
        except Exception as e:
            self.logger.warning(f"Typecheck skipped due to error: {e}")

        # Start Vite dev server
        env = {**os.environ, "BROWSER": "none", "NO_COLOR": "1"}
        try:
            npm = _require_executable("npm")
            process = subprocess.Popen(
                [npm, "run", "dev", "--", "--port", str(port), "--host"],
                cwd=str(root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
                text=True,
                bufsize=1,
            )
            self._processes[project_id] = process
            self._ports[project_id] = port

            ready = await self._wait_for_port(port, timeout=45, process=process)
            if not ready:
                output = self._drain_output(process)
                return AgentResult(
                    success=False,
                    error=f"Vite did not open port {port} within 45 s.\n\n{output[-1200:]}",
                )

            url = f"http://localhost:{port}"
            self.logger.info(f"Preview ready → {url}")
            return AgentResult(
                success=True,
                content=f"Preview running at {url}",
                data={"port": port, "url": url},
            )
        except Exception as e:
            return AgentResult(success=False, error=str(e))

    async def _stop(self, project_id: str) -> AgentResult:
        process = self._processes.pop(project_id, None)
        self._ports.pop(project_id, None)
        if process:
            try:
                process.terminate()
                await asyncio.sleep(0.5)
                if process.poll() is None:
                    process.kill()
            except Exception:
                pass
        return AgentResult(success=True, content="Preview stopped")

    async def stop_all(self) -> None:
        """Terminate every still-running dev server. Called on backend
        shutdown so a restart doesn't leave orphaned `npm run dev`
        processes holding preview ports open."""
        for project_id in list(self._processes.keys()):
            await self._stop(project_id)

    # ── Source migration ───────────────────────────────────────────────────────

    def _migrate_root_sources_to_src(self, root: Path) -> None:
        """
        Move any .tsx/.jsx/.ts/.js/.css source files the LLM placed in the
        project root into src/ where Vite expects them.
        Config files and package files are left alone.
        """
        CONFIG_NAMES = {
            "vite.config.ts", "vite.config.js", "tsconfig.json", "tsconfig.node.json",
            "postcss.config.js", "postcss.config.cjs", "tailwind.config.ts",
            "tailwind.config.js", "tailwind.config.cjs", "babel.config.js",
            ".eslintrc.js", ".prettierrc.js",
        }
        SOURCE_EXTENSIONS = {".tsx", ".jsx", ".ts", ".js", ".css", ".svg", ".png"}

        src = root / "src"
        src.mkdir(exist_ok=True)

        for f in list(root.iterdir()):
            if not f.is_file():
                continue
            if f.name in CONFIG_NAMES:
                continue
            if f.suffix not in SOURCE_EXTENSIONS:
                continue
            # Only migrate if not already a config name
            dest = src / f.name
            if not dest.exists():
                f.rename(dest)
                self.logger.info(f"Migrated {f.name} → src/{f.name}")

    # ── Config writers ─────────────────────────────────────────────────────────

    def _write_canonical_configs(self, root: Path, port: int) -> None:
        """
        Overwrite all Vite/TS/Tailwind config files with known-good templates.
        We never try to patch LLM output — we own the config layer entirely.
        The user's app code (src/) is left untouched.
        """
        # vite.config.ts — always replace entirely
        (root / "vite.config.ts").write_text(make_vite_config(port), encoding="utf-8")
        # Remove any other vite config that might conflict
        for name in ["vite.config.js", "vite.config.mts", "vite.config.mjs"]:
            (root / name).unlink(missing_ok=True)

        # tsconfig.json — replace with lenient config (skipLibCheck, strict:false)
        (root / "tsconfig.json").write_text(CANONICAL_TSCONFIG, encoding="utf-8")
        (root / "tsconfig.node.json").unlink(missing_ok=True)

        # postcss — always ESM, always replace
        for name in ["postcss.config.js", "postcss.config.cjs", "postcss.config.mjs"]:
            (root / name).unlink(missing_ok=True)
        (root / "postcss.config.js").write_text(CANONICAL_POSTCSS, encoding="utf-8")

        # tailwind config — always ESM, always replace
        for name in ["tailwind.config.js", "tailwind.config.cjs", "tailwind.config.ts"]:
            (root / name).unlink(missing_ok=True)
        (root / "tailwind.config.js").write_text(CANONICAL_TAILWIND, encoding="utf-8")

        # package.json — preserve LLM dependencies but fix scripts + type
        self._fix_package_json(root)

        # index.html — replace (src/main.tsx is the canonical entry)
        (root / "index.html").write_text(CANONICAL_INDEX_HTML, encoding="utf-8")

        # src/ essentials
        src = root / "src"
        src.mkdir(exist_ok=True)

        # Always write main.tsx (entry point must be stable)
        (src / "main.tsx").write_text(CANONICAL_MAIN_TSX, encoding="utf-8")
        # Remove index.tsx / index.jsx duplicates that confuse Vite
        for name in ["index.tsx", "index.jsx", "index.ts", "index.js"]:
            (src / name).unlink(missing_ok=True)

        # index.css — create only if missing (preserve LLM styles)
        if not any((src / f).exists() for f in ["index.css", "global.css", "globals.css"]):
            (src / "index.css").write_text(CANONICAL_INDEX_CSS, encoding="utf-8")
        else:
            # Ensure @tailwind directives are present
            css_path = next(
                (src / f for f in ["index.css", "global.css", "globals.css"] if (src / f).exists()),
                src / "index.css",
            )
            css = css_path.read_text(encoding="utf-8", errors="replace")
            if "@tailwind base" not in css:
                css_path.write_text(CANONICAL_INDEX_CSS + "\n" + css, encoding="utf-8")

        # App.tsx — create fallback only if completely missing
        if not any((src / f).exists() for f in ["App.tsx", "App.jsx", "App.ts", "App.js"]):
            (src / "App.tsx").write_text(FALLBACK_APP_TSX, encoding="utf-8")

        # Remove App.css if it exists (we use Tailwind, not CSS files)
        (src / "App.css").unlink(missing_ok=True)

        self.logger.info("Canonical config files written")

    def _fix_package_json(self, root: Path) -> None:
        """Merge LLM dependencies with canonical scripts and type:module."""
        pkg_path = root / "package.json"
        pkg = dict(CANONICAL_PACKAGE_JSON)  # start from canonical
        pkg["dependencies"] = dict(CANONICAL_PACKAGE_JSON["dependencies"])
        pkg["devDependencies"] = dict(CANONICAL_PACKAGE_JSON["devDependencies"])

        if pkg_path.exists():
            try:
                existing = json.loads(pkg_path.read_text(encoding="utf-8"))
                # Preserve LLM-specified dependencies
                if existing.get("dependencies"):
                    pkg["dependencies"].update(existing["dependencies"])
                if existing.get("devDependencies"):
                    pkg["devDependencies"].update(existing["devDependencies"])
                # Use project name if set
                if existing.get("name") and existing["name"] != "webforge-project":
                    pkg["name"] = existing["name"]
            except Exception:
                pass

        # Reconcile with what generated src/ files actually import — the LLM is
        # never allowed to write package.json itself, so this is the only place
        # that guarantees an imported package is actually installable.
        known = {**pkg["dependencies"], **pkg["devDependencies"]}
        missing = sorted(
            name for name in _find_imported_packages(root)
            if name not in known
        )
        for name in missing:
            pinned = KNOWN_PACKAGE_VERSIONS.get(name)
            if pinned is None:
                # Not in our allowlist — "latest" can silently pull a
                # breaking major version on the next npm install (this is
                # exactly how @chakra-ui/react "latest" resolved to v3 and
                # broke a generated component's Table API with no clear
                # error pointing back at the real cause). Loud on purpose.
                self.logger.warning(
                    f"'{name}' is not in KNOWN_PACKAGE_VERSIONS — pinning to \"latest\", "
                    f"which is not reproducible and may pull a breaking major version. "
                    f"Consider adding a known-good version to KNOWN_PACKAGE_VERSIONS."
                )
                pinned = "latest"
            pkg["dependencies"][name] = pinned
        if missing:
            self.logger.info(f"Auto-added missing dependencies: {', '.join(missing)}")

        pkg_path.write_text(json.dumps(pkg, indent=2), encoding="utf-8")

    # ── npm helpers ────────────────────────────────────────────────────────────

    def _needs_npm_install(self, root: Path) -> bool:
        """Return True if npm install must run."""
        node_modules = root / "node_modules"
        if not node_modules.exists():
            return True
        # Check if installed Vite matches expected major version
        vite_pkg = node_modules / "vite" / "package.json"
        if not vite_pkg.exists():
            return True
        try:
            v = json.loads(vite_pkg.read_text(encoding="utf-8")).get("version", "")
            if not v.startswith("5."):
                self.logger.info(f"Vite {v} installed but 5.x required — purging node_modules")
                import shutil
                shutil.rmtree(str(node_modules), ignore_errors=True)
                (root / "package-lock.json").unlink(missing_ok=True)
                return True
        except Exception:
            return True

        # Any declared dependency missing from node_modules? Catches packages
        # added by a later edit/refactor, when node_modules already existed.
        try:
            pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
            all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            for name in all_deps:
                if not (node_modules / name).exists():
                    return True
        except Exception:
            return True
        return False

    def _run_npm_install(self, root: Path) -> tuple[int, str]:
        npm = _require_executable("npm")
        result = subprocess.run(
            [npm, "install", "--prefer-offline"],
            cwd=str(root),
            shell=False,
            capture_output=True,
            text=True,
            timeout=240,
        )
        return result.returncode, (result.stdout or "") + (result.stderr or "")

    def _run_typecheck(self, root: Path) -> tuple[bool, str]:
        npx = _require_executable("npx")
        result = subprocess.run(
            [npx, "tsc", "--noEmit"],
            cwd=str(root),
            shell=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0, (result.stdout or "") + (result.stderr or "")

    # ── Process helpers ────────────────────────────────────────────────────────

    async def _wait_for_port(self, port: int, timeout: int, process: subprocess.Popen) -> bool:
        for _ in range(timeout):
            await asyncio.sleep(1)
            if process.poll() is not None:
                return False
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return True
        return False

    def _drain_output(self, process: subprocess.Popen) -> str:
        if not process.stdout:
            return ""
        lines = []
        try:
            for _ in range(100):
                line = process.stdout.readline()
                if not line:
                    break
                lines.append(line)
        except Exception:
            pass
        return "".join(lines)

    async def _find_port(self) -> Optional[int]:
        used = set(self._ports.values())
        for port in range(settings.preview_port_start, settings.preview_port_end):
            if port in used:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("localhost", port)) != 0:
                    return port
        return None
