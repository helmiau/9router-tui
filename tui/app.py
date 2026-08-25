"""NineRouterTUI — main App (extracted from app.py)."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static, TabbedContent, TabPane, Select
from textual import on, work

try:
    from _version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "1.0.0"

from client import NinerouterClient, load_config_from_env_and_file, has_any_config
from tui.panes.overview import OverviewPane
from tui.panes.providers import ProvidersPane
from tui.panes.nodes import NodesPane
from tui.panes.combos import CombosPane
from tui.panes.models import ModelsPane
from tui.panes.keys import KeysPane
from tui.panes.usage import UsagePane
from tui.panes.settings import SettingsPane
from tui.panes.pools import ProxyPoolsPane
from tui.panes.logs import LogsPane
from tui.panes.update import UpdatePane
from tui.screens.picker import ServerPickerScreen

class NineRouterTUI(App):
    CSS = """
    Screen { background: $background; }
    #overview-body, #providers-detail, #nodes-detail, #combos-detail, #models-detail, #keys-detail, #usage-body, #usage-detail, #settings-body {
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
        Binding("1", "tab('overview')", "Overview"),
        Binding("2", "tab('providers')", "Providers"),
        Binding("3", "tab('nodes')", "Nodes"),
        Binding("4", "tab('combos')", "Combos"),
        Binding("5", "tab('models')", "Models"),
        Binding("6", "tab('keys')", "Keys"),
        Binding("7", "tab('usage')", "Usage"),
        Binding("8", "tab('settings')", "Settings"),
        Binding("9", "tab('update')", "Update"),
        Binding("0", "tab('pools')", "Pools"),
        Binding("minus", "tab('logs')", "Logs"),
    ]

    def __init__(self, client: Optional[NinerouterClient] = None, **kw):
        super().__init__(**kw)
        self.client = client or NinerouterClient(load_config_from_env_and_file())
        self._detail_plain: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("[dim]Press 's' switch server • 'r' refresh • 1-9 tabs • 0 Pools • - Logs • q quit • Ctrl+Shift+C copy detail[/]", id="hint-bar")
        with TabbedContent(initial="overview"):
            with TabPane("Overview", id="overview"):
                yield OverviewPane(self.client)
            with TabPane("Providers", id="providers"):
                yield ProvidersPane(self.client)
            with TabPane("Nodes", id="nodes"):
                yield NodesPane(self.client)
            with TabPane("Combos", id="combos"):
                yield CombosPane(self.client)
            with TabPane("Models", id="models"):
                yield ModelsPane(self.client)
            with TabPane("Keys", id="keys"):
                yield KeysPane(self.client)
            with TabPane("Usage", id="usage"):
                yield UsagePane(self.client)
            with TabPane("Settings", id="settings"):
                yield SettingsPane(self.client)
            with TabPane("Pools", id="pools"):
                yield ProxyPoolsPane(self.client)
            with TabPane("Logs", id="logs"):
                yield LogsPane(self.client)
            with TabPane("Update", id="update"):
                yield UpdatePane(self.client)
        yield Footer()

    def action_refresh(self) -> None:
        # refresh current tab
        try:
            tc = self.query_one(TabbedContent)
            active = tc.active
            pane_map = {
                "overview": OverviewPane,
                "providers": ProvidersPane,
                "nodes": NodesPane,
                "combos": CombosPane,
                "models": ModelsPane,
                "keys": KeysPane,
                "usage": UsagePane,
                "settings": SettingsPane,
                "pools": ProxyPoolsPane,
                "logs": LogsPane,
                "update": UpdatePane,
            }
            cls = pane_map.get(active)
            if cls:
                for w in self.query(cls):
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
        cfg = NinerouterConfig(url=profile.url, api_key=profile.api_key, timeout=profile.timeout)
        self.client = NinerouterClient(cfg)
        self.sub_title = f"{profile.name} — {profile.url}"
        for pane in self.query(OverviewPane):
            pane.client = self.client
        for pane in self.query(ProvidersPane):
            pane.client = self.client
        for pane in self.query(NodesPane):
            pane.client = self.client
        for pane in self.query(CombosPane):
            pane.client = self.client
        for pane in self.query(ModelsPane):
            pane.client = self.client
        for pane in self.query(KeysPane):
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
        """Store plain text for a detail pane so copy works without markup parsing."""
        try:
            self._detail_plain[key] = plain
            # also stash on the Static widget for direct access
            sel_map = {
                "overview": "#overview-body",
                "providers": "#providers-detail",
                "nodes": "#nodes-detail",
                "combos": "#combos-detail",
                "models": "#models-detail",
                "keys": "#keys-detail",
                "usage": "#usage-detail",
                "settings": "#settings-body",
                "update": "#update-log",
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
        """Get plain text from the active pane's detail Static."""
        try:
            tc = self.query_one(TabbedContent)
            active = tc.active or ""
            # 1) stored plain text (most reliable)
            if active in self._detail_plain and self._detail_plain[active]:
                return self._detail_plain[active]
            pane_ids = {
                "overview": "#overview-body",
                "providers": "#providers-detail",
                "nodes": "#nodes-detail",
                "combos": "#combos-detail",
                "models": "#models-detail",
                "keys": "#keys-detail",
                "usage": "#usage-detail",
                "settings": "#settings-body",
                "update": "#update-log",
            }
            sel = pane_ids.get(active)
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
            from tui.panes.providers import ProvidersPane
            from tui.panes.nodes import NodesPane
            from tui.panes.combos import CombosPane
            from tui.panes.models import ModelsPane
            from tui.panes.keys import KeysPane
            from tui.panes.usage import UsagePane
            from tui.panes.settings import SettingsPane
            from tui.panes.pools import ProxyPoolsPane
            from tui.panes.logs import LogsPane
            from tui.panes.update import UpdatePane
            for pane in self.query(OverviewPane):
                pane.client = self.client
            for pane in self.query(ProvidersPane):
                pane.client = self.client
            for pane in self.query(NodesPane):
                pane.client = self.client
            for pane in self.query(CombosPane):
                pane.client = self.client
            for pane in self.query(ModelsPane):
                pane.client = self.client
            for pane in self.query(KeysPane):
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


# ── Server Picker (Modal) ──

