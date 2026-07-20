"""Regression tests for default network exposure.

Before the fix, the documented/default way to run the backend bound
0.0.0.0 with zero authentication, exposing full file read/write/delete to
anyone on the network. The fix defaults to 127.0.0.1 and loudly warns if
ever started on 0.0.0.0.
"""
import logging

import pytest

import app.main as main_module
from app.core.config import settings


def test_default_host_is_loopback_only():
    assert settings.host == "127.0.0.1"


async def test_lifespan_logs_bind_address_and_warns_on_0000(monkeypatch, caplog):
    async def fake_init_db():
        return None

    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(settings, "host", "0.0.0.0")
    monkeypatch.setattr(settings, "port", 8000)

    with caplog.at_level(logging.INFO, logger="webforge"):
        async with main_module.lifespan(main_module.app):
            pass

    messages = "\n".join(r.message for r in caplog.records)
    assert "0.0.0.0:8000" in messages
    assert "reachable from the network" in messages
    assert "no authentication" in messages.lower()


async def test_lifespan_does_not_warn_on_loopback(monkeypatch, caplog):
    async def fake_init_db():
        return None

    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(settings, "host", "127.0.0.1")
    monkeypatch.setattr(settings, "port", 8000)

    with caplog.at_level(logging.INFO, logger="webforge"):
        async with main_module.lifespan(main_module.app):
            pass

    messages = "\n".join(r.message for r in caplog.records)
    assert "127.0.0.1:8000" in messages
    assert "reachable from the network" not in messages
