"""Thinking level selection screen."""
from __future__ import annotations

from typing import List, Optional

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select, Static

from client import NinerouterClient


class ThinkingLevelScreen(ModalScreen):
    DEFAULT_CSS = """
    ThinkingLevelScreen { align: center middle; }
    #thinking-container { width: 60; height: auto; background: $surface; border: thick $primary; padding: 1 2; }
    #thinking-container > Horizontal { margin-top: 1; }
    """

    def __init__(self, client: NinerouterClient, provider_id: str, model_id: str, levels: List[str], on_save, **kw):
        super().__init__(**kw)
        self.client = client
        self.provider_id = provider_id
        self.model_id = model_id
        self.levels = levels or ["auto", "high", "medium", "low", "none"]
        self.on_save = on_save

    def compose(self) -> ComposeResult:
        with Vertical(id="thinking-container"):
            yield Static(f"Set thinking level for {self.model_id}")
            yield Label("Thinking level:")
            yield Select(
                options=[(lvl, lvl) for lvl in self.levels],
                value="auto" if "auto" in self.levels else self.levels[0],
                id="sel-thinking-level",
                allow_blank=False,
            )
            with Horizontal():
                yield Button("Save", id="btn-thinking-save", variant="success")
                yield Button("Cancel", id="btn-thinking-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-thinking-cancel":
            self.dismiss(None)
            return
        if event.button.id == "btn-thinking-save":
            level = self.query_one("#sel-thinking-level", Select).value
            if callable(self.on_save):
                self.on_save(self.provider_id, self.model_id, level)
            self.dismiss(level)
