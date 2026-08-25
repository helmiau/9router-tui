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
        from textual.widgets import Label, Static, Input, Button, Checkbox, DataTable
        is_edit = self._rec is not None
        rec = self._rec or {}
        models_val = ", ".join(rec.get("models", [])) if rec.get("models") else ""
        # Fetch available models for selector
        available: list[str] = []
        try:
            import asyncio as _aio
            # Try to get models synchronously if client has them cached, else fetch
            data = self._client.list_models() if hasattr(self._client, "list_models") else {}
            models_data = data.get("models", []) if isinstance(data, dict) else data if isinstance(data, list) else []
            for m in models_data[:200]:
                mid = m.get("model", m.get("id", ""))
                if mid:
                    available.append(mid)
        except Exception:
            pass
        self._available_models = available
        self._selected_models = set(rec.get("models", []))
        with Vertical(id="combo-edit-container"):
            yield Label("Edit Combo" if is_edit else "Add Combo", id="combo-edit-title")
            with Vertical(id="combo-edit-fields"):
                yield Label("Name (a-z, 0-9, -, _, .)")
                yield Input(value=rec.get("name", ""), placeholder="e.g. my-combo", id="combo-name")
                yield Label("Kind (optional)")
                yield Input(value=rec.get("kind", "") or "", placeholder="kind", id="combo-kind")
                yield Label("Filter models")
                yield Input(placeholder="Filter (e.g. gpt, claude)...", id="combo-filter")
                yield Label("Available models (check to add)")
                yield DataTable(id="combo-models-table", cursor_type="row", zebra_stripes=True)
                yield Label("Selected models (comma-separated, also editable)")
                yield Input(value=models_val, placeholder="model1, model2, ...", id="combo-models")
            yield Static("", id="combo-edit-status")
            with Horizontal():
                yield Button("Save", id="btn-combo-save", variant="primary")
                yield Button("Cancel", id="btn-combo-cancel", variant="default")

    def on_mount(self) -> None:
        try:
            table = self.query_one("#combo-models-table", DataTable)
            table.add_columns("✓", "Model")
            self._refresh_models_table("")
        except Exception:
            pass

    def _refresh_models_table(self, q: str) -> None:
        try:
            table = self.query_one("#combo-models-table", DataTable)
            table.clear()
            q = q.lower().strip()
            for mid in self._available_models:
                if q and q not in mid.lower():
                    continue
                checked = "✓" if mid in self._selected_models else " "
                table.add_row(checked, mid)
        except Exception:
            pass

    @on(Input.Changed, "#combo-filter")
    def on_filter(self, event: Input.Changed) -> None:
        self._refresh_models_table(event.value)

    @on(DataTable.RowSelected, "#combo-models-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            table = self.query_one("#combo-models-table", DataTable)
            row = table.get_row_at(event.cursor_row)
            mid = row[1]
            if mid in self._selected_models:
                self._selected_models.remove(mid)
            else:
                self._selected_models.add(mid)
            # Update input
            self.query_one("#combo-models", Input).value = ", ".join(sorted(self._selected_models))
            self._refresh_models_table(self.query_one("#combo-filter", Input).value)
        except Exception:
            pass
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
