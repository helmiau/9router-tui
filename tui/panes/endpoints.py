"""Endpoints pane — Endpoint and Keys > Endpoints sub-tab."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, DataTable, Label, Static, Switch

from client import NinerouterClient
from tui.helpers import _store_plain, status_style


class EndpointsPane(Static):
    """Endpoint + tunnel / tailscale / RTK / headroom / proxy toggles."""

    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._settings: Dict[str, Any] = {}
        self._tunnel: Dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        yield Label("Endpoints — tunnel, tailscale, dashboard access, RTK, headroom, proxy", id="endpoints-title")
        yield Horizontal(
            Button("Refresh", id="btn-endpoints-refresh", variant="primary"),
            Button("Copy", id="btn-endpoints-copy", variant="default"),
        )
        yield Static("", id="endpoints-body")
        yield Static("[dim]Toggles send PATCH /api/settings. Tunnel/Tailscale actions call dedicated endpoints.[/]", id="endpoints-hint")

    def on_mount(self) -> None:
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        body = self.query_one("#endpoints-body", Static)
        body.update("Loading...")
        try:
            settings = await asyncio.to_thread(self.client.get_settings)
            tunnel = await asyncio.to_thread(self.client.tunnel_status)
            self._settings = settings if isinstance(settings, dict) else {}
            self._tunnel = tunnel if isinstance(tunnel, dict) else {}
            self._render()
        except Exception as e:
            body.update(f"[red]{e}[/]")
            _store_plain(body, str(e))

    def _render(self) -> None:
        try:
            body = self.query_one("#endpoints-body", Static)
            s = self._settings
            t = self._tunnel
            url = self.client.base
            lines = [
                f"[bold]Endpoint[/]: [cyan]{url}[/]",
                "",
                "[bold]Tunnel[/]",
                f"  enabled: [cyan]{s.get('tunnelEnabled')}[/]",
                f"  url: [cyan]{s.get('tunnelUrl')}[/]",
                f"  status: [cyan]{t.get('tunnel', {}).get('status')}[/]",
                f"  publicUrl: [cyan]{t.get('tunnel', {}).get('publicUrl')}[/]",
                "",
                "[bold]Tailscale[/]",
                f"  installed: [cyan]{t.get('tailscale', {}).get('installed')}[/]",
                f"  loggedIn: [cyan]{t.get('tailscale', {}).get('loggedIn')}[/]",
                f"  status: [cyan]{t.get('tailscale', {}).get('status')}[/]",
                "",
                "[bold]Dashboard Access[/]",
                f"  requireApiKey: [cyan]{s.get('requireApiKey')}[/]",
                f"  tunnelDashboardAccess: [cyan]{s.get('tunnelDashboardAccess')}[/]",
                f"  requireLogin: [cyan]{s.get('requireLogin')}[/]",
                "",
                "[bold]RTK / Headroom[/]",
                f"  rtkEnabled: [cyan]{s.get('rtkEnabled')}[/]",
                f"  headroomEnabled: [cyan]{s.get('headroomEnabled')}[/]",
                f"  headroomUrl: [cyan]{s.get('headroomUrl')}[/]",
                "",
                "[bold]Outbound Proxy[/]",
                f"  outboundProxyEnabled: [cyan]{s.get('outboundProxyEnabled')}[/]",
                f"  outboundProxyUrl: [cyan]{s.get('outboundProxyUrl')}[/]",
                f"  outboundNoProxy: [cyan]{s.get('outboundNoProxy')}[/]",
            ]
            body.update("\n".join(lines))
            _store_plain(body, "\n".join(lines))
        except Exception:
            pass

    # ── actions ──
    def action_copy(self) -> None:
        try:
            text = self._detail_plain()
            if text:
                self.app._copy_text(text)
        except Exception:
            pass

    def _detail_plain(self) -> str:
        try:
            body = self.query_one("#endpoints-body", Static)
            return getattr(body, "_plain_text", "") or ""
        except Exception:
            return ""

    @on(Button.Pressed, "#btn-endpoints-refresh")
    def _refresh(self) -> None:
        self.refresh_data()

    @on(Button.Pressed, "#btn-endpoints-copy")
    def _copy(self) -> None:
        self.action_copy()
