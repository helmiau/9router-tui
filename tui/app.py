"""NineRouterTUI — main App (extracted from app.py)."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static, TabbedContent, TabPane, Select
from textual import on, work

try:
    from _version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "1.0.0"

from client import NinerouterClient, load_config_from_env_and_file, has_any_config
from tui.panes.overview import OverviewPane
from tui.panes.endpoints import EndpointsPane
from tui.panes.keys import KeysPane
from tui.panes.provider_connections import ProviderConnectionsPane
from tui.panes.provider_models import ProviderModelsPane
from tui.panes.nodes import NodesPane
from tui.panes.combos import CombosPane
from tui.panes.models import ModelsPane
from tui.panes.usage import UsagePane
from tui.panes.settings import SettingsPane
from tui.panes.pools import ProxyPoolsPane
from tui.panes.logs import LogsPane
from tui.panes.update import UpdatePane
from tui.screens.picker import ServerPickerScreen
from tui.screens.tui_config import TuiConfigScreen

class NineRouterTUI(App):
    CSS = """
    Screen { background: $background; }
    #overview-body, #endpoints-body, #prov-conn-detail, #prov-models-detail, #nodes-detail, #combos-detail, #models-detail, #keys-detail, #usage-body, #usage-detail, #settings-body {
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
    .hidden { display: none; }
    #settings-editor { padding: 1 1; border: solid $primary-background; margin: 1 0; height: auto; }
    #settings-editor-fields { padding: 1 0; }
    #settings-editor-status { padding: 0 1; height: auto; }
    """

    TITLE = "9Router — Terminal Dashboard"
    SUB_TITLE = "Standalone TUI (no omnexsync dependency)"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "switch_server", "Switch Server"),
        Binding("ctrl+c", "copy_detail", "Copy", show=False, priority=False),
        Binding("ctrl+shift+c", "copy_detail", "Copy Detail", show=False, priority=True),
        Binding("ctrl+a", "select_all_input", "Select All", show=False, priority=True),
        Binding("1", "tab('dashboard')", "Dashboard"),
        Binding("2", "tab('endpoint-keys')", "Endpoint & Key"),
        Binding("3", "tab('providers')", "Providers"),
        Binding("4", "tab('combos')", "Combos"),
        Binding("5", "tab('usage')", "Usage"),
        Binding("6", "tab('system')", "System"),
    ]

    def __init__(self, client: Optional[NinerouterClient] = None, **kw):
        super().__init__(**kw)
        self.client = client or NinerouterClient(load_config_from_env_and_file())
        self._detail_plain: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("[dim]Press 's' switch server • 'r' refresh • 1-6 tabs • q quit • Ctrl+Shift+C copy detail[/]", id="hint-bar")
        with TabbedContent(initial="dashboard"):
            # ── Tab 1: Dashboard (web: /dashboard home) ──
            with TabPane("Dashboard", id="dashboard"):
                with TabbedContent():
                    with TabPane("Health", id="dashboard-health"):
                        yield OverviewPane(self.client)
                    with TabPane("Profiles", id="dashboard-profiles"):
                        yield Static("[dim]Server profiles — press 's' to switch, or use Manage Servers below[/]", id="profiles-intro")
                        yield Horizontal(
                            Button("Switch Server", id="btn-profiles-switch", variant="primary"),
                            Button("Manage Servers", id="btn-profiles-servers", variant="default"),
                        )
                    with TabPane("TUI Config", id="dashboard-tui-config"):
                        yield Static("[dim]TUI Config — click Edit button below[/]", id="tui-config-intro")
                        yield Horizontal(
                            Button("Edit TUI Config", id="btn-tui-config-edit", variant="default"),
                            Button("Manage Servers", id="btn-tui-servers", variant="default"),
                        )
            # ── Tab 2: Endpoint & Key (web: /dashboard/endpoint) ──
            with TabPane("Endpoint & Key", id="endpoint-keys"):
                with TabbedContent():
                    with TabPane("Endpoints", id="ek-endpoints"):
                        yield EndpointsPane(self.client)
                    with TabPane("Keys", id="ek-keys"):
                        yield KeysPane(self.client)
            # ── Tab 3: Providers (web: /dashboard/providers) ──
            with TabPane("Providers", id="providers"):
                with TabbedContent():
                    with TabPane("Connections", id="providers-manage"):
                        yield ProviderConnectionsPane(self.client)
                    with TabPane("Available Models", id="providers-models"):
                        yield ProviderModelsPane(self.client)
                    with TabPane("Nodes", id="providers-nodes"):
                        yield NodesPane(self.client)
                    with TabPane("Models", id="providers-models-list"):
                        yield ModelsPane(self.client)
            # ── Tab 4: Combos (web: /dashboard/combos) ──
            with TabPane("Combos", id="combos"):
                yield CombosPane(self.client)
            # ── Tab 5: Usage (web: /dashboard/usage) ──
            with TabPane("Usage", id="usage"):
                with TabbedContent():
                    with TabPane("Stats", id="usage-stats"):
                        yield UsagePane(self.client)
                    with TabPane("Request Logs", id="usage-logs"):
                        yield LogsPane(self.client)
            # ── Tab 6: System (web: System section — proxy-pools, settings, update) ──
            with TabPane("System", id="system"):
                with TabbedContent():
                    with TabPane("Proxy Pools", id="system-pools"):
                        yield ProxyPoolsPane(self.client)
                    with TabPane("Settings", id="system-settings"):
                        yield SettingsPane(self.client)
                    with TabPane("Update & Docker", id="system-update"):
                        yield UpdatePane(self.client)
        yield Footer()

    def action_refresh(self) -> None:
        # refresh current tab
        try:
            tc = self.query_one(TabbedContent)
            active = tc.active
            # Direct panes (no sub-tabs)
            direct = {"combos": CombosPane}
            cls = direct.get(active)
            if cls:
                for w in self.query(cls):
                    if hasattr(w, "refresh_data"):
                        w.refresh_data()
                        break
                return
            # Tabs with nested sub-tabs — refresh the active sub-tab
            sub_map = {
                "dashboard": {
                    "dashboard-health": OverviewPane,
                },
                "endpoint-keys": {
                    "ek-endpoints": EndpointsPane,
                    "ek-keys": KeysPane,
                },
                "providers": {
                    "providers-manage": ProviderConnectionsPane,
                    "providers-models": ProviderModelsPane,
                    "providers-nodes": NodesPane,
                    "providers-models-list": ModelsPane,
                },
                "usage": {
                    "usage-stats": UsagePane,
                    "usage-logs": LogsPane,
                },
                "system": {
                    "system-pools": ProxyPoolsPane,
                    "system-settings": SettingsPane,
                    "system-update": UpdatePane,
                },
            }
            subs = sub_map.get(active)
            if not subs:
                return
            subtc = self.query_one(f"#{active} TabbedContent")
            sub = subtc.active
            sub_cls = subs.get(sub)
            if sub_cls:
                for w in self.query(sub_cls):
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
        cfg = NinerouterConfig(url=profile.url, api_key=profile.api_key, password=getattr(profile, "password", ""), timeout=profile.timeout)
        self.client = NinerouterClient(cfg)
        self.sub_title = f"{profile.name} — {profile.url}"
        for pane in self.query(OverviewPane):
            pane.client = self.client
        for pane in self.query(EndpointsPane):
            pane.client = self.client
        for pane in self.query(KeysPane):
            pane.client = self.client
        for pane in self.query(ProviderConnectionsPane):
            pane.client = self.client
        for pane in self.query(ProviderModelsPane):
            pane.client = self.client
        for pane in self.query(NodesPane):
            pane.client = self.client
        for pane in self.query(CombosPane):
            pane.client = self.client
        for pane in self.query(ModelsPane):
            pane.client = self.client
        for pane in self.query(UsagePane):
            pane.client = self.client
        for pane in self.query(SettingsPane):
            pane.client = self.client
        for pane in self.query(ProxyPoolsPane):
            pane.client = self.client
        for pane in self.query(LogsPane):
            pane.client = self.client
        for pane in self.query(UpdatePane):
            pane.client = self.client
        self.action_refresh()
        self.notify(f"Switched to {profile.name} — {profile.url}", timeout=3)

    # ── Clipboard helpers ──
    def _focused_input(self):
        try:
            w = self.focused
            from textual.widgets import Input
            if isinstance(w, Input):
                return w
        except Exception:
            pass
        return None

    def _copy_text(self, text: str) -> None:
        if not text or text.strip() in ("—", ""):
            self.notify("Nothing to copy", severity="warning", timeout=2)
            return
        try:
            # OSC 52 — works in most terminals (Windows Terminal, WezTerm, kitty, etc.)
            self.copy_to_clipboard(text)
            # System clipboard fallback (Windows clip, Linux xclip/xsel, or pyperclip)
            try:
                import subprocess, shutil
                if shutil.which("clip"):
                    subprocess.run(["clip"], input=text.encode("utf-8"), timeout=2, check=False)
                elif shutil.which("xclip"):
                    subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), timeout=2, check=False)
                elif shutil.which("xsel"):
                    subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode("utf-8"), timeout=2, check=False)
                else:
                    try:
                        import pyperclip  # type: ignore
                        pyperclip.copy(text)
                    except Exception:
                        pass
            except Exception:
                pass
            preview = text[:60].replace("\n", " ") + ("…" if len(text) > 60 else "")
            self.notify(f"Copied: {preview}", timeout=2)
        except Exception as e:
            self.notify(f"Copy failed: {e}", severity="error", timeout=2)

    def _set_detail_plain(self, key: str, plain: str) -> None:
        """Store plain text for a detail pane so copy works without markup parsing.

        `key` is the active sub-tab id (e.g. 'usage-logs', 'providers-nodes').
        """
        try:
            self._detail_plain[key] = plain
            # also stash on the Static widget for direct access
            sel_map = {
                "dashboard": "#overview-body",
                "dashboard-health": "#overview-body",
                "endpoint-keys": "#endpoints-body",
                "ek-endpoints": "#endpoints-body",
                "ek-keys": "#keys-detail",
                "providers": "#prov-conn-detail",
                "providers-manage": "#prov-conn-detail",
                "providers-models": "#prov-models-detail",
                "providers-nodes": "#nodes-detail",
                "providers-models-list": "#models-detail",
                "combos": "#combos-detail",
                "usage": "#usage-detail",
                "usage-stats": "#usage-detail",
                "usage-logs": "#logs-detail",
                "system": "#settings-body",
                "system-pools": "#pools-detail",
                "system-settings": "#settings-body",
                "system-update": "#update-log",
            }
            sel = sel_map.get(key)
            if sel:
                try:
                    w = self.query_one(sel, Static)
                    w._plain_text = plain  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception:
            pass

    def _get_detail_text(self) -> str:
        """Get plain text from the active pane's detail Static.

        Resolves the active sub-tab (if any) so copy works for nested
        TabbedContent (e.g. Usage > Request Logs, Providers > Nodes).
        """
        try:
            tc = self.query_one(TabbedContent)
            active = tc.active or ""
            # resolve active nested sub-tab
            nested_map = {
                "dashboard": ("#dashboard TabbedContent", "dashboard-health"),
                "endpoint-keys": ("#endpoint-keys TabbedContent", "ek-endpoints"),
                "providers": ("#providers TabbedContent", "providers-manage"),
                "usage": ("#usage TabbedContent", "usage-stats"),
                "system": ("#system TabbedContent", "system-pools"),
            }
            sub = None
            if active in nested_map:
                sel, default = nested_map[active]
                try:
                    subtc = self.query_one(sel)
                    sub = subtc.active or default
                except Exception:
                    sub = default
            lookup = sub or active
            # 1) stored plain text (most reliable)
            if lookup in self._detail_plain and self._detail_plain[lookup]:
                return self._detail_plain[lookup]
            pane_ids = {
                "dashboard": "#overview-body",
                "dashboard-health": "#overview-body",
                "endpoint-keys": "#endpoints-body",
                "ek-endpoints": "#endpoints-body",
                "ek-keys": "#keys-detail",
                "providers": "#prov-conn-detail",
                "providers-manage": "#prov-conn-detail",
                "providers-models": "#prov-models-detail",
                "providers-nodes": "#nodes-detail",
                "providers-models-list": "#models-detail",
                "combos": "#combos-detail",
                "usage": "#usage-detail",
                "usage-stats": "#usage-detail",
                "usage-logs": "#logs-detail",
                "system": "#settings-body",
                "system-pools": "#pools-detail",
                "system-settings": "#settings-body",
                "system-update": "#update-log",
            }
            sel = pane_ids.get(lookup)
            if sel:
                w = self.query_one(sel, Static)
                # 2) widget stashed plain
                if hasattr(w, "_plain_text") and getattr(w, "_plain_text"):
                    return str(getattr(w, "_plain_text"))
                # 3) fallback: try to extract from content/visual
                for attr in ("_plain_text", "_content", "__content"):
                    try:
                        v = getattr(w, attr, "")
                        if v and str(v).strip() not in ("", "None"):
                            txt = str(v)
                            import re
                            plain = re.sub(r"\[/?[^\]]*\]", "", txt)
                            if plain.strip():
                                return plain.strip()
                    except Exception:
                        continue
                try:
                    txt = str(w.content) if hasattr(w, "content") else ""
                    if txt and txt.strip() not in ("", "None"):
                        import re
                        return re.sub(r"\[/?[^\]]*\]", "", txt).strip()
                except Exception:
                    pass
        except Exception:
            pass
        return ""

    def action_copy_detail(self) -> None:
        """Copy: if Input focused with selection, copy selection; else copy detail pane."""
        inp = self._focused_input()
        if inp is not None:
            try:
                if inp.selected_text:
                    inp.action_copy()
                    self.notify(f"Copied: {inp.selected_text[:60]}", timeout=2)
                    return
                # no selection but Input has value — copy whole value
                if inp.value and inp.has_focus:
                    self._copy_text(inp.value)
                    return
            except Exception:
                pass
        txt = self._get_detail_text()
        if txt:
            import re
            plain = re.sub(r"\[/?[^\]]*\]", "", txt)
            self._copy_text(plain.strip())
        else:
            self.notify("Nothing to copy — select a row first", severity="warning", timeout=2)

    def action_select_all_input(self) -> None:
        inp = self._focused_input()
        if inp is not None:
            try:
                inp.selection = (0, len(inp.value))
                return
            except Exception:
                pass
        self.notify("Select all: focus an input first", severity="warning", timeout=2)

    def on_mount(self) -> None:
        from client import has_any_config
        # Check if auto-login is enabled in config.toml [ui] auto_login
        auto_login = True
        try:
            from client import _get_app_dir
            import pathlib
            cfg_path = pathlib.Path(_get_app_dir()) / "config.toml"
            if cfg_path.exists():
                try:
                    import tomllib
                    with open(cfg_path, "rb") as f:
                        data = tomllib.load(f)
                except ImportError:
                    import tomli as tomllib  # type: ignore
                    with open(cfg_path, "rb") as f:
                        data = tomllib.load(f)
                auto_login = data.get("ui", {}).get("auto_login", True)
                if isinstance(auto_login, str):
                    auto_login = auto_login.lower() not in ("false", "0", "no", "off")
        except Exception:
            pass
        if auto_login:
            self._try_auto_login()
        if not has_any_config():
            self.call_later(lambda: self.push_screen(ServerPickerScreen(self.client, self._on_server_picked)))

    def _try_auto_login(self) -> bool:
        """Try to auto-login to default server. Returns True if succeeded."""
        try:
            from client import _load_servers_from_file, NinerouterConfig, NinerouterClient
            servers = _load_servers_from_file()
            if not servers:
                return False
            default_profile = None
            for s in servers:
                if s.url.rstrip("/") == self.client.base.rstrip("/"):
                    default_profile = s
                    break
            if not default_profile:
                default_profile = servers[0]
            if not default_profile:
                return False
            cfg = NinerouterConfig(url=default_profile.url, api_key=default_profile.api_key, timeout=default_profile.timeout)
            try:
                from client import _get_app_dir
                import pathlib
                cfg_path = pathlib.Path(_get_app_dir()) / "config.toml"
                if cfg_path.exists():
                    try:
                        import tomllib
                        with open(cfg_path, "rb") as f:
                            data = tomllib.load(f)
                    except ImportError:
                        import tomli as tomllib  # type: ignore
                        with open(cfg_path, "rb") as f:
                            data = tomllib.load(f)
                    srv = data.get("server", {})
                    if srv.get("password"):
                        cfg.password = srv["password"]
            except Exception:
                pass
            self.client = NinerouterClient(cfg)
            self.sub_title = f"{default_profile.name} — {default_profile.url}"
            from tui.panes.overview import OverviewPane
            from tui.panes.endpoints import EndpointsPane
            from tui.panes.keys import KeysPane
            from tui.panes.provider_connections import ProviderConnectionsPane
            from tui.panes.provider_models import ProviderModelsPane
            from tui.panes.nodes import NodesPane
            from tui.panes.combos import CombosPane
            from tui.panes.models import ModelsPane
            from tui.panes.usage import UsagePane
            from tui.panes.settings import SettingsPane
            from tui.panes.pools import ProxyPoolsPane
            from tui.panes.logs import LogsPane
            from tui.panes.update import UpdatePane
            for pane in self.query(OverviewPane):
                pane.client = self.client
            for pane in self.query(EndpointsPane):
                pane.client = self.client
            for pane in self.query(KeysPane):
                pane.client = self.client
            for pane in self.query(ProviderConnectionsPane):
                pane.client = self.client
            for pane in self.query(ProviderModelsPane):
                pane.client = self.client
            for pane in self.query(NodesPane):
                pane.client = self.client
            for pane in self.query(CombosPane):
                pane.client = self.client
            for pane in self.query(ModelsPane):
                pane.client = self.client
            for pane in self.query(UsagePane):
                pane.client = self.client
            for pane in self.query(SettingsPane):
                pane.client = self.client
            for pane in self.query(ProxyPoolsPane):
                pane.client = self.client
            for pane in self.query(LogsPane):
                pane.client = self.client
            for pane in self.query(UpdatePane):
                pane.client = self.client
            self.notify(f"Auto-login: {default_profile.name} — {default_profile.url}", timeout=2)
            return True
        except Exception:
            return False

    @on(Button.Pressed, "#btn-profiles-switch")
    def on_profiles_switch(self) -> None:
        self.action_switch_server()

    @on(Button.Pressed, "#btn-profiles-servers")
    def on_profiles_servers(self) -> None:
        from tui.screens.tui_servers import TuiServersScreen
        self.push_screen(TuiServersScreen(self._on_tui_servers_done))

    @on(Button.Pressed, "#btn-tui-config-edit")
    def on_tui_config_edit(self) -> None:
        self.push_screen(TuiConfigScreen(self._on_tui_config_done))

    def _on_tui_config_done(self, ok: bool) -> None:
        if ok:
            self.notify("TUI config saved", timeout=2)
            self.action_refresh()

    @on(Button.Pressed, "#btn-tui-servers")
    def on_tui_servers(self) -> None:
        from tui.screens.tui_servers import TuiServersScreen
        self.push_screen(TuiServersScreen(self._on_tui_servers_done))

    def _on_tui_servers_done(self, ok: bool) -> None:
        if ok:
            self.notify("Servers updated", timeout=2)
            self.action_refresh()


# ── Server Picker (Modal) ──

