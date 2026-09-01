"""Provider strategy editor screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Checkbox

from client import NinerouterClient


class ProviderStrategyScreen(ModalScreen):
    DEFAULT_CSS = """
    ProviderStrategyScreen { align: center middle; }
    #strat-container { width: 70; height: auto; background: $surface; border: thick $primary; padding: 1 2; }
    #strat-container > Horizontal { margin-top: 1; }
    """

    def __init__(self, client: NinerouterClient, provider: dict, proxy_pools: list[dict], on_save, **kw):
        super().__init__(**kw)
        self.client = client
        self.provider = provider
        self.proxy_pools = proxy_pools or []
        self.on_save = on_save
        self._strategy = dict((provider.get("strategy") or {}))

    def compose(self) -> ComposeResult:
        strat = self._strategy
        with Vertical(id="strat-container"):
            yield Static(f"Strategy: {self.provider.get('name')} ({self.provider.get('id')})")
            yield Checkbox("Round Robin", value=strat.get("roundRobin", False), id="chk-round-robin")
            yield Label("Sticky Round-Robin Limit:")
            yield Input(placeholder="0 = unlimited", value=str(strat.get("stickyRoundRobinLimit", "") or ""), id="inp-sticky-limit")
            yield Label("Proxy Pool:")
            pool_options = [(p.get("name", p.get("id")), p.get("name", p.get("id"))) for p in self.proxy_pools]
            pool_options.insert(0, ("— none —", ""))
            yield Select(options=pool_options, value=strat.get("proxyPool") or "", id="sel-proxy-pool", allow_blank=False)
            yield Label("Fallback Strategy:")
            yield Select(
                options=[("none", "none"), ("next", "next"), ("all", "all")],
                value=strat.get("fallbackStrategy") or "none",
                id="sel-fallback",
                allow_blank=False,
            )
            with Horizontal():
                yield Button("Save", id="btn-strat-save", variant="success")
                yield Button("Cancel", id="btn-strat-cancel", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-strat-cancel":
            self.dismiss(None)
            return
        if event.button.id == "btn-strat-save":
            rr = bool(self.query_one("#chk-round-robin", Checkbox).value)
            sticky_raw = self.query_one("#inp-sticky-limit", Input).value.strip()
            try:
                sticky = int(sticky_raw) if sticky_raw else 0
            except ValueError:
                sticky = 0
            proxy = self.query_one("#sel-proxy-pool", Select).value or ""
            fallback = self.query_one("#sel-fallback", Select).value or "none"
            strategy = {
                "roundRobin": rr,
                "stickyRoundRobinLimit": sticky,
                "proxyPool": proxy,
                "fallbackStrategy": fallback,
            }
            if callable(self.on_save):
                self.on_save(self.provider.get("id"), strategy)
            self.dismiss(strategy)

    def on_select_changed(self, event: Select.Changed) -> None:
        # no-op, kept for future validation
        pass
