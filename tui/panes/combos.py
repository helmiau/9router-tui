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

class CombosPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._data: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("Combos — Fallback Chains (GET /api/combos)", id="combos-title")
        yield Horizontal(
            Button("Refresh", id="btn-combos-refresh", variant="primary"),
            Button("Add Combo", id="btn-combos-add", variant="success"),
        )
        yield DataTable(id="table-combos", cursor_type="row", zebra_stripes=True)
        yield Static("", id="combos-detail")
        yield Horizontal(
            Button("Copy Detail", id="btn-combos-copy", variant="default"),
            Button("Edit", id="btn-combos-edit", variant="default"),
            Button("Delete", id="btn-combos-delete", variant="error"),
        )

    def on_mount(self) -> None:
        table = self.query_one("#table-combos", DataTable)
        table.add_columns("Name", "Kind", "Models", "ID")
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        table = self.query_one("#table-combos", DataTable)
        table.clear()
        self._data = []
        try:
            data = await asyncio.to_thread(self.client.list_combos)
            self._data = data
            for c in data:
                models = c.get("models", [])
                table.add_row(
                    c.get("name", "—"),
                    c.get("kind", "—") or "—",
                    f"{len(models)} models" if models else "—",
                    c.get("id", "")[:8],
                )
            w = self.query_one("#combos-detail", Static)
            txt = f"{len(data)} combos"
            w.update(f"[dim]{txt}[/]")
            _store_plain(w, txt)
        except Exception as e:
            w = self.query_one("#combos-detail", Static)
            w.update(f"[red]{e}[/]")
            _store_plain(w, str(e))

    @on(Button.Pressed, "#btn-combos-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    @on(Button.Pressed, "#btn-combos-copy")
    def on_copy(self) -> None:
        try:
            w = self.query_one("#combos-detail", Static)
            plain = getattr(w, "_plain_text", "") or ""
            if plain:
                self.app._copy_text(plain)  # type: ignore[attr-defined]
            else:
                self.app.notify("Nothing to copy — select a row first", severity="warning")  # type: ignore[attr-defined]
        except Exception:
            pass

    def _selected_combo(self) -> Optional[Dict[str, Any]]:
        try:
            table = self.query_one("#table-combos", DataTable)
            if table.cursor_row is None or table.cursor_row < 0:
                return None
            return self._data[table.cursor_row] if 0 <= table.cursor_row < len(self._data) else None
        except Exception:
            return None

    @on(Button.Pressed, "#btn-combos-add")
    def on_add(self) -> None:
        from tui.screens.combos import ComboEditScreen
        self.app.push_screen(ComboEditScreen(self.client, None, self._on_combo_saved))

    @on(Button.Pressed, "#btn-combos-edit")
    def on_edit(self) -> None:
        from tui.screens.combos import ComboEditScreen
        rec = self._selected_combo()
        if not rec:
            self.app.notify("Select a combo first", severity="warning")
            return
        self.app.push_screen(ComboEditScreen(self.client, rec, self._on_combo_saved))

    @on(Button.Pressed, "#btn-combos-delete")
    def on_delete(self) -> None:
        rec = self._selected_combo()
        if not rec:
            self.app.notify("Select a combo first", severity="warning")
            return
        from tui.screens.confirm import ConfirmScreen
        self.app.push_screen(ConfirmScreen(f"Delete combo '{rec.get('name')}'?", lambda ok: self._do_delete(ok, rec)))

    def _do_delete(self, ok: bool, rec: Dict[str, Any]) -> None:
        if not ok:
            return
        cid = rec.get("id", "")
        import asyncio as _aio
        async def _del():
            try:
                await _aio.to_thread(self.client.delete_combo, cid)
                self.app.notify(f"Deleted {cid}", timeout=2)
                self.refresh_data()
            except Exception as e:
                self.app.notify(f"Delete failed: {e}", severity="error", timeout=4)
        _aio.create_task(_del())

    def _on_combo_saved(self, ok: bool) -> None:
        if ok:
            self.refresh_data()

    @on(DataTable.RowSelected, "#table-combos")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = event.cursor_row
            rec = self._data[idx] if 0 <= idx < len(self._data) else None
            if rec:
                models = rec.get("models", [])
                txt = f"{rec.get('name')}  kind={rec.get('kind','—')}  id={rec.get('id')}\n{json.dumps(models, indent=2, ensure_ascii=False)[:3000]}"
                w = self.query_one("#combos-detail", Static)
                w.update(f"[bold]{rec.get('name')}[/]  kind={rec.get('kind','—')}  id={rec.get('id')}\n[dim]{json.dumps(models, indent=2, ensure_ascii=False)[:3000]}[/]")
                _store_plain(w, txt)
        except Exception:
            pass
