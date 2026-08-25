from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static, Select, TextArea

from client import NinerouterClient

class ConfirmScreen(ModalScreen):
    DEFAULT_CSS = """
    ConfirmScreen { align: center middle; }
    #confirm-container { width: 60; height: auto; background: $surface; border: thick $primary; padding: 1 2; }
    #confirm-msg { margin-bottom: 1; }
    """
    def __init__(self, msg: str, callback, **kw):
        super().__init__(**kw)
        self._msg = msg
        self._cb = callback
    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Button
        with Vertical(id="confirm-container"):
            yield Label(self._msg, id="confirm-msg")
            with Horizontal():
                yield Button("Yes", id="btn-confirm-yes", variant="error")
                yield Button("No", id="btn-confirm-no", variant="default")
    @on(Button.Pressed, "#btn-confirm-yes")
    def on_yes(self) -> None:
        self.dismiss(True)
        self._cb(True)
    @on(Button.Pressed, "#btn-confirm-no")
    def on_no(self) -> None:
        self.dismiss(False)
        self._cb(False)
