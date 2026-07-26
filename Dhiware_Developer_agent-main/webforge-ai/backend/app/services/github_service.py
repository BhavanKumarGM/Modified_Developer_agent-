"""GitHub repository import: validate the URL, then clone it via GitPython
(the same `git` package GitAgent already uses for local snapshots — no new
subprocess/shell surface).

Only public github.com HTTPS URLs are accepted. This app has no
authentication, so a permissive clone target (git://, ssh://, file://, or
an arbitrary host) would let a caller make the backend fetch from anywhere
reachable from this machine — including internal network addresses or the
local filesystem — not just the intended public repo. Restricting to
`https://github.com/<owner>/<repo>` closes that off.
"""
from __future__ import annotations

import re
from pathlib import Path

import git

_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9][A-Za-z0-9-]{0,38})"
    r"/(?P<repo>[A-Za-z0-9._-]+?)(?:\.git)?/?$"
)


class InvalidGitHubUrlError(ValueError):
    """Raised when a URL is not an acceptable public github.com repo URL."""


def parse_github_url(url: str) -> tuple[str, str]:
    """Validate `url` and return (owner, repo). Raises
    InvalidGitHubUrlError if it isn't a public github.com HTTPS repo URL."""
    match = _GITHUB_URL_RE.match(url.strip())
    if not match:
        raise InvalidGitHubUrlError(
            "Only public GitHub repository URLs are supported, e.g. "
            "https://github.com/owner/repo"
        )
    return match.group("owner"), match.group("repo")


def clone_repo(url: str, dest: Path) -> None:
    """Clone `url` into `dest` (which must not exist or be empty).

    Callers MUST validate `url` with parse_github_url() first — this
    function does not re-validate, so skipping that check would let an
    arbitrary URL reach `git clone`. Raises git.GitCommandError (repo not
    found, network failure, etc.) on failure. This performs a full clone
    (not shallow) so the repository's actual commit history is preserved,
    matching what a "real git clone" is expected to do.
    """
    git.Repo.clone_from(url, str(dest))
