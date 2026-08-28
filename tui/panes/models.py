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

class ModelsPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._data: List[Dict[str, Any]] = []
        self._filtered: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("Models — Available Models (GET /api/models & /v1/models)", id="models-title")
        yield Horizontal(
            Button("Refresh", id="btn-models-refresh", variant="primary"),
            Input(placeholder="Filter model...", id="input-models-filter"),
        )
        yield DataTable(id="table-models", cursor_type="row", zebra_stripes=True)
        yield Static("", id="models-detail")
        yield Horizontal(Button("Copy Detail", id="btn-models-copy", variant="default"))

    def on_mount(self) -> None:
        table = self.query_one("#table-models", DataTable)
        table.add_columns("Model", "Provider", "Alias", "Caps")
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        table = self.query_one("#table-models", DataTable)
        table.clear()
        self._data = []
        try:
            data = await asyncio.to_thread(self.client.list_models)
            # /api/models returns {models: [...]}
            models = data.get("models", []) if isinstance(data, dict) else data
            self._data = models
            for m in models[:500]:
                caps = m.get("caps", {})
                cap_str = ",".join(k for k, v in caps.items() if v) if isinstance(caps, dict) else str(caps)[:20]
                table.add_row(
                    m.get("model", m.get("id", "—"))[:30],
                    m.get("provider", "—")[:16],
                    m.get("alias", "—")[:20],
                    cap_str[:24],
                )
            self._filtered = list(self._data)
            w = self.query_one("#models-detail", Static)
            txt = f"{len(models)} models"
            w.update(f"[dim]{txt}[/]")
            _store_plain(w, txt)
        except Exception as e:
            self._filtered = list(self._data)
            w = self.query_one("#models-detail", Static)
            w.update(f"[red]{e}[/]")
            _store_plain(w, str(e))

    @on(Button.Pressed, "#btn-models-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    @on(Button.Pressed, "#btn-models-copy")
    def on_copy(self) -> None:
        try:
            self._filtered = list(self._data)
            w = self.query_one("#models-detail", Static)
            plain = getattr(w, "_plain_text", "") or ""
            if plain:
                self.app._copy_text(plain)  # type: ignore[attr-defined]
            else:
                self.app.notify("Nothing to copy — select a row first", severity="warning")  # type: ignore[attr-defined]
        except Exception:
            pass

    @on(Input.Changed, "#input-models-filter")
    def on_filter(self, event: Input.Changed) -> None:
        q = event.value.lower().strip()
        table = self.query_one("#table-models", DataTable)
        table.clear()
        for m in self._data:
            hay = f"{m.get('model','')} {m.get('provider','')} {m.get('alias','')}".lower()
            if q and q not in hay:
                continue
            caps = m.get("caps", {})
            cap_str = ",".join(k for k, v in caps.items() if v) if isinstance(caps, dict) else str(caps)[:20]
            table.add_row(
                m.get("model", m.get("id", "—"))[:30],
                m.get("provider", "—")[:16],
                m.get("alias", "—")[:20],
                cap_str[:24],
            )
