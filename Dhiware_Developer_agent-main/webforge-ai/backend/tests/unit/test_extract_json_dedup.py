"""Regression tests for the JSON-extraction deduplication (audit item 2.4).

Before the fix, six agents each had their own copy-pasted `_extract_json`
using a greedy regex (`re.search(r'\\{[\\s\\S]+\\}', text)`), which
over-matches when the LLM response contains stray braces in prose before or
after the actual JSON object. The fix moves a single hardened
implementation onto BaseAgent.
"""
import re
from pathlib import Path

import pytest

from app.agents.base_agent import BaseAgent


AGENTS_DIR = Path(__file__).resolve().parents[2] / "app" / "agents"


def test_extract_json_defined_in_exactly_one_agent_file():
    matches = []
    for path in AGENTS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"def _extract_json\(", text):
            matches.append(path.name)
    assert matches == ["base_agent.py"], (
        f"_extract_json must be defined only on BaseAgent, found in: {matches}"
    )


class _DummyAgent(BaseAgent):
    name = "dummy"

    async def run(self, task, context, **kwargs):
        raise NotImplementedError


@pytest.fixture()
def agent():
    return _DummyAgent(llm=object())


def test_extracts_plain_json(agent):
    result = agent._extract_json('{"a": 1, "b": "two"}')
    assert result == {"a": 1, "b": "two"}


def test_extracts_json_with_surrounding_prose(agent):
    text = 'Sure thing! Here is the plan: {"intent": "build", "tasks": []} Hope that helps!'
    result = agent._extract_json(text)
    assert result == {"intent": "build", "tasks": []}


def test_ignores_stray_braces_in_prose_before_json():
    """The old greedy regex `\\{[\\s\\S]+\\}` would match from the FIRST
    '{' to the LAST '}' in the whole text, swallowing unrelated prose braces
    into what should be a small clean object. raw_decode must not do that."""
    agent = _DummyAgent(llm=object())
    text = 'Note: use the {value} placeholder syntax. Plan: {"intent": "edit"}'
    result = agent._extract_json(text)
    assert result == {"intent": "edit"}


def test_repairs_literal_newlines_inside_string_values(agent):
    # Invalid JSON: a literal newline inside a string value.
    text = '{"content": "line one\nline two"}'
    result = agent._extract_json(text)
    assert result == {"content": "line one\nline two"}


def test_raises_value_error_when_no_json_present(agent):
    with pytest.raises(ValueError):
        agent._extract_json("no json here at all")
