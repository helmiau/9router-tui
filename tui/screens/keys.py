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

class KeyCreateScreen(ModalScreen):
    DEFAULT_CSS = """
    KeyCreateScreen { align: center middle; }
    #key-create-container { width: 60; height: auto; background: $surface; border: thick $primary; padding: 1 2; }
    #key-create-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #key-create-status { height: auto; margin: 1 0; }
    """
    def __init__(self, client, callback, **kw):
        super().__init__(**kw)
        self._client = client
        self._cb = callback
    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Input, Button
        with Vertical(id="key-create-container"):
            yield Label("Create API Key", id="key-create-title")
            yield Input(placeholder="Key name (e.g. my-key)", id="key-name")
            yield Static("", id="key-create-status")
            with Horizontal():
                yield Button("Create", id="btn-key-create", variant="primary")
                yield Button("Cancel", id="btn-key-cancel", variant="default")
    @on(Button.Pressed, "#btn-key-create")
    def on_create(self) -> None:
        try:
            name = self.query_one("#key-name", Input).value.strip()
            if not name:
                self.query_one("#key-create-status", Static).update("[red]Name is required[/]")
                return
            import asyncio as _aio
            async def _do():
                try:
                    res = await _aio.to_thread(self._client.create_key, name)
                    key_val = res.get("key", res.get("apiKey", ""))
                    # Show key once
                    self.app.push_screen(KeyShowScreen(key_val, res.get("name", name)))
                    self.app.notify(f"Created key: {name}", timeout=3)
                    self.dismiss(True)
                    self._cb(True)
                except Exception as e:
                    self.query_one("#key-create-status", Static).update(f"[red]{e}[/]")
            _aio.create_task(_do())
        except Exception as e:
            try:
                self.query_one("#key-create-status", Static).update(f"[red]{e}[/]")
            except Exception:
                pass
    @on(Button.Pressed, "#btn-key-cancel")
    def on_cancel(self) -> None:
        self.dismiss(False)
        self._cb(False)

class KeyShowScreen(ModalScreen):
    DEFAULT_CSS = """
    KeyShowScreen { align: center middle; }
    #key-show-container { width: 70; height: auto; background: $surface; border: thick $primary; padding: 1 2; }
    #key-show-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #key-show-value { padding: 1 1; border: solid $primary-background; margin: 1 0; }
    """
    def __init__(self, key_val: str, name: str, **kw):
        super().__init__(**kw)
        self._key = key_val
        self._name = name
    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Button
        with Vertical(id="key-show-container"):
            yield Label(f"API Key Created — {self._name}", id="key-show-title")
            yield Static(f"[bold]{self._key}[/]", id="key-show-value")
            yield Static("[yellow]Copy this key now — it won't be shown again![/]", id="key-show-hint")
            with Horizontal():
                yield Button("Copy", id="btn-key-copy", variant="primary")
                yield Button("Close", id="btn-key-close", variant="default")
    @on(Button.Pressed, "#btn-key-copy")
    def on_copy(self) -> None:
        try:
            self.app._copy_text(self._key)  # type: ignore[attr-defined]
        except Exception:
            pass
    @on(Button.Pressed, "#btn-key-close")
    def on_close(self) -> None:
        self.dismiss(None)

class KeyEditScreen(ModalScreen):
    DEFAULT_CSS = """
    KeyEditScreen { align: center middle; }
    #key-edit-container { width: 60; height: auto; background: $surface; border: thick $primary; padding: 1 2; }
    #key-edit-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #key-edit-status { height: auto; margin: 1 0; }
    """
    def __init__(self, client, rec, callback, **kw):
        super().__init__(**kw)
        self._client = client
        self._rec = rec
        self._cb = callback
    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Input, Button, Checkbox
        rec = self._rec or {}
        with Vertical(id="key-edit-container"):
            yield Label(f"Edit Key — {rec.get('name','')}", id="key-edit-title")
            yield Input(value=rec.get("name",""), placeholder="Name", id="key-edit-name")
            yield Checkbox(value=bool(rec.get("isActive", True)), label="Active", id="key-edit-active")
            yield Static("", id="key-edit-status")
            with Horizontal():
                yield Button("Save", id="btn-key-edit-save", variant="primary")
                yield Button("Cancel", id="btn-key-edit-cancel", variant="default")
    @on(Button.Pressed, "#btn-key-edit-save")
    def on_save(self) -> None:
        try:
            name = self.query_one("#key-edit-name", Input).value.strip()
            is_active = self.query_one("#key-edit-active", Checkbox).value
            if not name:
                self.query_one("#key-edit-status", Static).update("[red]Name is required[/]")
                return
            import asyncio as _aio
            async def _do():
                try:
                    await _aio.to_thread(self._client.update_key, self._rec["id"], {"name": name, "isActive": is_active})
                    self.app.notify("Saved", timeout=2)
                    self.dismiss(True)
                    self._cb(True)
                except Exception as e:
                    self.query_one("#key-edit-status", Static).update(f"[red]{e}[/]")
            _aio.create_task(_do())
        except Exception as e:
            try:
                self.query_one("#key-edit-status", Static).update(f"[red]{e}[/]")
            except Exception:
                pass
    @on(Button.Pressed, "#btn-key-edit-cancel")
    def on_cancel(self) -> None:
        self.dismiss(False)
        self._cb(False)
