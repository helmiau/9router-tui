from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Label, Static, Select

from client import NinerouterClient
from tui.helpers import _store_plain, fmt_time, mask_key, status_style

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
                table.add_row(p.get("name","—")[:20], p.get("type","—"), p.get("proxyUrl","—")[:40], "yes" if p.get("isActive") else "no", p.get("id","")[:8])
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
