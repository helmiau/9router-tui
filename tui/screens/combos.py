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

class ComboEditScreen(ModalScreen):
    DEFAULT_CSS = """
    ComboEditScreen { align: center middle; }
    #combo-edit-container { width: 76; height: auto; max-height: 36; background: $surface; border: thick $primary; padding: 1 2; }
    #combo-edit-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #combo-edit-status { height: auto; margin: 1 0; }
    #combo-edit-fields Input { margin: 1 0; }
    """
    def __init__(self, client, rec, callback, **kw):
        super().__init__(**kw)
        self._client = client
        self._rec = rec
        self._cb = callback
    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Input, Button
        is_edit = self._rec is not None
        rec = self._rec or {}
        models_val = ", ".join(rec.get("models", [])) if rec.get("models") else ""
        with Vertical(id="combo-edit-container"):
            yield Label("Edit Combo" if is_edit else "Add Combo", id="combo-edit-title")
            with Vertical(id="combo-edit-fields"):
                yield Label("Name (a-z, 0-9, -, _, .)")
                yield Input(value=rec.get("name", ""), placeholder="e.g. my-combo", id="combo-name")
                yield Label("Kind (optional)")
                yield Input(value=rec.get("kind", "") or "", placeholder="kind", id="combo-kind")
                yield Label("Models (comma-separated, e.g. openai/gpt-4o, anthropic/claude-sonnet-4)")
                yield Input(value=models_val, placeholder="model1, model2, ...", id="combo-models")
            yield Static("", id="combo-edit-status")
            with Horizontal():
                yield Button("Save", id="btn-combo-save", variant="primary")
                yield Button("Cancel", id="btn-combo-cancel", variant="default")
    @on(Button.Pressed, "#btn-combo-save")
    def on_save(self) -> None:
        try:
            name = self.query_one("#combo-name", Input).value.strip()
            kind = self.query_one("#combo-kind", Input).value.strip() or None
            models_raw = self.query_one("#combo-models", Input).value.strip()
            models = [m.strip() for m in models_raw.split(",") if m.strip()] if models_raw else []
            if not name:
                self.query_one("#combo-edit-status", Static).update("[red]Name is required[/]")
                return
            import re
            if not re.match(r"^[a-zA-Z0-9_.\-]+$", name):
                self.query_one("#combo-edit-status", Static).update("[red]Name can only contain letters, numbers, -, _, .[/]")
                return
            payload = {"name": name, "models": models}
            if kind:
                payload["kind"] = kind
            import asyncio as _aio
            async def _do():
                try:
                    if self._rec:
                        await _aio.to_thread(self._client.update_combo, self._rec["id"], payload)
                    else:
                        await _aio.to_thread(self._client.create_combo, payload)
                    self.app.notify("Saved", timeout=2)
                    self.dismiss(True)
                    self._cb(True)
                except Exception as e:
                    self.query_one("#combo-edit-status", Static).update(f"[red]{e}[/]")
            _aio.create_task(_do())
        except Exception as e:
            try:
                self.query_one("#combo-edit-status", Static).update(f"[red]{e}[/]")
            except Exception:
                pass
    @on(Button.Pressed, "#btn-combo-cancel")
    def on_cancel(self) -> None:
        self.dismiss(False)
        self._cb(False)
