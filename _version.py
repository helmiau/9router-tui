"""Single source of truth for 9Router TUI version."""
from __future__ import annotations

import pathlib

def _read_version() -> str:
    try:
        return pathlib.Path(__file__).with_name("VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        return "1.0.0"

__version__ = _read_version()
VERSION = __version__
