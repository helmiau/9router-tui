from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Label, Static, Select

from client import NinerouterClient
from tui.helpers import _store_plain, display_node_id, fmt_time, mask_key, status_style

# Provider categories from 9router-master/open-sse/providers/registry
# Custom providers are openai-compatible / anthropic-compatible / custom-embedding
PROVIDER_CATEGORIES = {
    "custom": "Custom Providers",  # openai-compatible, anthropic-compatible, custom-embedding
    "oauth": "OAuth Providers",
    "freeTier": "Free Tier Providers",
    "apikey": "API Key Providers",
    "free": "Free Providers",
    "webCookie": "Web Cookie Providers",
}

def _provider_category(provider_id: str, node_type: str = "") -> str:
    """Classify a provider/node into category."""
    if node_type in ("openai-compatible", "anthropic-compatible", "custom-embedding"):
        return "custom"
    if provider_id.startswith("openai-compatible-") or provider_id.startswith("anthropic-compatible-") or provider_id.startswith("custom-embedding-"):
        return "custom"
    # For built-in providers, we need to check registry
    # Hardcoded known lists from 9router-master
    oauth = {"antigravity", "claude", "cline", "clinepass", "codebuddy-cn", "codebuddy-intl", "codex", "cursor", "gemini-cli", "github", "gitlab", "iflow", "kiro", "qoder", "trae", "windsurf", "xai", "zed", "copilot"}
    free = {"devin-cli", "gemini-cli", "kiro", "mimo-free", "opencode"}
    freeTier = {"api-airforce", "bazaarlink", "byteplus", "cloudflare-ai", "coqui", "deepseek", "edge-tts", "glm-cn", "minimax", "mistral", "nvidia", "openrouter", "poolside", "qwen", "tencent-hunyuan", "volcengine", "xiaomi-mimo", "zhipu"}
    if provider_id in oauth:
        return "oauth"
    if provider_id in free:
        return "free"
    if provider_id in freeTier:
        return "freeTier"
    # Default to apikey for known apikey providers
    return "apikey"


class NodesPane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._data: List[Dict[str, Any]] = []
        self._filtered: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Label("Provider Nodes — All Active AI Providers + Custom Endpoints", id="nodes-title")
        yield Horizontal(
            Button("Refresh", id="btn-nodes-refresh", variant="primary"),
            Button("Add Node", id="btn-nodes-add", variant="success"),
            Select([("All Categories", "all"), ("Custom Providers", "custom"), ("OAuth Providers", "oauth"), ("Free Tier Providers", "freeTier"), ("API Key Providers", "apikey")], value="all", id="select-nodes-category"),
            Select([("All", "all"), ("Enabled", "enabled"), ("Disabled", "disabled")], value="all", id="select-nodes-status"),
        )
        yield Horizontal(
            Input(placeholder="Filter by name/prefix...", id="input-nodes-filter"),
        )
        yield DataTable(id="table-nodes", cursor_type="row", zebra_stripes=True)
        yield Static("", id="nodes-detail")
        yield Horizontal(
            Button("Copy Detail", id="btn-nodes-copy", variant="default"),
            Button("Edit", id="btn-nodes-edit", variant="default"),
            Button("Toggle Active", id="btn-nodes-toggle", variant="default"),
            Button("Delete", id="btn-nodes-delete", variant="error"),
        )

    def on_mount(self) -> None:
        table = self.query_one("#table-nodes", DataTable)
        table.add_columns("Name", "Prefix", "Type", "API Type", "Base URL", "Active", "ID")
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        table = self.query_one("#table-nodes", DataTable)
        table.clear()
        self._data = []
        try:
            nodes = await asyncio.to_thread(self.client.list_nodes)
            # Also show built-in providers as provider entries (one row per provider, not per account)
            # — mirrors dashboard/providers page: each provider card = one provider, not N accounts
            try:
                providers = await asyncio.to_thread(self.client.list_providers)
                # Group by provider id (deduplicate accounts)
                seen_providers: dict[str, dict] = {}
                for p in providers:
                    prov = p.get("provider", "")
                    if not prov or prov.startswith("openai-compatible-") or prov.startswith("anthropic-compatible-") or prov.startswith("custom-embedding-"):
                        continue
                    if prov not in seen_providers:
                        seen_providers[prov] = p
                    else:
                        # keep the one with isActive=True if any
                        if p.get("isActive") and not seen_providers[prov].get("isActive"):
                            seen_providers[prov] = p
                node_ids = {n.get("id", "") for n in nodes}
                node_prefixes = {n.get("prefix", "") for n in nodes}
                for prov, p in seen_providers.items():
                    if prov in node_ids or prov in node_prefixes:
                        continue
                    nodes.append({
                        "name": prov,
                        "prefix": prov,
                        "type": "built-in",
                        "apiType": "—",
                        "baseUrl": "—",
                        "id": prov,
                        "isActive": True,
                        "_isProvider": True,
                    })
            except Exception:
                pass
            self._data = nodes
            for n in nodes:
                active_str = "yes" if n.get("isActive", True) else "no"
                table.add_row(
                    n.get("name", "—")[:20],
                    n.get("prefix", "—"),
                    n.get("type", "—"),
                    n.get("apiType", n.get("api_type", "—")),
                    n.get("baseUrl", n.get("base_url", "—"))[:40],
                    active_str,
                    display_node_id(n.get("id", ""))[:24],
                )
            self._filtered = list(self._data)
            w = self.query_one("#nodes-detail", Static)
            txt = f"{len(nodes)} nodes/providers"
            w.update(f"[dim]{txt}[/]")
            _store_plain(w, txt)
        except Exception as e:
            self._filtered = list(self._data)
            w = self.query_one("#nodes-detail", Static)
            w.update(f"[red]{e}[/]")
            _store_plain(w, str(e))

    @on(Button.Pressed, "#btn-nodes-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    def _apply_filters(self) -> None:
        try:
            q = self.query_one("#input-nodes-filter", Input).value.lower().strip()
        except Exception:
            q = ""
        try:
            cat = self.query_one("#select-nodes-category", Select).value or "all"
        except Exception:
            cat = "all"
        try:
            status = self.query_one("#select-nodes-status", Select).value or "all"
        except Exception:
            status = "all"
        table = self.query_one("#table-nodes", DataTable)
        table.clear()
        self._filtered = []
        for n in self._data:
            # Text filter
            hay = f"{n.get('name','')} {n.get('prefix','')} {n.get('id','')} {n.get('baseUrl','')}".lower()
            if q and q not in hay:
                continue
            # Category filter
            if cat != "all":
                ncat = _provider_category(n.get("prefix", n.get("id", "")), n.get("type", ""))
                if ncat != cat:
                    continue
            # Status filter
            if status != "all":
                is_active = n.get("isActive", True)
                # For built-in providers, check if active
                if n.get("_isProvider"):
                    is_active = True
                if status == "enabled" and not is_active:
                    continue
                if status == "disabled" and is_active:
                    continue
            self._filtered.append(n)
            active_str = "yes" if n.get("isActive", True) else "no"
            if n.get("_isProvider"):
                active_str = "yes"
            table.add_row(
                n.get("name", "—")[:20],
                n.get("prefix", "—"),
                n.get("type", "—"),
                n.get("apiType", n.get("api_type", "—")),
                n.get("baseUrl", n.get("base_url", "—"))[:40],
                active_str,
                display_node_id(n.get("id", ""))[:24],
            )

    @on(Input.Changed, "#input-nodes-filter")
    def on_filter(self, event: Input.Changed) -> None:
        self._apply_filters()

    @on(Select.Changed, "#select-nodes-category")
    def on_category_changed(self, event: Select.Changed) -> None:
        self._apply_filters()

    @on(Select.Changed, "#select-nodes-status")
    def on_status_changed(self, event: Select.Changed) -> None:
        self._apply_filters()

    def _selected_node(self) -> Optional[Dict[str, Any]]:
        try:
            table = self.query_one("#table-nodes", DataTable)
            if table.cursor_row is None or table.cursor_row < 0:
                return None
            data = self._filtered if self._filtered else self._data
            if 0 <= table.cursor_row < len(data):
                return data[table.cursor_row]
            row = table.get_row_at(table.cursor_row)
            short_id = row[-1]
            return next((n for n in self._data if n.get("id","").startswith(short_id) or short_id in n.get("id","")), None)
        except Exception:
            return None

    @on(DataTable.RowSelected, "#table-nodes")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = event.cursor_row
            data = self._filtered if self._filtered else self._data
            rec = data[idx] if 0 <= idx < len(data) else None
            if rec is None:
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

    @on(Button.Pressed, "#btn-nodes-toggle")
    def on_toggle(self) -> None:
        rec = self._selected_node()
        if not rec:
            self.app.notify("Select a node first", severity="warning")
            return
        if rec.get("_isProvider"):
            self.app.notify("Built-in provider — toggle via Providers tab", severity="warning")
            return
        new_val = not rec.get("isActive", True)
        import asyncio as _aio
        async def _do():
            try:
                await _aio.to_thread(self.client.update_node, rec["id"], {"isActive": new_val})
                self.app.notify(f"{'Enabled' if new_val else 'Disabled'} {rec.get('name')}", timeout=2)
                self.refresh_data()
            except Exception as e:
                self.app.notify(f"Toggle failed: {e}", severity="error", timeout=4)
        _aio.create_task(_do())

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
