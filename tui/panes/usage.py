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

class UsagePane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client

    def compose(self) -> ComposeResult:
        yield Label("Usage — Stats & History", id="usage-title")
        yield Horizontal(
            Button("Refresh", id="btn-usage-refresh", variant="primary"),
            Select([("7d", "7d"), ("24h", "24h"), ("30d", "30d"), ("today", "today"), ("all", "all")], value="7d", id="select-usage-period"),
        )
        yield Static("", id="usage-body")
        yield DataTable(id="table-usage-history", cursor_type="row", zebra_stripes=True)
        yield Static("", id="usage-detail")
        yield Horizontal(Button("Copy Detail", id="btn-usage-copy", variant="default"))

    def on_mount(self) -> None:
        table = self.query_one("#table-usage-history", DataTable)
        table.add_columns("Time", "Model", "Provider", "Tokens", "Cost")
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        period = "7d"
        try:
            sel = self.query_one("#select-usage-period", Select)
            period = sel.value or "7d"
        except Exception:
            pass
        body = self.query_one("#usage-body", Static)
        table = self.query_one("#table-usage-history", DataTable)
        table.clear()
        body.update("Loading...")
        try:
            stats = await asyncio.to_thread(self.client.get_usage_stats, period)
            txt = f"Period: {period}  {json.dumps(stats, indent=2, ensure_ascii=False)[:2000]}"
            body.update(f"[bold]Period:[/] {period}  [dim]{json.dumps(stats, indent=2, ensure_ascii=False)[:2000]}[/]")
            _store_plain(body, txt)
        except Exception as e:
            body.update(f"[red]Stats error: {e}[/]")
            _store_plain(body, f"Stats error: {e}")
        try:
            hist = await asyncio.to_thread(self.client.get_usage_history, 50)
            items = hist.get("history", hist.get("items", hist.get("data", []))) if isinstance(hist, dict) else hist
            if isinstance(items, list):
                for h in items[:50]:
                    table.add_row(
                        fmt_time(h.get("createdAt", h.get("timestamp", h.get("time", "")))),
                        h.get("model", "—")[:24],
                        h.get("provider", "—")[:16],
                        str(h.get("totalTokens", h.get("tokens", "—"))),
                        str(h.get("cost", "—")),
                    )
                self.query_one("#usage-detail", Static).update(f"[dim]{len(items)} records[/]")
        except Exception as e:
            self.query_one("#usage-detail", Static).update(f"[red]History error: {e}[/]")

    @on(Button.Pressed, "#btn-usage-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    @on(Button.Pressed, "#btn-usage-copy")
    def on_copy(self) -> None:
        try:
            w = self.query_one("#usage-detail", Static)
            plain = getattr(w, "_plain_text", "") or ""
            if plain:
                self.app._copy_text(plain)  # type: ignore[attr-defined]
            else:
                self.app.notify("Nothing to copy", severity="warning")  # type: ignore[attr-defined]
        except Exception:
            pass

    @on(Select.Changed, "#select-usage-period")
    def on_period_changed(self, event: Select.Changed) -> None:
        self.refresh_data()
