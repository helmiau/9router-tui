"""Provider connection (node) add/edit screen."""
from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from client import NinerouterClient


class ProviderConnectionEditScreen(ModalScreen):
    DEFAULT_CSS = """
    ProviderConnectionEditScreen { align: center middle; }
    #conn-container { width: 70; height: auto; background: $surface; border: thick $primary; padding: 1 2; }
    #conn-container > Horizontal { margin-top: 1; }
    """

    def __init__(self, client: NinerouterClient, provider: Optional[dict], on_save, **kw):
        super().__init__(**kw)
        self.client = client
        self.provider = provider or {}
        self.on_save = on_save

    def compose(self) -> ComposeResult:
        p = self.provider
        with Vertical(id="conn-container"):
            yield Static("Add / Edit Provider Connection")
            yield Label("Name:")
            yield Input(value=p.get("name", ""), id="inp-conn-name")
            yield Label("Provider type:")
            yield Select(
                options=[
                    ("openai-compatible-chat", "openai-compatible-chat"),
                    ("openai-compatible-responses", "openai-compatible-responses"),
                    ("anthropic-compatible", "anthropic-compatible"),
                    ("custom-embedding", "custom-embedding"),
                ],
                value=p.get("type", "openai-compatible-chat"),
                id="sel-conn-type",
                allow_blank=False,
            )
            yield Label("Base URL:")
            yield Input(value=p.get("baseUrl", ""), id="inp-conn-baseurl", placeholder="https://...")
            yield Label("API Key:")
            yield Input(value=p.get("apiKey", ""), id="inp-conn-apikey", password=True)
            yield Label("Priority:")
            yield Input(value=str(p.get("priority", 0)), id="inp-conn-priority")
            yield Label("Provider alias (for models):")
            yield Input(value=p.get("provider", ""), id="inp-conn-provider")
            with Horizontal():
                yield Button("Save", id="btn-conn-save", variant="success")
                yield Button("Cancel", id="btn-conn-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-conn-cancel":
            self.dismiss(None)
            return
        if event.button.id == "btn-conn-save":
            name = self.query_one("#inp-conn-name", Input).value.strip()
            ctype = self.query_one("#sel-conn-type", Select).value
            base_url = self.query_one("#inp-conn-baseurl", Input).value.strip()
            api_key = self.query_one("#inp-conn-apikey", Input).value
            try:
                priority = int(self.query_one("#inp-conn-priority", Input).value.strip() or "0")
            except ValueError:
                priority = 0
            provider_alias = self.query_one("#inp-conn-provider", Input).value.strip()
            payload = {
                "name": name,
                "type": ctype,
                "baseUrl": base_url,
                "apiKey": api_key,
                "priority": priority,
                "provider": provider_alias or name,
            }
            if self.provider.get("id"):
                payload["id"] = self.provider["id"]
            # Call on_save callback if provided
            if callable(self.on_save):
                self.on_save(payload.get("id") or name, payload)
            self.dismiss(payload)
