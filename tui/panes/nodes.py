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

class NodesPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._data: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("Provider Nodes — Endpoints (GET /api/provider-nodes)", id="nodes-title")
        yield Horizontal(
            Button("Refresh", id="btn-nodes-refresh", variant="primary"),
            Button("Add Node", id="btn-nodes-add", variant="success"),
            Input(placeholder="Filter...", id="input-nodes-filter"),
        )
        yield DataTable(id="table-nodes", cursor_type="row", zebra_stripes=True)
        yield Static("", id="nodes-detail")
        yield Horizontal(
            Button("Copy Detail", id="btn-nodes-copy", variant="default"),
            Button("Edit", id="btn-nodes-edit", variant="default"),
            Button("Edit UID", id="btn-nodes-edit-uid", variant="default"),
            Button("Delete", id="btn-nodes-delete", variant="error"),
        )

    def on_mount(self) -> None:
        table = self.query_one("#table-nodes", DataTable)
        table.add_columns("Name", "Prefix", "Type", "API Type", "Base URL", "ID")
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        table = self.query_one("#table-nodes", DataTable)
        table.clear()
        self._data = []
        try:
            data = await asyncio.to_thread(self.client.list_nodes)
            self._data = data
            for n in data:
                table.add_row(
                    n.get("name", "—")[:20],
                    n.get("prefix", "—"),
                    n.get("type", "—"),
                    n.get("apiType", n.get("api_type", "—")),
                    n.get("baseUrl", n.get("base_url", "—"))[:40],
                    n.get("id", "")[:12],
                )
            w = self.query_one("#nodes-detail", Static)
            txt = f"{len(data)} nodes"
            w.update(f"[dim]{txt}[/]")
            _store_plain(w, txt)
        except Exception as e:
            w = self.query_one("#nodes-detail", Static)
            w.update(f"[red]{e}[/]")
            _store_plain(w, str(e))

    @on(Button.Pressed, "#btn-nodes-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    @on(Input.Changed, "#input-nodes-filter")
    def on_filter(self, event: Input.Changed) -> None:
        q = event.value.lower().strip()
        table = self.query_one("#table-nodes", DataTable)
        table.clear()
        for n in self._data:
            hay = f"{n.get('name','')} {n.get('prefix','')} {n.get('id','')} {n.get('baseUrl','')}".lower()
            if q and q not in hay:
                continue
            table.add_row(
                n.get("name", "—")[:20],
                n.get("prefix", "—"),
                n.get("type", "—"),
                n.get("apiType", n.get("api_type", "—")),
                n.get("baseUrl", n.get("base_url", "—"))[:40],
                n.get("id", "")[:12],
            )

    def _selected_node(self) -> Optional[Dict[str, Any]]:
        try:
            table = self.query_one("#table-nodes", DataTable)
            if table.cursor_row is None or table.cursor_row < 0:
                return None
            row = table.get_row_at(table.cursor_row)
            short_id = row[-1]
            return next((n for n in self._data if n.get("id","").startswith(short_id) or short_id in n.get("id","")), None)
        except Exception:
            return None

    @on(DataTable.RowSelected, "#table-nodes")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = event.cursor_row
            table = self.query_one("#table-nodes", DataTable)
            row = table.get_row_at(idx)
            short_id = row[-1]
            rec = next((n for n in self._data if n.get("id","").startswith(short_id) or short_id in n.get("id","")), None)
            if rec:
                txt = f"{rec.get('name')}  prefix={rec.get('prefix')}  id={rec.get('id')}\n{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}"
                w = self.query_one("#nodes-detail", Static)
                w.update(f"[bold]{rec.get('name')}[/]  prefix={rec.get('prefix')}  id={rec.get('id')}\n[dim]{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}[/]")
                _store_plain(w, txt)
                self._selected_id = rec.get("id", "")
        except Exception:
            pass

    @on(Button.Pressed, "#btn-nodes-add")
    def on_add(self) -> None:
        from tui.screens.nodes import NodeEditScreen
        self.app.push_screen(NodeEditScreen(self.client, None, self._on_node_saved))

    @on(Button.Pressed, "#btn-nodes-edit")
    def on_edit(self) -> None:
        from tui.screens.nodes import NodeEditScreen
        rec = self._selected_node()
        if not rec:
            self.app.notify("Select a node first", severity="warning")
            return
        self.app.push_screen(NodeEditScreen(self.client, rec, self._on_node_saved))

    @on(Button.Pressed, "#btn-nodes-edit-uid")
    def on_edit_uid(self) -> None:
        from tui.screens.nodes import NodeUidEditScreen
        rec = self._selected_node()
        if not rec:
            self.app.notify("Select a node first", severity="warning")
            return
        self.app.push_screen(NodeUidEditScreen(self.client, rec, self._on_node_saved))

    @on(Button.Pressed, "#btn-nodes-delete")
    def on_delete(self) -> None:
        rec = self._selected_node()
        if not rec:
            self.app.notify("Select a node first", severity="warning")
            return
        from tui.screens.confirm import ConfirmScreen
        self.app.push_screen(ConfirmScreen(f"Delete node '{rec.get('name')}' ({rec.get('id')})?", lambda ok: self._do_delete(ok, rec)))

    def _do_delete(self, ok: bool, rec: Dict[str, Any]) -> None:
        if not ok:
            return
        nid = rec.get("id", "")
        try:
            import asyncio as _aio
            async def _del():
                try:
                    await _aio.to_thread(self.client.delete_node, nid)
                    self.app.notify(f"Deleted {nid}", timeout=2)
                    self.refresh_data()
                except Exception as e:
                    self.app.notify(f"Delete failed: {e}", severity="error", timeout=4)
            _aio.create_task(_del())
        except Exception as e:
            self.notify(f"Delete failed: {e}", severity="error")

    def _on_node_saved(self, ok: bool) -> None:
        if ok:
            self.refresh_data()
