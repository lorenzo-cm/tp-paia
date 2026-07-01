import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

DEFAULT_LOG_CONTEXT = {
    "conversation_id": "-",
    "external_conversation_id": "-",
    "contact_external_id": "-",
    "inbox_id": "-",
}
_LOG_CONTEXT: ContextVar[dict[str, str] | None] = ContextVar(
    "log_context", default=None
)


class LevelFilter(logging.Filter):
    def __init__(self, low: int, high: int) -> None:
        super().__init__()
        self.low = low
        self.high = high

    def filter(self, record: logging.LogRecord) -> bool:
        return self.low <= record.levelno <= self.high


class ContextFieldsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = _current_log_context()
        for field, default in DEFAULT_LOG_CONTEXT.items():
            if not hasattr(record, field):
                setattr(record, field, context.get(field, default))
        return True


def _current_log_context() -> dict[str, str]:
    context = _LOG_CONTEXT.get()
    if context is None:
        return DEFAULT_LOG_CONTEXT.copy()
    return context


def bind_log_context(**values: object) -> Token[dict[str, str]]:
    current = _current_log_context().copy()
    for key, value in values.items():
        if key not in DEFAULT_LOG_CONTEXT:
            continue
        current[key] = str(value) if value is not None else DEFAULT_LOG_CONTEXT[key]
    return _LOG_CONTEXT.set(current)


def reset_log_context(token: Token[dict[str, str]]) -> None:
    _LOG_CONTEXT.reset(token)


@contextmanager
def log_context(**values: object):
    token = bind_log_context(**values)
    try:
        yield
    finally:
        reset_log_context(token)


def setup_logging() -> None:
    formatter: logging.Formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | %(levelname)s | %(name)s | "
            "conv=%(conversation_id)s ext_conv=%(external_conversation_id)s "
            "contact=%(contact_external_id)s inbox=%(inbox_id)s | %(message)s"
        ),
        datefmt="%d-%m-%Y %H:%M:%S",
    )

    logger: logging.Logger = logging.getLogger()
    if getattr(logger, "_tp_paia_logging_configured", False):
        return

    # === FILE HANDLER: progress.log (INFO até WARNING) ===
    progress_handler: logging.FileHandler = logging.FileHandler(
        f"{LOG_DIR}/app.log", mode="a"
    )
    progress_handler.setLevel(logging.INFO)
    progress_handler.addFilter(LevelFilter(logging.INFO, logging.WARNING))
    progress_handler.addFilter(ContextFieldsFilter())
    progress_handler.setFormatter(formatter)

    # === FILE HANDLER: errors.log (ERROR e CRITICAL) ===
    error_handler: logging.FileHandler = logging.FileHandler(
        f"{LOG_DIR}/errors.log", mode="a"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.addFilter(LevelFilter(logging.ERROR, logging.CRITICAL))
    error_handler.addFilter(ContextFieldsFilter())
    error_handler.setFormatter(formatter)

    # === CONSOLE HANDLER ===
    console_handler: logging.StreamHandler[Any] = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.addFilter(ContextFieldsFilter())
    console_handler.setFormatter(formatter)

    # === ROOT LOGGER ===
    logger.setLevel(logging.INFO)
    logger.addHandler(progress_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    logger._tp_paia_logging_configured = True  # type: ignore[attr-defined]
