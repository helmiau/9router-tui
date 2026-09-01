"""Provider Connections pane — Providers > Manage API Key sub-tab."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Label, Static

from client import NinerouterClient
from tui.helpers import _store_plain, mask_key


class ProviderConnectionsPane(Static):
    """Manage API Key — provider nodes (connections) with strategy, proxy pool, round-robin, sticky."""

    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._data: List[Dict[str, Any]] = []
        self._filtered: List[Dict[str, Any]] = []
        self._proxy_pools: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("Manage API Key — Provider Nodes (connections)", id="prov-conn-title")
        yield Horizontal(
            Button("Refresh", id="btn-pc-refresh", variant="primary"),
            Button("Add Connection", id="btn-pc-add", variant="success"),
            Input(placeholder="Filter...", id="input-pc-filter"),
        )
        yield DataTable(id="table-pc", cursor_type="row", zebra_stripes=True)
        yield Static("", id="prov-conn-detail")
        yield Horizontal(
            Button("Copy Detail", id="btn-pc-copy", variant="default"),
            Button("Test Connection", id="btn-pc-test", variant="default"),
            Button("Edit Strategy", id="btn-pc-edit-strat", variant="default"),
            Button("Delete", id="btn-pc-delete", variant="error"),
        )

    def on_mount(self) -> None:
        table = self.query_one("#table-pc", DataTable)
        table.add_columns("Name", "Provider", "Type", "Priority", "Active", "Round-Robin", "Sticky Limit", "Proxy Pool", "ID")
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        table = self.query_one("#table-pc", DataTable)
        table.clear()
        self._data = []
        try:
            # Fetch providers (connections) and proxy pools
            providers = await asyncio.to_thread(self.client.list_providers)
            pools = await asyncio.to_thread(self.client.list_proxy_pools)
            self._data = providers
            self._proxy_pools = pools
            for p in providers:
                strat = p.get("strategy", {}) or {}
                table.add_row(
                    p.get("name", "—")[:24],
                    p.get("provider", "—")[:24],
                    p.get("type", "—")[:16],
                    str(p.get("priority", "—")),
                    "yes" if p.get("isActive") else "no",
                    "yes" if strat.get("roundRobin") else "no",
                    str(strat.get("stickyRoundRobinLimit", "—")),
                    strat.get("proxyPool", "—")[:16],
                    p.get("id", "")[:8],
                )
            self._filtered = list(self._data)
            w = self.query_one("#prov-conn-detail", Static)
            txt = f"{len(providers)} connections"
            w.update(f"[dim]{txt}[/]")
            _store_plain(w, txt)
        except Exception as e:
            self._filtered = list(self._data)
            w = self.query_one("#prov-conn-detail", Static)
            w.update(f"[red]{e}[/]")
            _store_plain(w, str(e))

    def _render_detail(self, rec: Dict[str, Any]) -> None:
        try:
            strat = rec.get("strategy", {}) or {}
            txt = (
                f"{rec.get('name')}  provider={rec.get('provider')}  id={rec.get('id')}\n"
                f"type={rec.get('type')}  priority={rec.get('priority')}  active={rec.get('isActive')}\n"
                f"strategy: roundRobin={strat.get('roundRobin')} stickyLimit={strat.get('stickyRoundRobinLimit')} "
                f"proxyPool={strat.get('proxyPool')} fallbackStrategy={strat.get('fallbackStrategy')}\n"
                f"{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}"
            )
            w = self.query_one("#prov-conn-detail", Static)
            w.update(
                f"[bold]{rec.get('name')}[/]  provider={rec.get('provider')}  id={rec.get('id')}\n"
                f"[dim]{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}[/]"
            )
            _store_plain(w, txt)
        except Exception:
            pass

    @on(Button.Pressed, "#btn-pc-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    @on(Input.Changed, "#input-pc-filter")
    def on_filter(self, event: Input.Changed) -> None:
        q = event.value.lower().strip()
        table = self.query_one("#table-pc", DataTable)
        table.clear()
        for p in self._data:
            hay = f"{p.get('name','')} {p.get('provider','')} {p.get('id','')}".lower()
            if q and q not in hay:
                continue
            strat = p.get("strategy", {}) or {}
            table.add_row(
                p.get("name", "—")[:24],
                p.get("provider", "—")[:24],
                p.get("type", "—")[:16],
                str(p.get("priority", "—")),
                "yes" if p.get("isActive") else "no",
                "yes" if strat.get("roundRobin") else "no",
                str(strat.get("stickyRoundRobinLimit", "—")),
                strat.get("proxyPool", "—")[:16],
                p.get("id", "")[:8],
            )

    @on(DataTable.RowSelected, "#table-pc")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = event.cursor_row
            data = self._filtered if self._filtered else self._data
            rec = data[idx] if 0 <= idx < len(data) else None
            if rec:
                self._render_detail(rec)
        except Exception:
            pass

    def _selected(self) -> Optional[Dict[str, Any]]:
        try:
            table = self.query_one("#table-pc", DataTable)
            if table.cursor_row is None or table.cursor_row < 0:
                return None
            data = self._filtered if self._filtered else self._data
            if 0 <= table.cursor_row < len(data):
                return data[table.cursor_row]
            row = table.get_row_at(table.cursor_row)
            short_id = row[-1]
            return next((p for p in self._data if p.get("id", "").startswith(short_id)), None)
        except Exception:
            return None

    @on(Button.Pressed, "#btn-pc-copy")
    def on_copy(self) -> None:
        try:
            w = self.query_one("#prov-conn-detail", Static)
            text = getattr(w, "_plain_text", "") or ""
            if text:
                self.app._copy_text(text)
        except Exception:
            pass

    @on(Button.Pressed, "#btn-pc-test")
    def on_test(self) -> None:
        rec = self._selected()
        if not rec:
            self.app.notify("Select a connection first", severity="warning")
            return
        detail = self.query_one("#prov-conn-detail", Static)
        detail.update(f"Testing {rec.get('name')}...")
        import asyncio as _aio

        async def _do():
            try:
                res = await _aio.to_thread(self.client.test_providers, "provider", rec.get("id"))
                txt = json.dumps(res, indent=2, ensure_ascii=False)[:2000]
                detail.update(f"[green]Test {rec.get('name')}:[/] {txt}")
                _store_plain(detail, txt)
            except Exception as e:
                detail.update(f"[red]Test failed: {e}[/]")
                _store_plain(detail, str(e))

        _aio.create_task(_do())

    @on(Button.Pressed, "#btn-pc-edit-strat")
    def on_edit_strategy(self) -> None:
        rec = self._selected()
        if not rec:
            self.app.notify("Select a connection first", severity="warning")
            return
        from tui.screens.provider_strategy import ProviderStrategyScreen
        self.app.push_screen(ProviderStrategyScreen(self.client, rec, self._proxy_pools, self._on_strategy_saved))

    def _on_strategy_saved(self, provider_id: str, strategy: Dict[str, Any]) -> None:
        import asyncio as _aio

        async def _do():
            try:
                await _aio.to_thread(self.client.update_provider, provider_id, {"strategy": strategy})
                self.app.notify("Strategy saved", timeout=2)
                self.refresh_data()
            except Exception as e:
                self.app.notify(f"Save failed: {e}", severity="error", timeout=4)

        _aio.create_task(_do())

    @on(Button.Pressed, "#btn-pc-delete")
    def on_delete(self) -> None:
        rec = self._selected()
        if not rec:
            self.app.notify("Select a connection first", severity="warning")
            return
        from tui.screens.confirm import ConfirmScreen
        self.app.push_screen(ConfirmScreen(f"Delete connection '{rec.get('name')}' ({rec.get('id')})?", lambda ok: self._do_delete(ok, rec)))

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

    @on(Button.Pressed, "#btn-pc-add")
    def on_add(self) -> None:
        from tui.screens.provider_connection_edit import ProviderConnectionEditScreen
        self.app.push_screen(ProviderConnectionEditScreen(self.client, None, self._on_connection_saved))

    def _on_connection_saved(self, provider_id: str, payload: Optional[Dict[str, Any]] = None) -> None:
        import asyncio as _aio

        async def _do():
            try:
                if payload and payload.get("id"):
                    await _aio.to_thread(self.client.update_provider, payload["id"], payload)
                    self.app.notify("Connection updated", timeout=2)
                else:
                    await _aio.to_thread(self.client.create_provider, payload or {})
                    self.app.notify("Connection created", timeout=2)
                self.refresh_data()
            except Exception as e:
                self.app.notify(f"Save failed: {e}", severity="error", timeout=4)

        _aio.create_task(_do())