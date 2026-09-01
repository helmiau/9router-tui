"""Provider Models pane — Providers > Available Models sub-tab."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from client import NinerouterClient
from tui.helpers import _store_plain

# Thinking levels per provider (from open-sse/providers/thinkingLevels.js)
THINKING_LEVELS = {
    "openai": ["auto", "high", "medium", "low", "none"],
    "anthropic": ["auto", "high", "medium", "low", "none"],
    "gemini": ["auto", "high", "medium", "low", "none"],
    "deepseek": ["auto", "high", "medium", "low", "none"],
    "claude-adaptive": ["auto", "high", "medium", "low", "none"],
    "default": ["auto", "high", "medium", "low", "none"],
}


class ProviderModelsPane(Static):
    """Available Models — thinking levels, custom/disabled models, fetch, add."""

    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._providers: List[Dict[str, Any]] = []
        self._models: List[Dict[str, Any]] = []
        self._custom: List[Dict[str, Any]] = []
        self._disabled: Dict[str, Any] = {}
        self._selected_provider: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Label("Available Models — thinking levels, custom/disabled models", id="prov-models-title")
        yield Horizontal(
            Select([], id="select-pm-provider", prompt="Select provider..."),
            Button("Refresh", id="btn-pm-refresh", variant="primary"),
            Button("Fetch Models", id="btn-pm-fetch", variant="default"),
            Button("Add Custom", id="btn-pm-add", variant="success"),
        )
        yield DataTable(id="table-pm", cursor_type="row", zebra_stripes=True)
        yield Static("", id="prov-models-detail")
        yield Horizontal(
            Button("Copy Detail", id="btn-pm-copy", variant="default"),
            Button("Test Model", id="btn-pm-test", variant="default"),
            Button("Toggle Disabled", id="btn-pm-toggle", variant="default"),
            Button("Set Thinking", id="btn-pm-thinking", variant="default"),
        )

    def on_mount(self) -> None:
        table = self.query_one("#table-pm", DataTable)
        table.add_columns("Model ID", "Name", "Type", "Thinking", "Custom", "Disabled", "Provider")
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        table = self.query_one("#table-pm", DataTable)
        table.clear()
        self._models = []
        try:
            providers = await asyncio.to_thread(self.client.list_providers)
            self._providers = providers
            sel = self.query_one("#select-pm-provider", Select)
            options = [(p.get("name", p.get("id", "?")), p.get("id")) for p in providers]
            sel.set_options(options)
            valid_ids = {p.get("id") for p in providers}
            if not self._selected_provider or self._selected_provider not in valid_ids:
                self._selected_provider = providers[0].get("id") if providers else None
                try:
                    sel.value = self._selected_provider
                except Exception:
                    pass
            # Fetch models for selected provider
            if self._selected_provider:
                models = await asyncio.to_thread(self.client.list_provider_models, self._selected_provider)
                self._models = models
                custom = await asyncio.to_thread(self.client.list_custom_models)
                self._custom = custom
                disabled = await asyncio.to_thread(self.client.list_disabled_models, self._selected_provider)
                self._disabled = disabled.get("ids", []) if isinstance(disabled, dict) else []
                custom_ids = {f"{m.get('providerAlias')}:{m.get('id')}" for m in custom}
                for m in models:
                    mid = m.get("id", "")
                    table.add_row(
                        mid[:40],
                        m.get("name", mid)[:24],
                        m.get("type", "llm")[:8],
                        m.get("thinking", "—")[:12],
                        "yes" if f"{self._selected_provider}:{mid}" in custom_ids else "no",
                        "yes" if mid in self._disabled else "no",
                        self._selected_provider[:8],
                    )
            w = self.query_one("#prov-models-detail", Static)
            txt = f"{len(self._models)} models"
            w.update(f"[dim]{txt}[/]")
            _store_plain(w, txt)
        except Exception as e:
            w = self.query_one("#prov-models-detail", Static)
            w.update(f"[red]{e}[/]")
            _store_plain(w, str(e))

    @on(Select.Changed, "#select-pm-provider")
    def on_provider_changed(self, event: Select.Changed) -> None:
        self._selected_provider = event.value
        self.refresh_data()

    @on(Button.Pressed, "#btn-pm-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    @on(Button.Pressed, "#btn-pm-fetch")
    def on_fetch(self) -> None:
        if not self._selected_provider:
            self.app.notify("Select a provider first", severity="warning")
            return
        rec = next((p for p in self._providers if p.get("id") == self._selected_provider), None)
        if not rec:
            return
        url = rec.get("baseUrl", "")
        ptype = rec.get("type", "openai-compatible")
        if not url:
            self.app.notify("Provider has no baseUrl", severity="warning")
            return
        detail = self.query_one("#prov-models-detail", Static)
        detail.update("Fetching suggested models...")
        import asyncio as _aio

        async def _do():
            try:
                data = await _aio.to_thread(self.client.list_suggested_models, url, ptype)
                txt = json.dumps(data[:50], indent=2, ensure_ascii=False)[:2000]
                detail.update(f"[green]Suggested ({len(data)}):[/] {txt}")
                _store_plain(detail, txt)
            except Exception as e:
                detail.update(f"[red]Fetch failed: {e}[/]")
                _store_plain(detail, str(e))

        _aio.create_task(_do())

    @on(Button.Pressed, "#btn-pm-add")
    def on_add(self) -> None:
        if not self._selected_provider:
            self.app.notify("Select a provider first", severity="warning")
            return
        from tui.screens.custom_model_edit import CustomModelEditScreen
        self.app.push_screen(CustomModelEditScreen(self.client, self._selected_provider, None, self._on_custom_saved))

    def _on_custom_saved(self, provider_alias: str, payload: Optional[Dict[str, Any]] = None) -> None:
        import asyncio as _aio

        async def _do():
            try:
                if payload:
                    await _aio.to_thread(
                        self.client.create_custom_model,
                        payload.get("providerAlias", provider_alias),
                        payload.get("id", ""),
                        payload.get("type", "llm"),
                        payload.get("name", ""),
                    )
                    self.app.notify("Custom model created", timeout=2)
                self.refresh_data()
            except Exception as e:
                self.app.notify(f"Save failed: {e}", severity="error", timeout=4)

        _aio.create_task(_do())

    @on(Button.Pressed, "#btn-pm-copy")
    def on_copy(self) -> None:
        try:
            w = self.query_one("#prov-models-detail", Static)
            text = getattr(w, "_plain_text", "") or ""
            if text:
                self.app._copy_text(text)
        except Exception:
            pass

    @on(Button.Pressed, "#btn-pm-test")
    def on_test(self) -> None:
        rec = self._selected_model()
        if not rec:
            self.app.notify("Select a model first", severity="warning")
            return
        detail = self.query_one("#prov-models-detail", Static)
        detail.update(f"Testing {rec.get('id')}...")
        import asyncio as _aio

        async def _do():
            try:
                res = await _aio.to_thread(self.client.test_model, rec.get("id"), rec.get("type", "llm"))
                txt = json.dumps(res, indent=2, ensure_ascii=False)[:2000]
                detail.update(f"[green]Test {rec.get('id')}:[/] {txt}")
                _store_plain(detail, txt)
            except Exception as e:
                detail.update(f"[red]Test failed: {e}[/]")
                _store_plain(detail, str(e))

        _aio.create_task(_do())

    @on(Button.Pressed, "#btn-pm-toggle")
    def on_toggle_disabled(self) -> None:
        rec = self._selected_model()
        if not rec or not self._selected_provider:
            self.app.notify("Select a model first", severity="warning")
            return
        mid = rec.get("id", "")
        is_disabled = mid in self._disabled
        import asyncio as _aio

        async def _do():
            try:
                if is_disabled:
                    await _aio.to_thread(self.client.enable_models, self._selected_provider, [mid])
                    self.app.notify(f"Enabled {mid}", timeout=2)
                else:
                    await _aio.to_thread(self.client.disable_models, self._selected_provider, [mid])
                    self.app.notify(f"Disabled {mid}", timeout=2)
                self.refresh_data()
            except Exception as e:
                self.app.notify(f"Toggle failed: {e}", severity="error", timeout=4)

        _aio.create_task(_do())

    @on(Button.Pressed, "#btn-pm-thinking")
    def on_set_thinking(self) -> None:
        rec = self._selected_model()
        if not rec or not self._selected_provider:
            self.app.notify("Select a model first", severity="warning")
            return
        from tui.screens.thinking_level import ThinkingLevelScreen
        provider = next((p for p in self._providers if p.get("id") == self._selected_provider), None)
        ptype = (provider or {}).get("type", "default")
        levels = THINKING_LEVELS.get(ptype, THINKING_LEVELS["default"])
        self.app.push_screen(ThinkingLevelScreen(self.client, self._selected_provider, rec.get("id"), levels, self._on_thinking_saved))

    def _on_thinking_saved(self, provider_id: str, model_id: str, level: str) -> None:
        import asyncio as _aio

        async def _do():
            try:
                # providerThinking is keyed by providerId → { mode }
                await _aio.to_thread(self.client.patch_provider_thinking, {provider_id: {"mode": level}})
                self.app.notify(f"Thinking set to {level}", timeout=2)
                self.refresh_data()
            except Exception as e:
                self.app.notify(f"Save failed: {e}", severity="error", timeout=4)

        _aio.create_task(_do())

    def _selected_model(self) -> Optional[Dict[str, Any]]:
        try:
            table = self.query_one("#table-pm", DataTable)
            if table.cursor_row is None or table.cursor_row < 0:
                return None
            if 0 <= table.cursor_row < len(self._models):
                return self._models[table.cursor_row]
            row = table.get_row_at(table.cursor_row)
            mid = row[0]
            return next((m for m in self._models if m.get("id", "").startswith(mid)), None)
        except Exception:
            return None

    @on(DataTable.RowSelected, "#table-pm")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            idx = event.cursor_row
            rec = self._models[idx] if 0 <= idx < len(self._models) else None
            if rec:
                txt = f"{rec.get('id')}  name={rec.get('name')}  type={rec.get('type')}\n{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}"
                w = self.query_one("#prov-models-detail", Static)
                w.update(f"[bold]{rec.get('id')}[/]  name={rec.get('name')}  type={rec.get('type')}\n[dim]{json.dumps(rec, indent=2, ensure_ascii=False)[:2000]}[/]")
                _store_plain(w, txt)
        except Exception:
            pass