from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static, Select, TextArea

from client import NinerouterClient

class ServerPickerScreen(ModalScreen):
    """Interactive server picker shown when no config exists, or on 's'."""

    DEFAULT_CSS = """
    ServerPickerScreen { align: center middle; }
    #picker-container {
        width: 72;
        height: auto;
        max-height: 36;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #picker-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #picker-table { height: 10; min-height: 6; }
    #picker-detail { height: auto; max-height: 6; margin: 1 0; }
    #picker-inputs { height: auto; }
    #picker-inputs Input { margin: 1 0; }
    """

    def __init__(self, client, callback, **kw):
        super().__init__(**kw)
        self._client = client
        self._callback = callback
        self._servers = []
        self._selected = None

    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, DataTable, Static, Input, Button
        with Vertical(id="picker-container"):
            yield Label("Select 9Router Server — no config found, pick one or add custom", id="picker-title")
            yield DataTable(id="picker-table", cursor_type="row", zebra_stripes=True)
            yield Static("", id="picker-detail")
            with Vertical(id="picker-inputs"):
                yield Label("Custom server (leave empty to use selected):", id="picker-custom-label")
                yield Input(placeholder="https://your-9router.example.com  or  http://localhost:20128", id="input-custom-url")
                yield Input(placeholder="API key (optional, if requireApiKey=true)", id="input-custom-key", password=False)
                yield Input(placeholder="Name (optional, e.g. My VPS)", id="input-custom-name")
                yield Label("Remote Docker via SSH (optional — for VPS):", id="picker-ssh-label")
                yield Input(placeholder="SSH host (e.g. 1.2.3.4 or vps.example.com)", id="input-ssh-host")
                yield Input(placeholder="SSH user (default: root)", id="input-ssh-user")
                yield Input(placeholder="SSH key path (e.g. ~/.ssh/id_rsa)", id="input-ssh-key")
                yield Input(placeholder="Compose path (e.g. /opt/9router/docker-compose.yml)", id="input-compose-path")
            with Horizontal():
                yield Button("OK", id="btn-picker-ok", variant="primary")
                yield Button("Connect", id="btn-picker-connect", variant="primary")
                yield Button("Save & Connect", id="btn-picker-save", variant="default")
                yield Button("Cancel", id="btn-picker-cancel", variant="error")

    def on_mount(self) -> None:
        from textual.widgets import DataTable
        table = self.query_one("#picker-table", DataTable)
        table.add_columns("Name", "URL", "Status", "Latency")
        self._load_servers()
        self._refresh_table()

    def _load_servers(self) -> None:
        from client import _load_servers_from_file, DEFAULT_SERVERS, ServerProfile
        saved = _load_servers_from_file()
        seen = set()
        merged = []
        for s in saved + DEFAULT_SERVERS:
            if s.url not in seen:
                seen.add(s.url)
                merged.append(s)
        # auto-detected local servers
        try:
            from client import auto_detect_servers
            for det in auto_detect_servers(timeout=2):
                url = det["url"]
                if url not in seen:
                    seen.add(url)
                    merged.append(ServerProfile(name=det["name"], url=url, description="Auto-detected (reachable)"))
        except Exception:
            pass
        cur = self._client.base if hasattr(self._client, "base") else ""
        if cur and cur not in seen:
            merged.insert(0, ServerProfile(name="Current", url=cur, api_key=self._client.cfg.api_key, description="From current config"))
        self._servers = merged

    @work(exclusive=True)
    async def _refresh_table(self) -> None:
        from textual.widgets import DataTable, Static
        import asyncio
        from client import probe_server
        table = self.query_one("#picker-table", DataTable)
        table.clear()
        detail = self.query_one("#picker-detail", Static)
        detail.update("[dim]Probing servers...[/]")
        results = []
        for s in self._servers:
            res = await asyncio.to_thread(probe_server, s.url, s.api_key, 4)
            results.append(res)
        table.clear()
        for s, res in zip(self._servers, results):
            status = "[green]OK[/]" if res["ok"] else f"[red]{res['error'] or res['status']}[/]"
            latency = f"{res['latency_ms']}ms" if res["latency_ms"] is not None else "—"
            try:
                from client import detect_host_info
                hi = detect_host_info(s.url)
                kind_label = hi['label']
                if s.ssh_host:
                    kind_label += " +SSH"
                status = f"{status} {kind_label}"
            except Exception:
                pass
            table.add_row(s.name, s.url[:32], status, latency)
        detail.update("[dim]↑/↓ to select, Enter to connect, or fill Custom below. 's' anytime to switch.[/]")
        if self._servers:
            self._selected = self._servers[0]

    @on(DataTable.RowSelected, "#picker-table")
    def on_row_selected(self, event) -> None:
        try:
            idx = event.cursor_row
            if 0 <= idx < len(self._servers):
                self._selected = self._servers[idx]
                s = self._selected
                try:
                    from client import detect_host_info
                    hi = detect_host_info(s.url)
                    kind_info = f" [{hi['label']}: {hi['kind']}]"
                except Exception:
                    kind_info = ""
                self.query_one("#picker-detail", Static).update(f"[bold]{s.name}[/]  {s.url}{kind_info}  [dim]{s.description}[/]")
        except Exception:
            pass

    @on(Button.Pressed, "#btn-picker-ok")
    def on_ok(self) -> None:
        profile = self._resolve_profile()
        if profile:
            self.dismiss(profile)
            self._callback(profile)

    @on(Button.Pressed, "#btn-picker-connect")
    def on_connect(self) -> None:
        profile = self._resolve_profile()
        if profile:
            self.dismiss(profile)
            self._callback(profile)

    @on(Button.Pressed, "#btn-picker-save")
    def on_save(self) -> None:
        profile = self._resolve_profile()
        if profile:
            from client import _load_servers_from_file, save_servers_to_file
            servers = _load_servers_from_file()
            found = False
            for i, s in enumerate(servers):
                if s.url == profile.url:
                    servers[i] = profile
                    found = True
                    break
            if not found:
                servers.append(profile)
            if not servers:
                servers = [profile]
            try:
                save_servers_to_file(servers)
            except Exception:
                pass
            self.dismiss(profile)
            self._callback(profile)

    @on(Button.Pressed, "#btn-picker-cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)

    def _resolve_profile(self):
        from textual.widgets import Input
        from client import ServerProfile
        try:
            custom_url = self.query_one("#input-custom-url", Input).value.strip()
            custom_key = self.query_one("#input-custom-key", Input).value.strip()
            custom_name = self.query_one("#input-custom-name", Input).value.strip()
            ssh_host = self.query_one("#input-ssh-host", Input).value.strip()
            ssh_user = self.query_one("#input-ssh-user", Input).value.strip()
            ssh_key = self.query_one("#input-ssh-key", Input).value.strip()
            compose_path = self.query_one("#input-compose-path", Input).value.strip()
        except Exception:
            custom_url = custom_key = custom_name = ssh_host = ssh_user = ssh_key = compose_path = ""
        if custom_url:
            if not custom_url.startswith("http"):
                custom_url = "http://" + custom_url
            custom_url = custom_url.rstrip("/")
            return ServerProfile(name=custom_name or custom_url, url=custom_url, api_key=custom_key, timeout=15, description="Custom", ssh_host=ssh_host, ssh_user=ssh_user or "root", ssh_key=ssh_key, compose_path=compose_path)
        if self._selected:
            # if SSH fields filled, merge into selected
            if ssh_host:
                from dataclasses import replace
                try:
                    return replace(self._selected, ssh_host=ssh_host, ssh_user=ssh_user or "root", ssh_key=ssh_key, compose_path=compose_path)
                except Exception:
                    pass
            return self._selected
        if self._servers:
            return self._servers[0]
        return None


# ── Settings Edit Screens (multi-config) ──
