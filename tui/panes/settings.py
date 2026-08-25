from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Static, Switch, Select, TextArea

from client import NinerouterClient
from tui.helpers import _store_plain, fmt_time, mask_key, status_style
# deferred import for screens to avoid circular

class SettingsPane(Static):
    """Settings editor — view + edit multi-config via PATCH /api/settings."""

    # Known editable keys (discovered from 9Router settings API)
    EDITABLE_FIELDS = [
        ("requireApiKey", "bool", "Require API Key"),
        ("tunnelEnabled", "bool", "Tunnel Enabled"),
        ("tunnelUrl", "str", "Tunnel URL"),
        ("logLevel", "select:debug,info,warn,error", "Log Level"),
        ("defaultModel", "str", "Default Model"),
        ("maxRetries", "int", "Max Retries"),
        ("requestTimeout", "int", "Request Timeout (ms)"),
        ("enableProxy", "bool", "Enable Proxy"),
        ("proxyUrl", "str", "Proxy URL"),
    ]

    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client
        self._raw: Dict[str, Any] = {}
        self._dirty: Dict[str, Any] = {}

    def compose(self) -> ComposeResult:
        yield Label("Settings — 9Router Config (GET/PATCH /api/settings)", id="settings-title")
        yield Horizontal(
            Button("Refresh", id="btn-settings-refresh", variant="primary"),
            Button("Edit", id="btn-settings-edit", variant="default"),
            Button("Save", id="btn-settings-save", variant="success"),
            Button("Copy", id="btn-settings-copy", variant="default"),
        )
        yield Static("", id="settings-body")
        yield Static("[dim]Click Edit to modify settings. Save sends PATCH /api/settings.[/]", id="settings-hint")
        # Editor area — hidden until Edit
        with Vertical(id="settings-editor", classes="hidden"):
            yield Label("[bold]Editor — change values then Save[/]", id="settings-editor-title")
            yield Static("", id="settings-editor-fields")
            with Horizontal(id="settings-editor-actions"):
                yield Button("Save", id="btn-settings-editor-save", variant="success")
                yield Button("Cancel", id="btn-settings-editor-cancel", variant="default")
                yield Button("Raw JSON", id="btn-settings-raw", variant="default")
            yield Static("", id="settings-editor-status")

    def on_mount(self) -> None:
        self.refresh_data()

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        body = self.query_one("#settings-body", Static)
        body.update("Loading...")
        try:
            data = await asyncio.to_thread(self.client.get_settings)
            self._raw = data if isinstance(data, dict) else {}
            txt = json.dumps(data, indent=2, ensure_ascii=False)[:6000]
            body.update(f"[dim]{txt}[/]")
            _store_plain(body, txt)
            self._dirty.clear()
            self._render_editor_fields()
        except Exception as e:
            body.update(f"[red]{e}[/]")
            _store_plain(body, str(e))

    def _render_editor_fields(self) -> None:
        """Render editable fields into #settings-editor-fields."""
        try:
            container = self.query_one("#settings-editor-fields", Static)
            if not self._raw:
                container.update("[dim]No settings loaded — Refresh first[/]")
                return
            lines: List[str] = []
            for key, kind, label in self.EDITABLE_FIELDS:
                val = self._raw.get(key, "—")
                dirty_mark = " [yellow]*[/]" if key in self._dirty else ""
                if kind == "bool":
                    lines.append(f"[bold]{label}[/] ({key}): [cyan]{val}[/]{dirty_mark}")
                elif kind.startswith("select:"):
                    opts = kind.split(":", 1)[1]
                    lines.append(f"[bold]{label}[/] ({key}): [cyan]{val}[/] [dim]({opts})[/]{dirty_mark}")
                else:
                    lines.append(f"[bold]{label}[/] ({key}): [cyan]{val}[/]{dirty_mark}")
            # Show extra keys not in EDITABLE_FIELDS
            extra = [k for k in self._raw.keys() if k not in {f[0] for f in self.EDITABLE_FIELDS}]
            if extra:
                lines.append("")
                lines.append("[dim]Other keys (read-only in form, editable via Raw JSON):[/]")
                for k in extra[:20]:
                    v = self._raw[k]
                    vs = json.dumps(v, ensure_ascii=False)[:80] if isinstance(v, (dict, list)) else str(v)[:80]
                    lines.append(f"  [dim]{k}: {vs}[/]")
            if self._dirty:
                lines.append("")
                lines.append(f"[yellow]Dirty: {', '.join(self._dirty.keys())}[/] — press Save to PATCH")
            container.update("\n".join(lines))
        except Exception:
            pass

    def _set_editor_visible(self, visible: bool) -> None:
        try:
            ed = self.query_one("#settings-editor")
            if visible:
                ed.remove_class("hidden")
            else:
                ed.add_class("hidden")
        except Exception:
            pass

    @on(Button.Pressed, "#btn-settings-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    @on(Button.Pressed, "#btn-settings-edit")
    def on_edit(self) -> None:
        from tui.screens.settings_edit import SettingsEditScreen
        if not self._raw:
            self.notify("No settings loaded — Refresh first", severity="warning")
            return
        self.app.push_screen(SettingsEditScreen(self._raw, self._on_edit_done))

    def _on_edit_done(self, patch: Optional[Dict[str, Any]]) -> None:
        if patch is None:
            return
        if not patch:
            self.notify("No changes", severity="warning")
            return
        self._dirty = patch
        self._render_editor_fields()
        self._set_editor_visible(True)
        self.notify(f"Staged {len(patch)} change(s) — press Save to apply", timeout=3)

    @on(Button.Pressed, "#btn-settings-save")
    @on(Button.Pressed, "#btn-settings-editor-save")
    async def on_save(self) -> None:
        if not self._dirty:
            self.notify("No changes to save — click Edit first", severity="warning")
            return
        status = self.query_one("#settings-editor-status", Static)
        status.update(f"[yellow]Saving {len(self._dirty)} field(s)...[/]")
        try:
            res = await asyncio.to_thread(self.client.patch_settings, self._dirty)
            status.update(f"[green]Saved:[/] {json.dumps(res, ensure_ascii=False)[:800]}")
            self.notify(f"Saved {len(self._dirty)} setting(s)", timeout=3)
            self._dirty.clear()
            self._set_editor_visible(False)
            self.refresh_data()
        except Exception as e:
            status.update(f"[red]Save failed: {e}[/]")
            self.notify(f"Save failed: {e}", severity="error", timeout=4)

    @on(Button.Pressed, "#btn-settings-editor-cancel")
    def on_cancel(self) -> None:
        self._dirty.clear()
        self._render_editor_fields()
        self._set_editor_visible(False)
        self.query_one("#settings-editor-status", Static).update("")

    @on(Button.Pressed, "#btn-settings-raw")
    def on_raw(self) -> None:
        from tui.screens.settings_edit import SettingsRawScreen
        self.app.push_screen(SettingsRawScreen(self._raw, self._on_raw_done))

    def _on_raw_done(self, patch: Optional[Dict[str, Any]]) -> None:
        if patch is None:
            return
        if not patch:
            self.notify("No changes", severity="warning")
            return
        self._dirty.update(patch)
        self._render_editor_fields()
        self._set_editor_visible(True)
        self.notify(f"Staged {len(patch)} change(s) from Raw JSON", timeout=3)
