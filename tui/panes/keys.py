from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Label, Static

from client import NinerouterClient
from tui.helpers import _store_plain, fmt_time, mask_key

class KeysPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._data: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("API Keys — Dashboard Keys (GET /api/keys)", id="keys-title")
        yield Horizontal(
            Button("Refresh", id="btn-keys-refresh", variant="primary"),
            Button("Create Key", id="btn-keys-create", variant="success"),
        )
        yield DataTable(id="table-keys", cursor_type="row", zebra_stripes=True)
        yield Static("", id="keys-detail")
        yield Horizontal(
            Button("Copy Detail", id="btn-keys-copy", variant="default"),
            Button("Edit", id="btn-keys-edit", variant="default"),
            Button("Toggle Active", id="btn-keys-toggle", variant="default"),
            Button("Delete", id="btn-keys-delete", variant="error"),
        )

    def on_mount(self) -> None:
        table = self.query_one("#table-keys", DataTable)
        table.add_columns("Name", "Key", "Active", "Machine ID", "Created", "ID")
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        table = self.query_one("#table-keys", DataTable)
        table.clear()
        self._data = []
        try:
            data = await asyncio.to_thread(self.client.list_keys)
            self._data = data
            for k in data:
                table.add_row(
                    k.get("name", "—"),
                    mask_key(k.get("key", "")),
                    "yes" if k.get("isActive", True) else "no",
                    k.get("machineId", k.get("machine_id", "—"))[:12],
                    fmt_time(k.get("createdAt", k.get("created_at", ""))),
                    k.get("id", "")[:8],
                )
            w = self.query_one("#keys-detail", Static)
            txt = f"{len(data)} keys"
            w.update(f"[dim]{txt}[/]")
            _store_plain(w, txt)
        except Exception as e:
            w = self.query_one("#keys-detail", Static)
            w.update(f"[red]{e}[/]")
            _store_plain(w, str(e))

    @on(Button.Pressed, "#btn-keys-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    def _selected_key(self) -> Optional[Dict[str, Any]]:
        try:
            table = self.query_one("#table-keys", DataTable)
            if table.cursor_row is None or table.cursor_row < 0:
                return None
            row = table.get_row_at(table.cursor_row)
            short_id = row[-1]
            return next((k for k in self._data if k.get("id","").startswith(short_id)), None)
        except Exception:
            return None

    @on(Button.Pressed, "#btn-keys-create")
    def on_create(self) -> None:
        from tui.screens.keys import KeyCreateScreen
        self.app.push_screen(KeyCreateScreen(self.client, self._on_key_created))

    def _on_key_created(self, ok: bool) -> None:
        if ok:
            self.refresh_data()

    @on(Button.Pressed, "#btn-keys-delete")
    def on_delete(self) -> None:
        rec = self._selected_key()
        if not rec:
            self.app.notify("Select a key first", severity="warning")
            return
        from tui.screens.confirm import ConfirmScreen
        self.app.push_screen(ConfirmScreen(f"Delete key '{rec.get('name')}'?", lambda ok: self._do_delete(ok, rec)))

    def _do_delete(self, ok: bool, rec: Dict[str, Any]) -> None:
        if not ok:
            return
        kid = rec.get("id", "")
        import asyncio as _aio
        async def _del():
            try:
                await _aio.to_thread(self.client.delete_key, kid)
                self.app.notify(f"Deleted {kid}", timeout=2)
                self.refresh_data()
            except Exception as e:
                self.app.notify(f"Delete failed: {e}", severity="error", timeout=4)
        _aio.create_task(_del())

    @on(Button.Pressed, "#btn-keys-edit")
    def on_edit(self) -> None:
        rec = self._selected_key()
        if not rec:
            self.app.notify("Select a key first", severity="warning")
            return
        from tui.screens.keys import KeyEditScreen
        self.app.push_screen(KeyEditScreen(self.client, rec, lambda ok: self.refresh_data() if ok else None))

    @on(Button.Pressed, "#btn-keys-toggle")
    def on_toggle(self) -> None:
        rec = self._selected_key()
        if not rec:
            self.app.notify("Select a key first", severity="warning")
            return
        new_val = not rec.get("isActive", True)
        import asyncio as _aio
        async def _do():
            try:
                await _aio.to_thread(self.client.update_key, rec["id"], {"isActive": new_val})
                self.app.notify(f"{'Enabled' if new_val else 'Disabled'} {rec.get('name')}", timeout=2)
                self.refresh_data()
            except Exception as e:
                self.app.notify(f"Toggle failed: {e}", severity="error", timeout=4)
        _aio.create_task(_do())

    @on(Button.Pressed, "#btn-keys-copy")
    def on_copy(self) -> None:
        try:
            w = self.query_one("#keys-detail", Static)
            plain = getattr(w, "_plain_text", "") or ""
            if plain:
                self.app._copy_text(plain)  # type: ignore[attr-defined]
            else:
                self.app.notify("Nothing to copy — select a row first", severity="warning")  # type: ignore[attr-defined]
        except Exception:
            pass

    @on(DataTable.RowSelected, "#table-keys")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = event.cursor_row
            table = self.query_one("#table-keys", DataTable)
            row = table.get_row_at(idx)
            short_id = row[-1]
            rec = next((k for k in self._data if k.get("id","").startswith(short_id)), None)
            if rec:
                txt = f"{rec.get('name')}  key={mask_key(rec.get('key',''))}  id={rec.get('id')}\n{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}"
                w = self.query_one("#keys-detail", Static)
                w.update(f"[bold]{rec.get('name')}[/]  key={mask_key(rec.get('key',''))}  id={rec.get('id')}\n[dim]{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}[/]")
                _store_plain(w, txt)
        except Exception:
            pass
