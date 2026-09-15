"""Only predefined events are logged; arbitrary messages/tracebacks are discarded."""
import json
import logging
from datetime import datetime, timezone

EVENTS = {"request_complete", "database_unavailable", "unhandled_error", "seed_complete"}


class PrivacyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "safe_event", None)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname if record.levelname in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO",
            "event": event if isinstance(event, str) and event in EVENTS else "system_event",
        }
        status = getattr(record, "safe_status", None)
        if type(status) is int and 100 <= status <= 599:
            payload["status"] = status
        return json.dumps(payload)


class PrivacyHandler(logging.StreamHandler):
    def handleError(self, record: logging.LogRecord) -> None:
        # Python's default logging error reporter prints the original record,
        # including its unredacted message. Fail closed if the output stream fails.
        pass


def configure_logging() -> None:
    handler = PrivacyHandler()
    handler.setFormatter(PrivacyFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    # Uvicorn and SQLAlchemy must not bypass the privacy formatter.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy", "sqlalchemy.engine"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


def safe_log(event: str, *, status: int | None = None) -> None:
    logging.getLogger("mpe").info("", extra={"safe_event": event, "safe_status": status})
