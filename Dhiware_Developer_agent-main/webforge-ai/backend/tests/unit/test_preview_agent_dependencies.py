"""Regression tests for PreviewAgent's dependency auto-detection fallback.

Before this fix, any auto-detected import not in KNOWN_PACKAGE_VERSIONS was
silently pinned to "latest" with no logging. This is exactly what caused a
live incident: @chakra-ui/react wasn't in the map, got pinned to "latest",
resolved to Chakra v3 (which restructured the Table API), and broke the
build with an error that gave no hint the root cause was an unpinned,
non-reproducible dependency version.
"""
import json
import logging

import pytest

from app.agents.preview_agent import KNOWN_PACKAGE_VERSIONS, PreviewAgent
from app.core.llm_service import LLMService


@pytest.fixture()
def agent():
    return PreviewAgent(LLMService())


def _write_import(root, package: str):
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "App.tsx").write_text(f"import Thing from '{package}'\n", encoding="utf-8")


def test_chakra_ui_react_is_pinned_to_a_known_v2_version():
    """Direct regression test for the incident: the exact package that broke
    must now be pinned, not left to fall through to "latest"."""
    assert "@chakra-ui/react" in KNOWN_PACKAGE_VERSIONS
    assert KNOWN_PACKAGE_VERSIONS["@chakra-ui/react"].startswith("^2.")


def test_known_package_is_pinned_without_a_warning(agent, tmp_path, caplog):
    _write_import(tmp_path, "zustand")

    with caplog.at_level(logging.WARNING):
        agent._fix_package_json(tmp_path)

    pkg = json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))
    assert pkg["dependencies"]["zustand"] == KNOWN_PACKAGE_VERSIONS["zustand"]
    assert not any("latest" in r.message for r in caplog.records)


def test_unknown_package_falls_back_to_latest_with_a_warning(agent, tmp_path, caplog):
    _write_import(tmp_path, "some-totally-unknown-package")

    with caplog.at_level(logging.WARNING):
        agent._fix_package_json(tmp_path)

    pkg = json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))
    assert pkg["dependencies"]["some-totally-unknown-package"] == "latest"

    warnings = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("some-totally-unknown-package" in w and "latest" in w for w in warnings)
