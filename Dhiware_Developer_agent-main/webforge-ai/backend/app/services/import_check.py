"""Detects hallucinated local imports in LLM-generated code.

The generation/editing models frequently describe a component (in their
intro text or their own JSX) that imports sibling files they never actually
included in the "files"/"new_files" JSON — e.g. `BillingScreen.tsx` importing
`./InvoiceTable`, `./Payments`, etc. that were never generated. Vite/tsc
correctly reports this as a hard "Cannot find module" error at preview time,
but by then there's no good recovery path for the user. This module finds
the gap while the result is still in memory, so the caller can do a single
targeted follow-up generation for exactly the missing files.
"""
from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from typing import Optional

# Reuse the same import-specifier shape PreviewAgent's npm dependency
# detection uses (import/export ... from '...', require(...), import(...)),
# but we only care about relative specifiers here — bare specifiers are npm
# packages, already handled separately by PreviewAgent.
_IMPORT_SPEC_RE = re.compile(
    r"""(?:import\s+(?:[\w*\s{},]+\s+from\s+)?|export\s+(?:[\w*\s{},]+\s+from\s+)?|require\(\s*|import\(\s*)"""
    r"""['"](\.[^'"]+)['"]"""
)
_NON_MODULE_SUFFIXES = (".css", ".scss", ".sass", ".less", ".json", ".svg", ".png", ".jpg", ".jpeg", ".gif")


@dataclass(frozen=True)
class MissingImport:
    importer: str  # path of the file that contains the import
    specifier: str  # the raw specifier as written, e.g. "./InvoiceTable"
    resolved_hint: str  # best-guess resolved path (no extension)


def find_missing_local_imports(
    files: list[dict], known_paths: Optional[set[str]] = None
) -> list[MissingImport]:
    """Return every relative import in `files` that doesn't resolve to a
    known file (by path, ignoring extension).

    By default the "known" universe is just the paths in `files` — fine
    when `files` is a complete, just-generated set (CodeGenerationAgent's
    case). Pass `known_paths` (e.g. every file actually on disk) when
    `files` is only a subset being scanned for imports but resolution
    should consider the whole project — this is what makes the check
    correct even when the caller's pre-fetched file snapshot was
    incomplete (see Orchestrator._repair_missing_local_imports).
    """
    if known_paths is not None:
        known_stems = {posixpath.splitext(p)[0] for p in known_paths}
    else:
        known_stems = {posixpath.splitext(f["path"])[0] for f in files if f.get("path")}
    missing: list[MissingImport] = []

    for f in files:
        path = f.get("path")
        content = f.get("content")
        if not path or not content:
            continue
        base_dir = posixpath.dirname(path)
        for match in _IMPORT_SPEC_RE.finditer(content):
            spec = match.group(1)
            if spec.endswith(_NON_MODULE_SUFFIXES):
                continue
            resolved = posixpath.normpath(posixpath.join(base_dir, spec))
            resolved_stem = posixpath.splitext(resolved)[0]
            if resolved_stem not in known_stems:
                missing.append(MissingImport(importer=path, specifier=spec, resolved_hint=resolved_stem))

    return missing
