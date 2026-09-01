from __future__ import annotations

import asyncio
import json

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Label, Static

from client import NinerouterClient
from tui.helpers import _store_plain, fmt_time

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


if __name__ == "__main__":
    import os

    from client import load_config_from_env_and_file

    try:
        from _version import __version__ as APP_VERSION
    except ImportError:
        APP_VERSION = "1.0.0"

    from tui.app import NineRouterTUI

    import argparse

    parser = argparse.ArgumentParser(description=f"9Router Terminal Dashboard v{APP_VERSION} (standalone)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    parser.add_argument("--url", default=None, help="9Router base URL (default: NINEROUTER_URL or http://localhost:20128)")
    parser.add_argument("--api-key", default=None, help="API key (default: NINEROUTER_KEY)")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    args = parser.parse_args()

    cfg = load_config_from_env_and_file(args.config)
    if args.url:
        cfg.url = args.url
    if args.api_key:
        cfg.api_key = args.api_key

    # also allow env override
    if os.getenv("NINEROUTER_URL"):
        cfg.url = os.getenv("NINEROUTER_URL", cfg.url)
    if os.getenv("NINEROUTER_KEY"):
        cfg.api_key = os.getenv("NINEROUTER_KEY", cfg.api_key)

    client = NinerouterClient(cfg)
    app = NineRouterTUI(client)
    app.run()
