"""Logging setup for slate-agents."""

from __future__ import annotations

import logging
import sys

from .config import settings

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(
        stream=sys.stdout,
        level=settings.effective_log_level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Silence noisy google-genai SDK warnings that are normal during ADK operation
    logging.getLogger("google.genai.types").setLevel(logging.ERROR)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(name)
