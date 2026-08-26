"""Centralized logging configuration."""
import logging
import logging.handlers
import threading
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

_LOG_FMT = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# user_id → the FileHandler for their current session (created on login)
_session_handlers: dict[int, logging.FileHandler] = {}

# ContextVar propagates automatically into asyncio executor threads (used by
# LangGraph's ToolNode) and into threading.Thread instances (copied at start).
# This replaces threading.local(), which is not inherited across thread boundaries.
_user_ctx_var: ContextVar[int | None] = ContextVar("session_user_id", default=None)


class _RoutingHandler(logging.Handler):
    """Routes agent log records to the session file of the currently active user."""

    def emit(self, record: logging.LogRecord) -> None:
        user_id = _user_ctx_var.get()
        if user_id is None:
            return
        handler = _session_handlers.get(user_id)
        if handler:
            handler.handle(record)


def open_user_session(user_id: int) -> None:
    """Create a new session log file for this user. Called once on login."""
    sessions_dir = Path(__file__).parent.parent.parent / "logs" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_path = sessions_dir / f"session_user{user_id}_{timestamp}.log"

    handler = logging.FileHandler(session_path, encoding="utf-8")
    handler.setFormatter(_LOG_FMT)
    handler.setLevel(logging.DEBUG)

    old = _session_handlers.pop(user_id, None)
    if old:
        old.close()
    _session_handlers[user_id] = handler


def set_session_user(user_id: int) -> None:
    """Bind user_id to the current context.
    Propagates automatically into executor threads and child threads."""
    if user_id not in _session_handlers:
        open_user_session(user_id)
    _user_ctx_var.set(user_id)


def clear_session_user() -> None:
    """Clear the user binding from the current context."""
    _user_ctx_var.set(None)


def setup_logging() -> None:
    logs_dir = Path(__file__).parent.parent.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # ── Error log ──────────────────────────────────────────────────────────
    # Buffered in memory; file is only created when an ERROR is emitted.
    error_path = logs_dir / f"error_{timestamp}.log"
    error_file = logging.FileHandler(error_path, delay=True)
    error_file.setFormatter(_LOG_FMT)
    memory_handler = logging.handlers.MemoryHandler(
        capacity=1000,
        flushLevel=logging.ERROR,
        target=error_file,
        flushOnClose=False,
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(memory_handler)

    # ── Session log ────────────────────────────────────────────────────────
    # The routing handler dispatches each record to the file of whichever user
    # is active on the current thread (set by the agent request handler).
    # Attach to both namespaces: agent modules under the `agents` package resolve
    # to either `agents.*` or `server.agents.*` depending on import path.
    for ns in ("agents", "server.agents"):
        ns_logger = logging.getLogger(ns)
        ns_logger.addHandler(_RoutingHandler())
        ns_logger.propagate = True

    # ── Suppress noisy third-party loggers ────────────────────────────────
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
