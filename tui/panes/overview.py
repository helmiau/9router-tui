from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Label, Static

from client import NinerouterClient
from tui.helpers import _store_plain, fmt_time, mask_key, status_style

class OverviewPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client

    def compose(self) -> ComposeResult:
        yield Label("Overview — 9Router Health & Summary", id="overview-title")
        yield Static("", id="overview-body")
        yield Horizontal(
            Button("Refresh", id="btn-overview-refresh", variant="primary"),
            Button("Test All Providers", id="btn-test-all", variant="default"),
            Button("Copy", id="btn-overview-copy", variant="default"),
        )

    async def on_mount(self) -> None:
        await self.refresh_data()

    async def refresh_data(self) -> None:
        body = self.query_one("#overview-body", Static)
        body.update("Loading...")
        try:
            health = await asyncio.to_thread(self.client.health)
            settings = await asyncio.to_thread(self.client.get_settings)
            version = {}
            try:
                version = await asyncio.to_thread(self.client.get_version)
            except Exception:
                pass
            nodes = await asyncio.to_thread(self.client.list_nodes)
            providers = await asyncio.to_thread(self.client.list_providers)
            combos = await asyncio.to_thread(self.client.list_combos)

            ok = health.get("ok", False)
            ver = version.get("version", version.get("tag", "—")) if isinstance(version, dict) else str(version)
            active = sum(1 for p in providers if p.get("isActive"))
            total = len(providers)
            node_count = len(nodes)
            combo_count = len(combos)

            # providerStrategies summary
            strategies = settings.get("providerStrategies", {}) if isinstance(settings, dict) else {}

            lines = []
            lines.append(f"[bold]Health:[/] {'[green]OK[/]' if ok else '[red]FAIL[/]'}   [bold]Version:[/] {ver}   [bold]URL:[/] {self.client.base}")
            lines.append(f"[bold]Providers:[/] {active}/{total} active   [bold]Nodes:[/] {node_count}   [bold]Combos:[/] {combo_count}")
            lines.append(f"[bold]Require API Key:[/] {settings.get('requireApiKey', '—')}   [bold]Tunnel:[/] {settings.get('tunnelEnabled', '—')} {settings.get('tunnelUrl','')[:40]}")
            if strategies:
                lines.append(f"[bold]Strategies:[/] {len(strategies)} providers configured")
            lines.append("")
            lines.append("[dim]Press 'r' to refresh, 't' to test all providers[/]")

            plain = "\n".join(lines)
            body.update(plain)
            _store_plain(body, plain)
        except Exception as e:
            msg = str(e)
            if "401" in msg or "Unauthorized" in msg:
                err = f"Error: {e}\n[red]401 Unauthorized — check password in config.toml [server] or Settings → TUI Config[/]\n[dim]Try: Settings → TUI Config → set password, or press 's' to switch server[/]"
            else:
                err = f"Error: {e}\nCheck NINEROUTER_URL and NINEROUTER_KEY"
            body.update(f"[red]{err}[/]")
            _store_plain(body, err)

    @on(Button.Pressed, "#btn-overview-refresh")
    async def on_refresh(self) -> None:
        await self.refresh_data()

    @on(Button.Pressed, "#btn-test-all")
    async def on_test_all(self) -> None:
        body = self.query_one("#overview-body", Static)
        body.update("Testing all providers...")
        try:
            res = await asyncio.to_thread(self.client.test_providers, "all")
            txt = f"Test done:\n{json.dumps(res, indent=2, ensure_ascii=False)[:2000]}"
            body.update(f"[green]Test done:[/]\n{json.dumps(res, indent=2, ensure_ascii=False)[:2000]}")
            _store_plain(body, txt)
        except Exception as e:
            body.update(f"[red]Test failed: {e}[/]")
            _store_plain(body, f"Test failed: {e}")

    @on(Button.Pressed, "#btn-overview-copy")
    def on_copy(self) -> None:
        try:
            w = self.query_one("#overview-body", Static)
            plain = getattr(w, "_plain_text", "") or str(w.content) if hasattr(w, "content") else ""
            if plain:
                self.app._copy_text(plain)  # type: ignore[attr-defined]
            else:
                self.app.notify("Nothing to copy", severity="warning")  # type: ignore[attr-defined]
        except Exception:
            pass
