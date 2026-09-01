"""Custom model add/edit screen."""
from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from client import NinerouterClient


class CustomModelEditScreen(ModalScreen):
    DEFAULT_CSS = """
    CustomModelEditScreen { align: center middle; }
    #cmodel-container { width: 70; height: auto; background: $surface; border: thick $primary; padding: 1 2; }
    #cmodel-container > Horizontal { margin-top: 1; }
    """

    def __init__(self, client: NinerouterClient, provider_alias: str, model: Optional[dict], on_save, **kw):
        super().__init__(**kw)
        self.client = client
        self.provider_alias = provider_alias
        self.model = model or {}
        self.on_save = on_save

    def compose(self) -> ComposeResult:
        m = self.model
        with Vertical(id="cmodel-container"):
            yield Static("Add Custom Model")
            yield Label("Provider Alias:")
            yield Input(value=self.provider_alias or "", id="inp-cmodel-provider", disabled=True)
            yield Label("Model ID:")
            yield Input(value=m.get("id", ""), id="inp-cmodel-id", placeholder="e.g. gpt-4o-custom")
            yield Label("Type:")
            yield Select(
                options=[("llm", "llm"), ("embedding", "embedding"), ("rerank", "rerank"), ("moderation", "moderation")],
                value=m.get("type", "llm"),
                id="sel-cmodel-type",
                allow_blank=False,
            )
            yield Label("Name:")
            yield Input(value=m.get("name", ""), id="inp-cmodel-name", placeholder="display name")
            with Horizontal():
                yield Button("Save", id="btn-cmodel-save", variant="success")
                yield Button("Cancel", id="btn-cmodel-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cmodel-cancel":
            self.dismiss(None)
            return
        if event.button.id == "btn-cmodel-save":
            model_id = self.query_one("#inp-cmodel-id", Input).value.strip()
            mtype = self.query_one("#sel-cmodel-type", Select).value
            name = self.query_one("#inp-cmodel-name", Input).value.strip()
            if not model_id:
                self.app.notify("Model ID is required", severity="error")
                return
            payload = {
                "providerAlias": self.provider_alias,
                "id": model_id,
                "type": mtype,
                "name": name or model_id,
            }
            # Call on_save callback if provided
            if callable(self.on_save):
                self.on_save(payload.get("providerAlias"), payload)
            self.dismiss(payload)
