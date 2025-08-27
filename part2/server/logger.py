import json
import logging
import sys
import time
import uuid
from typing import Any


class JsonLogger:
    """
    Minimal structured logger that prints JSON lines to stdout.
    Usage:
        from .logger import log
        log("index_built", count=123, files=3)
    """
    def __init__(self, name: str = "app", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter('%(message)s'))

        # Avoid duplicate handlers if module reloaded
        if not any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers):
            self.logger.addHandler(handler)

    def log(self, event: str, **kwargs: Any) -> None:
        entry = {
            "event": event,
            "ts": time.time(),
            "request_id": str(uuid.uuid4()),
            **kwargs,
        }
        self.logger.info(json.dumps(entry, ensure_ascii=False))


# Convenience function
log = JsonLogger().log
