"""Per-turn correlation ID for logging.

`message_id` (already generated once per chat turn — see routers/chat.py)
is threaded through a contextvar so every log line emitted anywhere during
that turn's planner → agent → git → WebSocket-event lifecycle carries the
same id, without having to pass it explicitly through every function
signature. Set once at the top of Orchestrator.handle_message; every
logger in the process shares the one handler main.py attaches the
MessageIdFilter to, so this works regardless of which module logs.
"""
from __future__ import annotations

import contextvars
import logging

message_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("message_id", default="-")


class MessageIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.message_id = message_id_var.get()
        return True
