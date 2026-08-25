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


class ProxyPoolsPane(Static):
    def __init__(self, client, **kw):
        super().__init__(**kw)
        self.client = client
        self._data = []
    def compose(self) -> ComposeResult:
        yield Label("Proxy Pools — GET /api/proxy-pools", id="pools-title")
        yield Horizontal(Button("Refresh", id="btn-pools-refresh", variant="primary"))
        yield DataTable(id="table-pools", cursor_type="row", zebra_stripes=True)
        yield Static("", id="pools-detail")
        yield Horizontal(Button("Copy Detail", id="btn-pools-copy", variant="default"))
    def on_mount(self) -> None:
        table = self.query_one("#table-pools", DataTable)
        table.add_columns("Name", "Type", "Proxy URL", "Active", "ID")
        self.refresh_data()
    @work(exclusive=True)
    async def refresh_data(self) -> None:
        table = self.query_one("#table-pools", DataTable)
        table.clear()
        self._data = []
        try:
            data = await asyncio.to_thread(self.client.list_proxy_pools)
            self._data = data if isinstance(data, list) else []
            for p in self._data:
                table.add_row(p.get("name","—")[:20], p.get("type","—"), p.get("proxyUrl","—")[:40], "✓" if p.get("isActive") else "✗", p.get("id","")[:8])
            w = self.query_one("#pools-detail", Static)
            txt = f"{len(self._data)} pools"
            w.update(f"[dim]{txt}[/]")
            _store_plain(w, txt)
        except Exception as e:
            w = self.query_one("#pools-detail", Static)
            w.update(f"[red]{e}[/]")
            _store_plain(w, str(e))
    @on(Button.Pressed, "#btn-pools-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()
    @on(Button.Pressed, "#btn-pools-copy")
    def on_copy(self) -> None:
        try:
            w = self.query_one("#pools-detail", Static)
            plain = getattr(w, "_plain_text", "") or ""
            if plain:
                self.app._copy_text(plain)  # type: ignore[attr-defined]
            else:
                self.app.notify("Nothing to copy — select a row first", severity="warning")  # type: ignore[attr-defined]
        except Exception:
            pass
    @on(DataTable.RowSelected, "#table-pools")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = event.cursor_row
            rec = self._data[idx] if 0 <= idx < len(self._data) else None
            if rec:
                txt = f"{rec.get('name')}  type={rec.get('type')}  id={rec.get('id')}\n{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}"
                w = self.query_one("#pools-detail", Static)
                w.update(f"[bold]{rec.get('name')}[/]  type={rec.get('type')}  id={rec.get('id')}\n[dim]{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}[/]")
                _store_plain(w, txt)
        except Exception:
            pass


class LogsPane(Static):
    def __init__(self, client, **kw):
        super().__init__(**kw)
        self.client = client
        self._data = []
    def compose(self) -> ComposeResult:
        yield Label("Request Logs — GET /api/usage/logs", id="logs-title")
        yield Horizontal(Button("Refresh", id="btn-logs-refresh", variant="primary"))
        yield DataTable(id="table-logs", cursor_type="row", zebra_stripes=True)
        yield Static("", id="logs-detail")
        yield Horizontal(Button("Copy Detail", id="btn-logs-copy", variant="default"))
    def on_mount(self) -> None:
        table = self.query_one("#table-logs", DataTable)
        table.add_columns("Time", "Model", "Provider", "Status", "ID")
        self.refresh_data()
    @work(exclusive=True)
    async def refresh_data(self) -> None:
        table = self.query_one("#table-logs", DataTable)
        table.clear()
        self._data = []
        try:
            data = await asyncio.to_thread(self.client.get_request_logs, 100)
            items = data if isinstance(data, list) else data.get("logs", data.get("data", [])) if isinstance(data, dict) else []
            self._data = items if isinstance(items, list) else []
            for r in self._data[:100]:
                table.add_row(fmt_time(r.get("createdAt", r.get("timestamp",""))), r.get("model","—")[:20], r.get("provider","—")[:16], str(r.get("status","—")), r.get("id","")[:8])
            w = self.query_one("#logs-detail", Static)
            txt = f"{len(self._data)} logs"
            w.update(f"[dim]{txt}[/]")
            _store_plain(w, txt)
        except Exception as e:
            w = self.query_one("#logs-detail", Static)
            w.update(f"[red]{e}[/]")
            _store_plain(w, str(e))
    @on(Button.Pressed, "#btn-logs-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()
    @on(Button.Pressed, "#btn-logs-copy")
    def on_copy(self) -> None:
        try:
            w = self.query_one("#logs-detail", Static)
            plain = getattr(w, "_plain_text", "") or ""
            if plain:
                self.app._copy_text(plain)  # type: ignore[attr-defined]
            else:
                self.app.notify("Nothing to copy — select a row first", severity="warning")  # type: ignore[attr-defined]
        except Exception:
            pass
    @on(DataTable.RowSelected, "#table-logs")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = event.cursor_row
            rec = self._data[idx] if 0 <= idx < len(self._data) else None
            if rec:
                txt = f"{rec.get('id')}  {rec.get('model')}  {rec.get('provider')}\n{json.dumps(rec, indent=2, ensure_ascii=False)[:3000]}"
                w = self.query_one("#logs-detail", Static)
                w.update(f"[bold]{rec.get('id')}[/]  {rec.get('model')}  {rec.get('provider')}\n[dim]{json.dumps(rec, indent=2, ensure_ascii=False)[:3000]}[/]")
                _store_plain(w, txt)
        except Exception:
            pass
