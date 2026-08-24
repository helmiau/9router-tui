"""
9Router TUI — Terminal Dashboard (Textual)
Standalone, no dependency on omnexsync.

Run:
  pip install -r requirements.txt
  python app.py
  # or
  textual run app.py

Env:
  NINEROUTER_URL=http://localhost:20128
  NINEROUTER_KEY=sk-...

Features:
  - No config? Shows interactive server picker (Local / Tunnel / Custom)
  - Switch server anytime: press 's' or click "Switch Server"
  - Servers saved to servers.json (or config.toml [[servers]])
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    Static,
    TabbedContent,
    TabPane,
    Select,
)
from textual.reactive import reactive
from textual import on, work

from client import (
    NinerouterClient,
    NinerouterConfig,
    ServerProfile,
    DEFAULT_SERVERS,
    load_config_from_env_and_file,
    has_any_config,
    _load_servers_from_file,
    save_servers_to_file,
    probe_server,
)


# ── helpers ──
def mask_key(k: str) -> str:
    if not k:
        return "—"
    if len(k) <= 12:
        return k[:4] + "****"
    return k[:8] + "****" + k[-4:]


def fmt_time(s: Optional[str]) -> str:
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s[:19]


def status_style(s: str) -> str:
    s = (s or "").lower()
    if s in ("active", "ok", "success"):
        return "green"
    if s in ("unavailable", "error", "failed"):
        return "red"
    if s in ("testing", "pending"):
        return "yellow"
    return "white"


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

            body.update("\n".join(lines))
        except Exception as e:
            body.update(f"[red]Error: {e}[/]\n[dim]Check NINEROUTER_URL and NINEROUTER_KEY[/]")

    @on(Button.Pressed, "#btn-overview-refresh")
    async def on_refresh(self) -> None:
        await self.refresh_data()

    @on(Button.Pressed, "#btn-test-all")
    async def on_test_all(self) -> None:
        body = self.query_one("#overview-body", Static)
        body.update("Testing all providers...")
        try:
            res = await asyncio.to_thread(self.client.test_providers, "all")
            body.update(f"[green]Test done:[/]\n{json.dumps(res, indent=2, ensure_ascii=False)[:2000]}")
        except Exception as e:
            body.update(f"[red]Test failed: {e}[/]")


class ProvidersPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._data: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("Providers — Connections (GET /api/providers)", id="providers-title")
        yield Horizontal(
            Button("Refresh", id="btn-providers-refresh", variant="primary"),
            Button("Test Batch", id="btn-providers-test", variant="default"),
            Input(placeholder="Filter by name/provider...", id="input-providers-filter"),
        )
        yield DataTable(id="table-providers", cursor_type="row", zebra_stripes=True)
        yield Static("", id="providers-detail")

    def on_mount(self) -> None:
        table = self.query_one("#table-providers", DataTable)
        table.add_columns("Name", "Provider", "Priority", "Active", "Status", "ID")
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        table = self.query_one("#table-providers", DataTable)
        table.clear()
        self._data = []
        try:
            data = await asyncio.to_thread(self.client.list_providers)
            self._data = data
            for p in data:
                table.add_row(
                    p.get("name", "—")[:24],
                    p.get("provider", "—")[:32],
                    str(p.get("priority", "—")),
                    "✓" if p.get("isActive") else "✗",
                    p.get("testStatus", p.get("status", "—")),
                    p.get("id", "")[:8],
                )
            self.query_one("#providers-detail", Static).update(f"[dim]{len(data)} connections[/]")
        except Exception as e:
            self.query_one("#providers-detail", Static).update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-providers-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    @on(Button.Pressed, "#btn-providers-test")
    async def on_test(self) -> None:
        detail = self.query_one("#providers-detail", Static)
        detail.update("Testing...")
        try:
            res = await asyncio.to_thread(self.client.test_providers, "all")
            detail.update(f"[green]Test:[/] {json.dumps(res, indent=2)[:1500]}")
        except Exception as e:
            detail.update(f"[red]{e}[/]")

    @on(Input.Changed, "#input-providers-filter")
    def on_filter(self, event: Input.Changed) -> None:
        q = event.value.lower().strip()
        table = self.query_one("#table-providers", DataTable)
        table.clear()
        for p in self._data:
            hay = f"{p.get('name','')} {p.get('provider','')} {p.get('id','')}".lower()
            if q and q not in hay:
                continue
            table.add_row(
                p.get("name", "—")[:24],
                p.get("provider", "—")[:32],
                str(p.get("priority", "—")),
                "✓" if p.get("isActive") else "✗",
                p.get("testStatus", p.get("status", "—")),
                p.get("id", "")[:8],
            )

    @on(DataTable.RowSelected, "#table-providers")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = event.cursor_row
            # filtered view — find by matching row
            table = self.query_one("#table-providers", DataTable)
            row = table.get_row_at(idx)
            short_id = row[-1]
            # find full record
            rec = next((p for p in self._data if p.get("id","").startswith(short_id)), None)
            if rec:
                detail = self.query_one("#providers-detail", Static)
                detail.update(f"[bold]{rec.get('name')}[/]  provider={rec.get('provider')}  id={rec.get('id')}\n[dim]{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}[/]")
        except Exception:
            pass


class NodesPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._data: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("Provider Nodes — Endpoints (GET /api/provider-nodes)", id="nodes-title")
        yield Horizontal(
            Button("Refresh", id="btn-nodes-refresh", variant="primary"),
            Input(placeholder="Filter...", id="input-nodes-filter"),
        )
        yield DataTable(id="table-nodes", cursor_type="row", zebra_stripes=True)
        yield Static("", id="nodes-detail")

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
            self.query_one("#nodes-detail", Static).update(f"[dim]{len(data)} nodes[/]")
        except Exception as e:
            self.query_one("#nodes-detail", Static).update(f"[red]{e}[/]")

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

    @on(DataTable.RowSelected, "#table-nodes")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = event.cursor_row
            table = self.query_one("#table-nodes", DataTable)
            row = table.get_row_at(idx)
            short_id = row[-1]
            rec = next((n for n in self._data if n.get("id","").startswith(short_id) or short_id in n.get("id","")), None)
            if rec:
                self.query_one("#nodes-detail", Static).update(f"[bold]{rec.get('name')}[/]  prefix={rec.get('prefix')}  id={rec.get('id')}\n[dim]{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}[/]")
        except Exception:
            pass


class CombosPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._data: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("Combos — Fallback Chains (GET /api/combos)", id="combos-title")
        yield Horizontal(Button("Refresh", id="btn-combos-refresh", variant="primary"))
        yield DataTable(id="table-combos", cursor_type="row", zebra_stripes=True)
        yield Static("", id="combos-detail")

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
            self.query_one("#combos-detail", Static).update(f"[dim]{len(data)} combos[/]")
        except Exception as e:
            self.query_one("#combos-detail", Static).update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-combos-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    @on(DataTable.RowSelected, "#table-combos")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = event.cursor_row
            rec = self._data[idx] if 0 <= idx < len(self._data) else None
            if rec:
                models = rec.get("models", [])
                self.query_one("#combos-detail", Static).update(
                    f"[bold]{rec.get('name')}[/]  kind={rec.get('kind','—')}  id={rec.get('id')}\n[dim]{json.dumps(models, indent=2, ensure_ascii=False)[:3000]}[/]"
                )
        except Exception:
            pass


class ModelsPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._data: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("Models — Available Models (GET /api/models & /v1/models)", id="models-title")
        yield Horizontal(
            Button("Refresh", id="btn-models-refresh", variant="primary"),
            Input(placeholder="Filter model...", id="input-models-filter"),
        )
        yield DataTable(id="table-models", cursor_type="row", zebra_stripes=True)
        yield Static("", id="models-detail")

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
            self.query_one("#models-detail", Static).update(f"[dim]{len(models)} models[/]")
        except Exception as e:
            self.query_one("#models-detail", Static).update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-models-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

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


class KeysPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._data: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("API Keys — Dashboard Keys (GET /api/keys)", id="keys-title")
        yield Horizontal(Button("Refresh", id="btn-keys-refresh", variant="primary"))
        yield DataTable(id="table-keys", cursor_type="row", zebra_stripes=True)
        yield Static("", id="keys-detail")

    def on_mount(self) -> None:
        table = self.query_one("#table-keys", DataTable)
        table.add_columns("Name", "Key", "Machine ID", "Created", "ID")
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
                    k.get("machineId", k.get("machine_id", "—"))[:12],
                    fmt_time(k.get("createdAt", k.get("created_at", ""))),
                    k.get("id", "")[:8],
                )
            self.query_one("#keys-detail", Static).update(f"[dim]{len(data)} keys[/]")
        except Exception as e:
            self.query_one("#keys-detail", Static).update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-keys-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()


class UsagePane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client

    def compose(self) -> ComposeResult:
        yield Label("Usage — Stats & History", id="usage-title")
        yield Horizontal(
            Button("Refresh", id="btn-usage-refresh", variant="primary"),
            Select([("7d", "7d"), ("24h", "24h"), ("30d", "30d"), ("today", "today"), ("all", "all")], value="7d", id="select-usage-period"),
        )
        yield Static("", id="usage-body")
        yield DataTable(id="table-usage-history", cursor_type="row", zebra_stripes=True)
        yield Static("", id="usage-detail")

    def on_mount(self) -> None:
        table = self.query_one("#table-usage-history", DataTable)
        table.add_columns("Time", "Model", "Provider", "Tokens", "Cost")
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        period = "7d"
        try:
            sel = self.query_one("#select-usage-period", Select)
            period = sel.value or "7d"
        except Exception:
            pass
        body = self.query_one("#usage-body", Static)
        table = self.query_one("#table-usage-history", DataTable)
        table.clear()
        body.update("Loading...")
        try:
            stats = await asyncio.to_thread(self.client.get_usage_stats, period)
            body.update(f"[bold]Period:[/] {period}  [dim]{json.dumps(stats, indent=2, ensure_ascii=False)[:2000]}[/]")
        except Exception as e:
            body.update(f"[red]Stats error: {e}[/]")
        try:
            hist = await asyncio.to_thread(self.client.get_usage_history, 50)
            items = hist.get("history", hist.get("items", hist.get("data", []))) if isinstance(hist, dict) else hist
            if isinstance(items, list):
                for h in items[:50]:
                    table.add_row(
                        fmt_time(h.get("createdAt", h.get("timestamp", h.get("time", "")))),
                        h.get("model", "—")[:24],
                        h.get("provider", "—")[:16],
                        str(h.get("totalTokens", h.get("tokens", "—"))),
                        str(h.get("cost", "—")),
                    )
                self.query_one("#usage-detail", Static).update(f"[dim]{len(items)} records[/]")
        except Exception as e:
            self.query_one("#usage-detail", Static).update(f"[red]History error: {e}[/]")

    @on(Button.Pressed, "#btn-usage-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    @on(Select.Changed, "#select-usage-period")
    def on_period_changed(self, event: Select.Changed) -> None:
        self.refresh_data()


class SettingsPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client

    def compose(self) -> ComposeResult:
        yield Label("Settings — 9Router Config (GET/PATCH /api/settings)", id="settings-title")
        yield Horizontal(Button("Refresh", id="btn-settings-refresh", variant="primary"))
        yield Static("", id="settings-body")

    def on_mount(self) -> None:
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        body = self.query_one("#settings-body", Static)
        body.update("Loading...")
        try:
            data = await asyncio.to_thread(self.client.get_settings)
            body.update(f"[dim]{json.dumps(data, indent=2, ensure_ascii=False)[:6000]}[/]")
        except Exception as e:
            body.update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-settings-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()


class UpdatePane(Static):
    def __init__(self, client, **kw):
        super().__init__(**kw)
        self.client = client
        self._version_info = None
        self._docker_info = None

    def compose(self) -> ComposeResult:
        yield Label("Update & Docker — 9Router Version & Container Management", id="update-title")
        yield Horizontal(
            Button("Check Version", id="btn-update-check", variant="primary"),
            Button("Update (dry-run)", id="btn-update-dry", variant="default"),
            Button("Update Now", id="btn-update-now", variant="success"),
            Select([("auto", "auto"), ("npm", "npm"), ("source", "source"), ("docker", "docker")], value="auto", id="select-update-method"),
        )
        yield Static("", id="update-version-body")
        yield Horizontal(
            Button("Docker Status", id="btn-docker-status", variant="primary"),
            Button("Docker Logs", id="btn-docker-logs", variant="default"),
            Button("Docker Pull", id="btn-docker-pull", variant="default"),
            Button("Docker Restart", id="btn-docker-restart", variant="default"),
            Button("Docker Update", id="btn-docker-update", variant="success"),
        )
        yield Static("", id="update-docker-body")
        yield Static("", id="update-log")

    def on_mount(self) -> None:
        self.refresh_version()

    def _get_profile(self):
        # find ServerProfile matching current client URL
        try:
            from client import _load_servers_from_file
            for s in _load_servers_from_file():
                if s.url.rstrip('/') == self.client.base.rstrip('/'):
                    return s
        except Exception:
            pass
        return None

    @work(exclusive=True)
    async def refresh_version(self) -> None:
        body = self.query_one("#update-version-body", Static)
        body.update("Checking version...")
        try:
            from updater import get_version_via_api, get_local_version, detect_host_info
            info = await asyncio.to_thread(get_version_via_api, self.client)
            self._version_info = info
            local = get_local_version()
            host_info = detect_host_info(self.client.base)
            kind = host_info["kind"]
            label = host_info["label"]
            profile = self._get_profile()
            is_remote_ssh = bool(profile and profile.ssh_host)
            # color by kind
            kind_color = {"local": "green", "private-ip": "cyan", "public-ip": "yellow", "domain": "yellow", "tunnel": "magenta"}.get(kind, "white")
            lines = []
            lines.append(f"[bold]Current:[/] {info.current}   [bold]Latest:[/] {info.latest}   [bold]Has Update:[/] {'[green]Yes[/]' if info.has_update else '[dim]No[/]'}")
            lines.append(f"[bold]Source:[/] {info.source}   [bold]Local pkg:[/] {local or '—'}")
            lines.append(f"[bold]URL:[/] {self.client.base}  [{kind_color}]({label}: {kind})[/]  host={host_info['host'] or '—'}")
            if profile and is_remote_ssh:
                lines.append(f"[bold]SSH:[/] {profile.ssh_target()}  [green](remote Docker via SSH)[/]  compose: {profile.compose_path or 'auto'}")
            elif profile:
                lines.append(f"[bold]Profile:[/] {profile.name} — {profile.description}")
            if info.error:
                lines.append(f"[red]Error: {info.error}[/]")
            if kind in ("public-ip", "domain") and not is_remote_ssh:
                lines.append("[yellow]Public VPS detected — add ssh_host to servers.json for remote Docker/update via SSH.[/]")
                lines.append("[dim]CLI: python cli.py --server VPS docker status  |  python cli.py --server VPS update[/]")
            elif kind == "tunnel":
                lines.append("[dim]Tunnel — remote, no Docker SSH. Use VPS SSH for Docker management.[/]")
            body.update("\n".join(lines))
        except Exception as e:
            body.update(f"[red]{e}[/]")

    @work(exclusive=True)
    async def refresh_docker(self) -> None:
        body = self.query_one("#update-docker-body", Static)
        body.update("Checking docker...")
        try:
            profile = self._get_profile()
            is_remote = bool(profile and profile.ssh_host)
            if is_remote:
                from updater import docker_status_remote
                info = await asyncio.to_thread(docker_status_remote, profile)
            else:
                from updater import docker_status
                info = await asyncio.to_thread(docker_status)
            self._docker_info = info
            if not info["available"]:
                body.update(f"[red]Docker not available: {info['error']}[/] {'[dim](remote)[/]' if is_remote else ''}")
                return
            lines = []
            prefix = "[dim](remote)[/] " if is_remote else ""
            lines.append(f"{prefix}[bold]Compose:[/] {info['compose'] or '—'}")
            if info["containers"]:
                for c in info["containers"]:
                    lines.append(f"  {c.get('name','—')}  {c.get('image','—')}  {c.get('status','—')}")
            else:
                lines.append("  [dim]No 9router containers found[/]")
            if info["images"]:
                lines.append(f"[bold]Images:[/] {', '.join(info['images'][:3])}")
            body.update("\n".join(lines))
        except Exception as e:
            body.update(f"[red]{e}[/]")

    def _get_method(self) -> str:
        try:
            sel = self.query_one("#select-update-method", Select)
            v = sel.value or "auto"
            if v == "auto":
                profile = self._get_profile()
                if profile and profile.ssh_host:
                    from updater import detect_install_method_remote
                    return detect_install_method_remote(profile)
                from updater import detect_install_method
                return detect_install_method()
            return v
        except Exception:
            return "npm"

    @on(Button.Pressed, "#btn-update-check")
    def on_check(self) -> None:
        self.refresh_version()

    @on(Button.Pressed, "#btn-update-dry")
    async def on_dry(self) -> None:
        log = self.query_one("#update-log", Static)
        method = self._get_method()
        log.update(f"[dim]Dry-run plan for {method}...[/]")
        try:
            from updater import build_update_plan
            plan = await asyncio.to_thread(build_update_plan, method, None)
            if isinstance(plan, tuple):
                plan = plan[0] if isinstance(plan[0], list) else []
            lines = [f"[bold]Method:[/] {method}  [dim](dry-run)[/]"]
            for cmd in plan:
                if isinstance(cmd, list):
                    lines.append(f"  $ {' '.join(cmd)}")
                elif isinstance(cmd, tuple):
                    lines.append(f"  $ {' '.join(cmd[0])}  (cwd={cmd[1]})")
            if not lines[1:]:
                lines.append("  [dim]No plan[/]")
            log.update("\n".join(lines))
        except Exception as e:
            log.update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-update-now")
    async def on_update_now(self) -> None:
        log = self.query_one("#update-log", Static)
        method = self._get_method()
        profile = self._get_profile()
        is_remote = bool(profile and profile.ssh_host)
        if is_remote:
            log.update(f"[yellow]Updating remote {profile.ssh_target()} via {method} (SSH)...[/]")
            try:
                from updater import run_update_remote
                steps = await asyncio.to_thread(run_update_remote, profile, method, False, None, None)
                lines = []
                for s in steps:
                    status = "[green]OK[/]" if s["rc"] == 0 else f"[red]FAIL rc={s['rc']}[/]"
                    lines.append(f"$ {s['cmd']}  {status}  [dim](remote)[/]")
                    if s["stdout"]:
                        lines.append(f"[dim]{s['stdout'][-800:]}[/]")
                    if s["stderr"]:
                        lines.append(f"[red]{s['stderr'][-800:]}[/]")
                    if s["rc"] != 0:
                        break
                else:
                    lines.append("[green]Remote update completed[/]")
                log.update("\n".join(lines))
                self.refresh_version()
            except Exception as e:
                log.update(f"[red]{e}[/]")
            return
        else:
            from updater import is_local_url
            if not is_local_url(self.client.base):
                log.update("[red]Remote server without SSH — cannot update from here. Add ssh_host to servers.json.[/]")
                return
            log.update(f"[yellow]Updating via {method}...[/]")
            try:
                from updater import run_update
                steps = await asyncio.to_thread(run_update, method, False, None, None)
                lines = []
                for s in steps:
                    status = "[green]OK[/]" if s["rc"] == 0 else f"[red]FAIL rc={s['rc']}[/]"
                    lines.append(f"$ {s['cmd']}  {status}")
                    if s["stdout"]:
                        lines.append(f"[dim]{s['stdout'][-800:]}[/]")
                    if s["stderr"]:
                        lines.append(f"[red]{s['stderr'][-800:]}[/]")
                    if s["rc"] != 0:
                        break
                else:
                    lines.append("[green]Update completed[/]")
                log.update("\n".join(lines))
                self.refresh_version()
            except Exception as e:
                log.update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-docker-status")
    def on_docker_status(self) -> None:
        self.refresh_docker()

    @on(Button.Pressed, "#btn-docker-logs")
    async def on_docker_logs(self) -> None:
        log = self.query_one("#update-log", Static)
        log.update("[dim]Fetching docker logs...[/]")
        try:
            profile = self._get_profile()
            is_remote = bool(profile and profile.ssh_host)
            if is_remote:
                from updater import docker_logs_remote
                rc, out, err = await asyncio.to_thread(docker_logs_remote, profile, "9router", 100)
            else:
                from updater import docker_logs
                rc, out, err = await asyncio.to_thread(docker_logs, "9router", 100)
            if rc != 0:
                log.update(f"[red]docker logs failed rc={rc}: {err[:800]}[/]")
            else:
                log.update(f"[dim]{out[-4000:] or 'No logs'}[/]")
        except Exception as e:
            log.update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-docker-pull")
    async def on_docker_pull(self) -> None:
        log = self.query_one("#update-log", Static)
        profile = self._get_profile()
        is_remote = bool(profile and profile and profile.ssh_host)
        log.update(f"[dim]docker pull decolua/9router:latest ...{' (remote)' if is_remote else ''}[/]")
        try:
            if is_remote:
                from updater import _run_remote
                rc, out, err = await asyncio.to_thread(_run_remote, profile, "docker pull decolua/9router:latest", 300)
            else:
                from updater import run_cmd
                rc, out, err = await asyncio.to_thread(run_cmd, ["docker", "pull", "decolua/9router:latest"], None, 300)
            status = "[green]OK[/]" if rc == 0 else f"[red]FAIL rc={rc}[/]"
            log.update(f"{status}\n[dim]{out[-2000:]}[/]\n[red]{err[-2000:]}[/]" if err else f"{status}\n[dim]{out[-2000:]}[/]")
        except Exception as e:
            log.update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-docker-restart")
    async def on_docker_restart(self) -> None:
        log = self.query_one("#update-log", Static)
        profile = self._get_profile()
        is_remote = bool(profile and profile.ssh_host)
        log.update(f"[dim]Restarting 9router...{' (remote)' if is_remote else ''}[/]")
        try:
            if is_remote:
                from updater import _run_remote
                compose = profile.compose_path
                if not compose:
                    rc_tmp, out_tmp, _ = await asyncio.to_thread(_run_remote, profile, "ls -1 docker-compose.yml 9router-master/docker-compose.yml 9router-master/9router-master/docker-compose.yml 2>/dev/null | head -1", 10)
                    if rc_tmp == 0 and out_tmp.strip():
                        compose = out_tmp.strip()
                if compose:
                    rc, out, err = await asyncio.to_thread(_run_remote, profile, f"docker compose -f {compose} restart 9router", 60)
                    if rc == 0:
                        log.update(f"[green]Restarted via compose (remote): 9router[/]\n[dim]{out[-800:]}[/]")
                        return
                rc, out, err = await asyncio.to_thread(_run_remote, profile, "docker restart 9router", 30)
            else:
                from updater import run_cmd
                import pathlib
                compose = None
                for p in [pathlib.Path.cwd() / "docker-compose.yml", pathlib.Path.cwd() / "9router-master" / "docker-compose.yml", pathlib.Path.cwd() / "9router-master" / "9router-master" / "docker-compose.yml"]:
                    if p.exists():
                        compose = str(p)
                        break
                if compose:
                    rc, out, err = await asyncio.to_thread(run_cmd, ["docker", "compose", "-f", compose, "restart", "9router"], None, 60)
                    if rc == 0:
                        log.update(f"[green]Restarted via compose: 9router[/]\n[dim]{out[-800:]}[/]")
                        return
                rc, out, err = await asyncio.to_thread(run_cmd, ["docker", "restart", "9router"], None, 30)
            status = "[green]OK[/]" if rc == 0 else f"[red]FAIL rc={rc}[/]"
            log.update(f"{status} 9router\n[dim]{out[-800:]}[/]\n[red]{err[-800:]}[/]" if err else f"{status} 9router\n[dim]{out[-800:]}[/]")
        except Exception as e:
            log.update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-docker-update")
    async def on_docker_update(self) -> None:
        log = self.query_one("#update-log", Static)
        profile = self._get_profile()
        is_remote = bool(profile and profile.ssh_host)
        log.update(f"[dim]Docker update: compose pull + up -d ...{' (remote)' if is_remote else ''}[/]")
        try:
            if is_remote:
                from updater import run_update_remote
                steps = await asyncio.to_thread(run_update_remote, profile, "docker", False, None, None)
            else:
                from updater import run_update
                steps = await asyncio.to_thread(run_update, "docker", False, None, None)
            lines = []
            for s in steps:
                status = "[green]OK[/]" if s["rc"] == 0 else f"[red]FAIL rc={s['rc']}[/]"
                lines.append(f"$ {s['cmd']}  {status}")
                if s["stdout"]:
                    lines.append(f"[dim]{s['stdout'][-800:]}[/]")
                if s["stderr"]:
                    lines.append(f"[red]{s['stderr'][-800:]}[/]")
                if s["rc"] != 0:
                    break
            else:
                lines.append("[green]Docker update completed[/]")
            log.update("\n".join(lines))
        except Exception as e:
            log.update(f"[red]{e}[/]")


class NineRouterTUI(App):
    CSS = """
    Screen { background: $background; }
    #overview-body, #providers-detail, #nodes-detail, #combos-detail, #models-detail, #keys-detail, #usage-body, #usage-detail, #settings-body {
        padding: 1 1;
        border: solid $primary-background;
        margin: 1 0;
        height: auto;
        max-height: 18;
    }
    DataTable { height: 1fr; min-height: 8; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 1 1; }
    #hint-bar { padding: 0 1; height: 1; background: $panel; color: $text-muted; }
    #update-version-body, #update-docker-body, #update-log { padding: 1 1; border: solid $primary-background; margin: 1 0; height: auto; max-height: 14; }
    #update-log { max-height: 20; }
    """

    TITLE = "9Router — Terminal Dashboard"
    SUB_TITLE = "Standalone TUI (no omnexsync dependency)"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "switch_server", "Switch Server"),
        Binding("1", "tab('overview')", "Overview"),
        Binding("2", "tab('providers')", "Providers"),
        Binding("3", "tab('nodes')", "Nodes"),
        Binding("4", "tab('combos')", "Combos"),
        Binding("5", "tab('models')", "Models"),
        Binding("6", "tab('keys')", "Keys"),
        Binding("7", "tab('usage')", "Usage"),
        Binding("8", "tab('settings')", "Settings"),
        Binding("9", "tab('update')", "Update"),
    ]

    def __init__(self, client: Optional[NinerouterClient] = None, **kw):
        super().__init__(**kw)
        self.client = client or NinerouterClient(load_config_from_env_and_file())

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("[dim]Press 's' to switch server  •  'r' to refresh  •  1-9 tabs  •  q quit[/]", id="hint-bar")
        with TabbedContent(initial="overview"):
            with TabPane("Overview", id="overview"):
                yield OverviewPane(self.client)
            with TabPane("Providers", id="providers"):
                yield ProvidersPane(self.client)
            with TabPane("Nodes", id="nodes"):
                yield NodesPane(self.client)
            with TabPane("Combos", id="combos"):
                yield CombosPane(self.client)
            with TabPane("Models", id="models"):
                yield ModelsPane(self.client)
            with TabPane("Keys", id="keys"):
                yield KeysPane(self.client)
            with TabPane("Usage", id="usage"):
                yield UsagePane(self.client)
            with TabPane("Settings", id="settings"):
                yield SettingsPane(self.client)
            with TabPane("Update", id="update"):
                yield UpdatePane(self.client)
        yield Footer()

    def action_refresh(self) -> None:
        # refresh current tab
        try:
            tc = self.query_one(TabbedContent)
            active = tc.active
            pane_map = {
                "overview": OverviewPane,
                "providers": ProvidersPane,
                "nodes": NodesPane,
                "combos": CombosPane,
                "models": ModelsPane,
                "keys": KeysPane,
                "usage": UsagePane,
                "settings": SettingsPane,
                "update": UpdatePane,
            }
            cls = pane_map.get(active)
            if cls:
                for w in self.query(cls):
                    if hasattr(w, "refresh_data"):
                        w.refresh_data()
                        break
        except Exception:
            pass

    def action_tab(self, name: str) -> None:
        try:
            self.query_one(TabbedContent).active = name
        except Exception:
            pass

    def action_switch_server(self) -> None:
        self.push_screen(ServerPickerScreen(self.client, self._on_server_picked))

    def _on_server_picked(self, profile) -> None:
        if not profile:
            return
        from client import NinerouterConfig, NinerouterClient
        cfg = NinerouterConfig(url=profile.url, api_key=profile.api_key, timeout=profile.timeout)
        self.client = NinerouterClient(cfg)
        self.sub_title = f"{profile.name} — {profile.url}"
        for pane in self.query(OverviewPane):
            pane.client = self.client
        for pane in self.query(ProvidersPane):
            pane.client = self.client
        for pane in self.query(NodesPane):
            pane.client = self.client
        for pane in self.query(CombosPane):
            pane.client = self.client
        for pane in self.query(ModelsPane):
            pane.client = self.client
        for pane in self.query(KeysPane):
            pane.client = self.client
        for pane in self.query(UsagePane):
            pane.client = self.client
        for pane in self.query(SettingsPane):
            pane.client = self.client
        for pane in self.query(UpdatePane):
            pane.client = self.client
        self.action_refresh()
        self.notify(f"Switched to {profile.name} — {profile.url}", timeout=3)

    def on_mount(self) -> None:
        from client import has_any_config
        if not has_any_config():
            self.call_later(lambda: self.push_screen(ServerPickerScreen(self.client, self._on_server_picked)))


# ── Server Picker (Modal) ──
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

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="9Router Terminal Dashboard (standalone)")
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
