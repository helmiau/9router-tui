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

try:
    from tui.panes.settings import SettingsPane as _SettingsPane
    EDITABLE_FIELDS = _SettingsPane.EDITABLE_FIELDS
except Exception:
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

class SettingsEditScreen(ModalScreen):
    """Form to edit multiple settings at once. Returns dict patch or None."""

    DEFAULT_CSS = """
    SettingsEditScreen { align: center middle; }
    #edit-container {
        width: 78;
        height: auto;
        max-height: 38;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #edit-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #edit-fields { height: auto; max-height: 26; }
    #edit-fields Input, #edit-fields Select { margin: 1 0; }
    #edit-status { height: auto; margin: 1 0; }
    """

    def __init__(self, raw: Dict[str, Any], callback, **kw):
        super().__init__(**kw)
        self._raw = raw or {}
        self._callback = callback

    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Input, Button, Select
        fields = EDITABLE_FIELDS
        with Vertical(id="edit-container"):
            yield Label("Edit Settings — change values, then Apply", id="edit-title")
            with VerticalScroll(id="edit-fields"):
                for key, kind, label in fields:
                    cur = self._raw.get(key, "")
                    cur_s = str(cur) if cur != "" else ""
                    if kind == "bool":
                        # Use Select for bool
                        yield Label(f"{label} ({key})")
                        yield Select([("true", "true"), ("false", "false")], value=str(cur).lower() if str(cur).lower() in ("true", "false") else "false", id=f"edit-{key}", allow_blank=True)
                    elif kind.startswith("select:"):
                        opts = kind.split(":", 1)[1].split(",")
                        choices = [(o.strip(), o.strip()) for o in opts]
                        cur_v = str(cur) if str(cur) in [o.strip() for o in opts] else (opts[0] if opts else "")
                        yield Label(f"{label} ({key})")
                        yield Select(choices, value=cur_v, id=f"edit-{key}", allow_blank=True)
                    elif kind == "int":
                        yield Label(f"{label} ({key})")
                        yield Input(value=cur_s, placeholder=f"{label} (int)", id=f"edit-{key}")
                    else:
                        yield Label(f"{label} ({key})")
                        yield Input(value=cur_s, placeholder=label, id=f"edit-{key}")
            yield Static("", id="edit-status")
            with Horizontal():
                yield Button("Apply", id="btn-edit-apply", variant="primary")
                yield Button("Cancel", id="btn-edit-cancel", variant="default")

    @on(Button.Pressed, "#btn-edit-apply")
    def on_apply(self) -> None:
        patch: Dict[str, Any] = {}
        for key, kind, _label in EDITABLE_FIELDS:
            try:
                w = self.query_one(f"#edit-{key}")
                raw_val = None
                if hasattr(w, "value"):
                    raw_val = w.value
                elif hasattr(w, "value"):
                    raw_val = w.value
                # Select returns value, Input returns value
                val = raw_val
                if val is None or (isinstance(val, str) and val == ""):
                    continue
                # Normalize
                orig = self._raw.get(key)
                if kind == "bool":
                    norm = str(val).lower() == "true"
                    if orig is not None and bool(orig) == norm:
                        continue
                    patch[key] = norm
                elif kind == "int":
                    try:
                        norm = int(str(val).strip())
                    except Exception:
                        self.query_one("#edit-status", Static).update(f"[red]Invalid int for {key}: {val}[/]")
                        return
                    if orig is not None and orig == norm:
                        continue
                    patch[key] = norm
                else:
                    norm = str(val)
                    if orig is not None and str(orig) == norm:
                        continue
                    patch[key] = norm
            except Exception:
                continue
        self.dismiss(patch)
        self._callback(patch)

    @on(Button.Pressed, "#btn-edit-cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
        self._callback(None)

class SettingsRawScreen(ModalScreen):
    """Raw JSON editor for settings — edit any keys, multi-config."""

    DEFAULT_CSS = """
    SettingsRawScreen { align: center middle; }
    #raw-container {
        width: 82;
        height: 36;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #raw-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #raw-area { height: 22; border: solid $primary-background; }
    #raw-status { height: auto; margin: 1 0; }
    """

    def __init__(self, raw: Dict[str, Any], callback, **kw):
        super().__init__(**kw)
        self._raw = raw or {}
        self._callback = callback

    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Button, TextArea
        with Vertical(id="raw-container"):
            yield Label("Raw JSON — edit any settings (only changed keys will be PATCHed)", id="raw-title")
            yield TextArea(json.dumps(self._raw, indent=2, ensure_ascii=False), id="raw-area", language="json")
            yield Static("[dim]Edit JSON, then Apply. Invalid JSON will be rejected.[/]", id="raw-status")
            with Horizontal():
                yield Button("Apply", id="btn-raw-apply", variant="primary")
                yield Button("Cancel", id="btn-raw-cancel", variant="default")

    @on(Button.Pressed, "#btn-raw-apply")
    def on_apply(self) -> None:
        try:
            ta = self.query_one("#raw-area", TextArea)
            text = ta.text
            data = json.loads(text)
            if not isinstance(data, dict):
                self.query_one("#raw-status", Static).update("[red]JSON must be an object[/]")
                return
            # diff against original — only changed keys
            patch: Dict[str, Any] = {}
            for k, v in data.items():
                if k not in self._raw or self._raw[k] != v:
                    patch[k] = v
            # also detect deletions? skip — PATCH usually merges
            self.dismiss(patch)
            self._callback(patch)
        except json.JSONDecodeError as e:
            self.query_one("#raw-status", Static).update(f"[red]Invalid JSON: {e}[/]")
        except Exception as e:
            self.query_one("#raw-status", Static).update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-raw-cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)
        self._callback(None)


# ── Node Edit / UID Edit / Confirm ──
