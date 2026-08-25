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

from tui.helpers import uid_prefix_for_type, validate_uid, extract_uid_suffix

class NodeEditScreen(ModalScreen):
    """Create or edit a provider node. For edit, pre-fills from rec."""

    DEFAULT_CSS = """
    NodeEditScreen { align: center middle; }
    #node-edit-container { width: 76; height: auto; max-height: 36; background: $surface; border: thick $primary; padding: 1 2; }
    #node-edit-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #node-edit-fields Input, #node-edit-fields Select { margin: 1 0; }
    #node-edit-status { height: auto; margin: 1 0; }
    """

    def __init__(self, client, rec: Optional[Dict[str, Any]], callback, **kw):
        super().__init__(**kw)
        self._client = client
        self._rec = rec
        self._cb = callback

    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Input, Button, Select
        is_edit = self._rec is not None
        title = "Edit Node" if is_edit else "Add Node"
        rec = self._rec or {}
        with Vertical(id="node-edit-container"):
            yield Label(title, id="node-edit-title")
            with Vertical(id="node-edit-fields"):
                yield Label("Name")
                yield Input(value=rec.get("name", ""), placeholder="e.g. CutadAI", id="node-name")
                yield Label("Prefix (e.g. cutad, hcn, bynara)")
                yield Input(value=rec.get("prefix", ""), placeholder="prefix", id="node-prefix")
                yield Label("Type")
                yield Select([("openai-compatible", "openai-compatible"), ("anthropic-compatible", "anthropic-compatible"), ("custom-embedding", "custom-embedding")], value=rec.get("type", "openai-compatible"), id="node-type", allow_blank=False)
                yield Label("API Type (only for openai-compatible: chat / responses)")
                yield Select([("chat", "chat"), ("responses", "responses")], value=rec.get("apiType", rec.get("api_type", "chat")) or "chat", id="node-apitype", allow_blank=True)
                yield Label("Base URL")
                yield Input(value=rec.get("baseUrl", rec.get("base_url", "")), placeholder="https://api.example.com/v1", id="node-baseurl")
            yield Static("", id="node-edit-status")
            with Horizontal():
                yield Button("Save", id="btn-node-save", variant="primary")
                yield Button("Cancel", id="btn-node-cancel", variant="default")

    @on(Button.Pressed, "#btn-node-save")
    def on_save(self) -> None:
        try:
            name = self.query_one("#node-name", Input).value.strip()
            prefix = self.query_one("#node-prefix", Input).value.strip()
            ntype = self.query_one("#node-type", Select).value or "openai-compatible"
            apitype = self.query_one("#node-apitype", Select).value or "chat"
            base_url = self.query_one("#node-baseurl", Input).value.strip()
            if not name:
                self.query_one("#node-edit-status", Static).update("[red]Name is required[/]")
                return
            if not prefix:
                self.query_one("#node-edit-status", Static).update("[red]Prefix is required[/]")
                return
            if not base_url:
                self.query_one("#node-edit-status", Static).update("[red]Base URL is required[/]")
                return
            payload: Dict[str, Any] = {"name": name, "prefix": prefix, "type": ntype, "baseUrl": base_url}
            if ntype == "openai-compatible":
                payload["apiType"] = apitype if apitype in ("chat", "responses") else "chat"
            # async save
            import asyncio as _aio
            async def _do():
                try:
                    if self._rec:
                        await _aio.to_thread(self._client.update_node, self._rec["id"], payload)
                    else:
                        await _aio.to_thread(self._client.create_node, payload)
                    self.app.notify("Saved", timeout=2)
                    self.dismiss(True)
                    self._cb(True)
                except Exception as e:
                    self.query_one("#node-edit-status", Static).update(f"[red]{e}[/]")
            _aio.create_task(_do())
        except Exception as e:
            try:
                self.query_one("#node-edit-status", Static).update(f"[red]{e}[/]")
            except Exception:
                pass

    @on(Button.Pressed, "#btn-node-cancel")
    def on_cancel(self) -> None:
        self.dismiss(False)
        self._cb(False)

class NodeUidEditScreen(ModalScreen):
    """Edit the generated UID (suffix) of a provider node ID."""

    DEFAULT_CSS = """
    NodeUidEditScreen { align: center middle; }
    #uid-edit-container { width: 76; height: auto; background: $surface; border: thick $primary; padding: 1 2; }
    #uid-edit-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #uid-edit-status { height: auto; margin: 1 0; }
    #uid-edit-fields Input { margin: 1 0; }
    """

    def __init__(self, client, rec: Dict[str, Any], callback, **kw):
        super().__init__(**kw)
        self._client = client
        self._rec = rec
        self._cb = callback

    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Input, Button
        rec = self._rec
        full_id = rec.get("id", "")
        ntype = rec.get("type", "")
        apitype = rec.get("apiType", rec.get("api_type", ""))
        prefix = uid_prefix_for_type(ntype, apitype)
        suffix = extract_uid_suffix(full_id, ntype, apitype)
        with Vertical(id="uid-edit-container"):
            yield Label(f"Edit UID — {rec.get('name', '')} ({full_id})", id="uid-edit-title")
            yield Static(f"[dim]Prefix: {prefix}  (read-only)[/]", id="uid-prefix-label")
            yield Static(f"[dim]Current full ID: {full_id}[/]", id="uid-current")
            yield Label("New suffix (a-z, 0-9, -, _  — e.g. cutad, hcnsec, bynara)")
            yield Input(value=suffix, placeholder="suffix", id="uid-suffix")
            yield Static(f"[dim]Preview: {prefix}<suffix>[/]", id="uid-preview")
            yield Static("", id="uid-edit-status")
            with Horizontal():
                yield Button("Save UID", id="btn-uid-save", variant="primary")
                yield Button("Cancel", id="btn-uid-cancel", variant="default")

    @on(Input.Changed, "#uid-suffix")
    def on_suffix_changed(self, event: Input.Changed) -> None:
        try:
            rec = self._rec
            ntype = rec.get("type", "")
            apitype = rec.get("apiType", rec.get("api_type", ""))
            prefix = uid_prefix_for_type(ntype, apitype)
            suffix = event.value.strip()
            preview = prefix + suffix if suffix else prefix + "…"
            self.query_one("#uid-preview", Static).update(f"[dim]Preview: {preview}[/]")
        except Exception:
            pass

    @on(Button.Pressed, "#btn-uid-save")
    def on_save(self) -> None:
        try:
            rec = self._rec
            ntype = rec.get("type", "")
            apitype = rec.get("apiType", rec.get("api_type", ""))
            prefix = uid_prefix_for_type(ntype, apitype)
            suffix = self.query_one("#uid-suffix", Input).value.strip()
            if not suffix:
                self.query_one("#uid-edit-status", Static).update("[red]Suffix cannot be empty[/]")
                return
            if not all(c.isalnum() or c in "-_" for c in suffix):
                self.query_one("#uid-edit-status", Static).update("[red]Suffix may only contain a-z, 0-9, -, _[/]")
                return
            new_id = prefix + suffix
            ok, err = validate_uid(ntype, apitype, new_id)
            if not ok:
                self.query_one("#uid-edit-status", Static).update(f"[red]{err}[/]")
                return
            if new_id == rec.get("id", ""):
                self.query_one("#uid-edit-status", Static).update("[yellow]No change[/]")
                return
            # 9Router has no direct UID PATCH — we do delete + create with same fields but new ID is server-generated.
            # Workaround: inform user that UID is server-generated; we can only recreate node with desired suffix via backup edit.
            # Instead, try to update via PUT if server supports id change, else show guidance.
            # Attempt: create new node with desired ID by using backup-style payload (some servers accept id in POST).
            # Fallback: show instructions.
            import asyncio as _aio
            async def _do():
                try:
                    # Try to create new node and delete old one — preserves data, changes ID
                    # First, try POST with explicit id (if server allows)
                    payload = {
                        "name": rec.get("name", ""),
                        "prefix": rec.get("prefix", ""),
                        "type": ntype,
                        "baseUrl": rec.get("baseUrl", rec.get("base_url", "")),
                        "apiType": apitype if ntype == "openai-compatible" else None,
                    }
                    # Remove None
                    payload = {k: v for k, v in payload.items() if v is not None}
                    # Attempt to create with new ID via direct API if supported
                    # If not, we fallback to informing user to edit backup JSON
                    try:
                        # Try POST with id field — some 9Router versions accept it
                        payload_with_id = {**payload, "id": new_id}
                        await _aio.to_thread(self._client.create_node, payload_with_id)
                        # If succeeded, delete old
                        try:
                            await _aio.to_thread(self._client.delete_node, rec["id"])
                        except Exception:
                            pass
                        self.app.notify(f"UID changed to {new_id}", timeout=3)
                        self.dismiss(True)
                        self._cb(True)
                        return
                    except Exception as e:
                        # If server rejects id, fallback to guidance
                        msg = str(e)
                        if "already exists" in msg.lower() or "duplicate" in msg.lower():
                            self.query_one("#uid-edit-status", Static).update(f"[red]ID already exists: {new_id}[/]")
                            return
                        # Generic fallback: tell user to edit backup
                        self.query_one("#uid-edit-status", Static).update(f"[yellow]Server does not allow direct UID edit.[/]\n[dim]To change UID, export backup JSON, edit providerNodes[].id from '{rec['id']}' to '{new_id}', then re-import.[/]\n[red]{e}[/]")
                except Exception as e:
                    self.query_one("#uid-edit-status", Static).update(f"[red]{e}[/]")
            _aio.create_task(_do())
        except Exception as e:
            try:
                self.query_one("#uid-edit-status", Static).update(f"[red]{e}[/]")
            except Exception:
                pass

    @on(Button.Pressed, "#btn-uid-cancel")
    def on_cancel(self) -> None:
        self.dismiss(False)
        self._cb(False)
