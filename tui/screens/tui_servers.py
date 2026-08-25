"""Manage servers — list, add, edit, delete, set default."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from textual import on
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static, Select


class TuiServersScreen(ModalScreen):
    DEFAULT_CSS = """
    TuiServersScreen { align: center middle; }
    #servers-container { width: 82; height: 36; background: $surface; border: thick $primary; padding: 1 2; }
    #servers-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #servers-table { height: 14; }
    #servers-detail { height: auto; margin: 1 0; }
    #servers-status { height: auto; margin: 1 0; }
    """

    def __init__(self, callback, **kw):
        super().__init__(**kw)
        self._cb = callback
        self._servers: List[Any] = []
        self._selected_idx: Optional[int] = None

    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Button, DataTable
        with Vertical(id="servers-container"):
            yield Label("Manage Servers — servers.json / config.toml [[servers]]", id="servers-title")
            yield DataTable(id="servers-table", cursor_type="row", zebra_stripes=True)
            yield Static("", id="servers-detail")
            with Horizontal():
                yield Button("Add", id="btn-srv-add", variant="success")
                yield Button("Edit", id="btn-srv-edit", variant="default")
                yield Button("Delete", id="btn-srv-delete", variant="error")
                yield Button("↑", id="btn-srv-up", variant="default")
                yield Button("↓", id="btn-srv-down", variant="default")
                yield Button("Set Default", id="btn-srv-default", variant="default")
            yield Static("", id="servers-status")
            with Horizontal():
                yield Button("Save & Close", id="btn-srv-save", variant="primary")
                yield Button("Cancel", id="btn-srv-cancel", variant="default")

    def on_mount(self) -> None:
        table = self.query_one("#servers-table", DataTable)
        table.add_columns("Name", "URL", "Description")
        self._load()

    def _load(self) -> None:
        from client import _load_servers_from_file
        self._servers = _load_servers_from_file()
        table = self.query_one("#servers-table", DataTable)
        table.clear()
        for s in self._servers:
            table.add_row(s.name, s.url[:40], s.description[:30])
        self.query_one("#servers-detail", Static).update(f"[dim]{len(self._servers)} server(s) — select a row to edit/delete[/]")

    @on(DataTable.RowSelected, "#servers-table")
    def on_row_selected(self, event) -> None:
        try:
            idx = event.cursor_row
            if 0 <= idx < len(self._servers):
                self._selected_idx = idx
                s = self._servers[idx]
                self.query_one("#servers-detail", Static).update(f"[bold]{s.name}[/] {s.url}  [dim]{s.description}[/]  api_key={'***' if s.api_key else '—'}")
        except Exception:
            pass

    @on(Button.Pressed, "#btn-srv-add")
    def on_add(self) -> None:
        self.app.push_screen(ServerEditScreen(None, self._on_edit_done))

    @on(Button.Pressed, "#btn-srv-edit")
    def on_edit(self) -> None:
        if self._selected_idx is None or not (0 <= self._selected_idx < len(self._servers)):
            self.query_one("#servers-status", Static).update("[yellow]Select a server first[/]")
            return
        self.app.push_screen(ServerEditScreen(self._servers[self._selected_idx], self._on_edit_done))

    def _on_edit_done(self, result) -> None:
        if result is None:
            return
        # result is (is_new, profile) or None
        if isinstance(result, tuple) and len(result) == 2:
            is_new, profile = result
            if is_new:
                self._servers.append(profile)
            else:
                if self._selected_idx is not None and 0 <= self._selected_idx < len(self._servers):
                    self._servers[self._selected_idx] = profile
            self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#servers-table", DataTable)
        table.clear()
        for s in self._servers:
            table.add_row(s.name, s.url[:40], s.description[:30])

    @on(Button.Pressed, "#btn-srv-delete")
    def on_delete(self) -> None:
        if self._selected_idx is None or not (0 <= self._selected_idx < len(self._servers)):
            self.query_one("#servers-status", Static).update("[yellow]Select a server first[/]")
            return
        s = self._servers[self._selected_idx]
        # Confirm
        from tui.screens.confirm import ConfirmScreen
        def _do(ok: bool):
            if ok:
                self._servers.pop(self._selected_idx)
                self._selected_idx = None
                self._refresh_table()
                self.query_one("#servers-detail", Static).update("[dim]Deleted[/]")
        self.app.push_screen(ConfirmScreen(f"Delete server '{s.name}'?", _do))

    @on(Button.Pressed, "#btn-srv-up")
    def on_up(self) -> None:
        if self._selected_idx is None or self._selected_idx <= 0:
            return
        idx = self._selected_idx
        self._servers[idx], self._servers[idx-1] = self._servers[idx-1], self._servers[idx]
        self._selected_idx = idx - 1
        self._refresh_table()
        self._save_order()

    @on(Button.Pressed, "#btn-srv-down")
    def on_down(self) -> None:
        if self._selected_idx is None or self._selected_idx >= len(self._servers) - 1:
            return
        idx = self._selected_idx
        self._servers[idx], self._servers[idx+1] = self._servers[idx+1], self._servers[idx]
        self._selected_idx = idx + 1
        self._refresh_table()
        self._save_order()

    def _save_order(self) -> None:
        try:
            from client import save_servers_to_file
            save_servers_to_file(self._servers)
            self.query_one("#servers-status", Static).update("[green]Order saved[/]")
        except Exception as e:
            self.query_one("#servers-status", Static).update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-srv-default")
    def on_default(self) -> None:
        if self._selected_idx is None or not (0 <= self._selected_idx < len(self._servers)):
            self.query_one("#servers-status", Static).update("[yellow]Select a server first[/]")
            return
        s = self._servers.pop(self._selected_idx)
        self._servers.insert(0, s)
        self._selected_idx = 0
        self._refresh_table()
        self._save_order()
        self.query_one("#servers-status", Static).update(f"[green]Default: {s.name}[/]")

    @on(Button.Pressed, "#btn-srv-save")
    def on_save(self) -> None:
        try:
            from client import save_servers_to_file
            save_servers_to_file(self._servers)
            self.dismiss(True)
            self._cb(True)
        except Exception as e:
            self.query_one("#servers-status", Static).update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-srv-cancel")
    def on_cancel(self) -> None:
        self.dismiss(False)
        self._cb(False)


class ServerEditScreen(ModalScreen):
    DEFAULT_CSS = """
    ServerEditScreen { align: center middle; }
    #srv-edit-container { width: 76; height: auto; max-height: 36; background: $surface; border: thick $primary; padding: 1 2; }
    #srv-edit-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #srv-edit-status { height: auto; margin: 1 0; }
    """

    def __init__(self, rec, callback, **kw):
        super().__init__(**kw)
        self._rec = rec
        self._cb = callback

    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Input, Button
        rec = self._rec
        is_edit = rec is not None
        with Vertical(id="srv-edit-container"):
            yield Label("Edit Server" if is_edit else "Add Server", id="srv-edit-title")
            yield Input(value=rec.name if rec else "", placeholder="Name (e.g. Local)", id="srv-name")
            yield Input(value=rec.url if rec else "", placeholder="URL (e.g. http://localhost:20128)", id="srv-url")
            yield Input(value=rec.api_key if rec else "", placeholder="API key (optional)", id="srv-api-key")
            yield Input(value=getattr(rec, "password", "") if rec else "", placeholder="Dashboard password (optional)", id="srv-password", password=True)
            yield Input(value=rec.description if rec else "", placeholder="Description", id="srv-desc")
            yield Input(value=getattr(rec, "ssh_host", "") if rec else "", placeholder="SSH host (optional, for VPS)", id="srv-ssh-host")
            yield Input(value=getattr(rec, "ssh_user", "") if rec else "", placeholder="SSH user (default root)", id="srv-ssh-user")
            yield Input(value=getattr(rec, "ssh_key", "") if rec else "", placeholder="SSH key path", id="srv-ssh-key")
            yield Input(value=getattr(rec, "compose_path", "") if rec else "", placeholder="Compose path", id="srv-compose")
            yield Static("", id="srv-edit-status")
            with Horizontal():
                yield Button("Save", id="btn-srv-edit-save", variant="primary")
                yield Button("Cancel", id="btn-srv-edit-cancel", variant="default")

    @on(Button.Pressed, "#btn-srv-edit-save")
    def on_save(self) -> None:
        try:
            from client import ServerProfile
            name = self.query_one("#srv-name", Input).value.strip()
            url = self.query_one("#srv-url", Input).value.strip()
            api_key = self.query_one("#srv-api-key", Input).value.strip()
            password = self.query_one("#srv-password", Input).value.strip()
            desc = self.query_one("#srv-desc", Input).value.strip()
            ssh_host = self.query_one("#srv-ssh-host", Input).value.strip()
            ssh_user = self.query_one("#srv-ssh-user", Input).value.strip()
            ssh_key = self.query_one("#srv-ssh-key", Input).value.strip()
            compose = self.query_one("#srv-compose", Input).value.strip()
            if not name:
                self.query_one("#srv-edit-status", Static).update("[red]Name is required[/]")
                return
            if not url:
                self.query_one("#srv-edit-status", Static).update("[red]URL is required[/]")
                return
            if not url.startswith("http"):
                url = "http://" + url
            url = url.rstrip("/")
            profile = ServerProfile(name=name, url=url, api_key=api_key, description=desc, ssh_host=ssh_host, ssh_user=ssh_user or "root", ssh_key=ssh_key, compose_path=compose)
            # Store password in api_key or as attribute if ServerProfile supports it
            if password:
                try:
                    profile.password = password  # type: ignore
                except Exception:
                    pass
            is_new = self._rec is None
            self.dismiss((is_new, profile))
            self._cb((is_new, profile))
        except Exception as e:
            try:
                self.query_one("#srv-edit-status", Static).update(f"[red]{e}[/]")
            except Exception:
                pass

    @on(Button.Pressed, "#btn-srv-edit-cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
        self._cb(None)
