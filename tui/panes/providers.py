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

class ProvidersPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._data: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("Providers — Connections (GET /api/providers)", id="providers-title")
        yield Horizontal(
            Button("Refresh", id="btn-providers-refresh", variant="primary"),
            Button("Test Batch", id="btn-providers-test", variant="default"),
            Input(placeholder="Filter by name/provider...", id="input-providers-filter"),
        )
        yield DataTable(id="table-providers", cursor_type="row", zebra_stripes=True)
        yield Static("", id="providers-detail")
        yield Horizontal(
            Button("Copy Detail", id="btn-providers-copy", variant="default"),
            Button("Delete", id="btn-providers-delete", variant="error"),
        )

    def on_mount(self) -> None:
        table = self.query_one("#table-providers", DataTable)
        table.add_columns("Name", "Provider", "Priority", "Active", "Status", "ID")
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        table = self.query_one("#table-providers", DataTable)
        table.clear()
        self._data = []
        try:
            data = await asyncio.to_thread(self.client.list_providers)
            self._data = data
            for p in data:
                table.add_row(
                    p.get("name", "—")[:24],
                    p.get("provider", "—")[:32],
                    str(p.get("priority", "—")),
                    "✓" if p.get("isActive") else "✗",
                    p.get("testStatus", p.get("status", "—")),
                    p.get("id", "")[:8],
                )
            w = self.query_one("#providers-detail", Static)
            txt = f"{len(data)} connections"
            w.update(f"[dim]{txt}[/]")
            _store_plain(w, txt)
        except Exception as e:
            w = self.query_one("#providers-detail", Static)
            w.update(f"[red]{e}[/]")
            _store_plain(w, str(e))

    @on(Button.Pressed, "#btn-providers-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    @on(Button.Pressed, "#btn-providers-test")
    async def on_test(self) -> None:
        detail = self.query_one("#providers-detail", Static)
        detail.update("Testing...")
        try:
            res = await asyncio.to_thread(self.client.test_providers, "all")
            txt = json.dumps(res, indent=2)[:1500]
            detail.update(f"[green]Test:[/] {txt}")
            _store_plain(detail, txt)
        except Exception as e:
            detail.update(f"[red]{e}[/]")
            _store_plain(detail, str(e))

    @on(Input.Changed, "#input-providers-filter")
    def on_filter(self, event: Input.Changed) -> None:
        q = event.value.lower().strip()
        table = self.query_one("#table-providers", DataTable)
        table.clear()
        for p in self._data:
            hay = f"{p.get('name','')} {p.get('provider','')} {p.get('id','')}".lower()
            if q and q not in hay:
                continue
            table.add_row(
                p.get("name", "—")[:24],
                p.get("provider", "—")[:32],
                str(p.get("priority", "—")),
                "✓" if p.get("isActive") else "✗",
                p.get("testStatus", p.get("status", "—")),
                p.get("id", "")[:8],
            )

    def _selected_provider(self) -> Optional[Dict[str, Any]]:
        try:
            table = self.query_one("#table-providers", DataTable)
            if table.cursor_row is None or table.cursor_row < 0:
                return None
            row = table.get_row_at(table.cursor_row)
            short_id = row[-1]
            return next((p for p in self._data if p.get("id","").startswith(short_id)), None)
        except Exception:
            return None

    @on(DataTable.RowSelected, "#table-providers")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = event.cursor_row
            table = self.query_one("#table-providers", DataTable)
            row = table.get_row_at(idx)
            short_id = row[-1]
            rec = next((p for p in self._data if p.get("id","").startswith(short_id)), None)
            if rec:
                txt = f"{rec.get('name')}  provider={rec.get('provider')}  id={rec.get('id')}\n{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}"
                w = self.query_one("#providers-detail", Static)
                w.update(f"[bold]{rec.get('name')}[/]  provider={rec.get('provider')}  id={rec.get('id')}\n[dim]{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}[/]")
                _store_plain(w, txt)
        except Exception:
            pass

    @on(Button.Pressed, "#btn-providers-delete")
    def on_delete(self) -> None:
        rec = self._selected_provider()
        if not rec:
            self.app.notify("Select a provider first", severity="warning")
            return
        from tui.screens.confirm import ConfirmScreen
        self.app.push_screen(ConfirmScreen(f"Delete provider '{rec.get('name')}' ({rec.get('id')})?", lambda ok: self._do_delete(ok, rec)))

    def _do_delete(self, ok: bool, rec: Dict[str, Any]) -> None:
        if not ok:
            return
        pid = rec.get("id", "")
        import asyncio as _aio
        async def _del():
            try:
                await _aio.to_thread(self.client.delete_provider, pid)
                self.app.notify(f"Deleted {pid}", timeout=2)
                self.refresh_data()
            except Exception as e:
                self.app.notify(f"Delete failed: {e}", severity="error", timeout=4)
        _aio.create_task(_del())

    @on(Button.Pressed, "#btn-providers-copy")
    def on_copy(self) -> None:
        try:
            w = self.query_one("#providers-detail", Static)
            plain = getattr(w, "_plain_text", "") or ""
            if plain:
                self.app._copy_text(plain)  # type: ignore[attr-defined]
            else:
                self.app.notify("Nothing to copy — select a row first", severity="warning")  # type: ignore[attr-defined]
        except Exception:
            pass
