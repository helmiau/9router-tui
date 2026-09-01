"""TUI Config editor — edits config.toml [server] + [ui] + [display]."""
from __future__ import annotations

from typing import Any, Dict, Optional

from textual import on
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, Select, Checkbox


class TuiConfigScreen(ModalScreen):
    DEFAULT_CSS = """
    TuiConfigScreen { align: center middle; }
    #tui-config-container { width: 76; height: auto; max-height: 38; background: $surface; border: thick $primary; padding: 1 2; }
    #tui-config-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #tui-config-fields Input, #tui-config-fields Select { margin: 1 0; }
    #tui-config-status { height: auto; margin: 1 0; }
    """

    def __init__(self, callback, **kw):
        super().__init__(**kw)
        self._cb = callback
        self._data: Dict[str, Any] = {}

    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Input, Button, Select, Checkbox
        # Load current config
        try:
            from client import _get_app_dir
            import pathlib
            cfg_path = pathlib.Path(_get_app_dir()) / "config.toml"
            if cfg_path.exists():
                try:
                    import tomllib
                    with open(cfg_path, "rb") as f:
                        self._data = tomllib.load(f)
                except ImportError:
                    import tomli as tomllib  # type: ignore
                    with open(cfg_path, "rb") as f:
                        self._data = tomllib.load(f)
        except Exception:
            pass
        srv = self._data.get("server", {})
        ui = self._data.get("ui", {})
        disp = self._data.get("display", {})
        with Vertical(id="tui-config-container"):
            yield Label("TUI Config — config.toml", id="tui-config-title")
            with Vertical(id="tui-config-fields"):
                yield Label("[server] url")
                yield Input(value=srv.get("url", "http://localhost:20128"), placeholder="http://localhost:20128", id="cfg-url")
                yield Label("[server] api_key")
                yield Input(value=srv.get("api_key", ""), placeholder="sk-...", id="cfg-api-key", password=False)
                yield Label("[server] password (for /api/* cookie auth)")
                yield Input(value=srv.get("password", ""), placeholder="123456", id="cfg-password", password=False)
                yield Label("[server] timeout (seconds)")
                yield Input(value=str(srv.get("timeout", 15)), placeholder="15", id="cfg-timeout")
                yield Label("[ui] auto_login (auto-login to default server on start)")
                yield Checkbox(value=bool(ui.get("auto_login", True)), label="Auto-login", id="cfg-auto-login")
                yield Label("[ui] theme")
                yield Select([("dark", "dark"), ("light", "light"), ("auto", "auto")], value=ui.get("theme", "dark"), id="cfg-theme", allow_blank=True)
                yield Label("[ui] default_page")
                # Migrate legacy default_page values to new tab IDs
                _legacy_map = {
                    "overview": "dashboard",
                    "endpoint-keys": "endpoint-keys",
                    "providers": "providers",
                    "nodes": "providers",
                    "combos": "combos",
                    "models": "providers",
                    "keys": "endpoint-keys",
                    "usage": "usage",
                    "settings": "system",
                    "pools": "system",
                    "logs": "system",
                    "update": "system",
                }
                _raw_default = ui.get("default_page", "dashboard")
                _migrated_default = _legacy_map.get(_raw_default, "dashboard")
                yield Select([("dashboard", "dashboard"), ("endpoint-keys", "Endpoint & Key"), ("providers", "providers"), ("combos", "combos"), ("usage", "usage"), ("system", "system")], value=_migrated_default, id="cfg-default-page", allow_blank=True)
                yield Label("[display] show_secrets")
                yield Checkbox(value=bool(disp.get("show_secrets", False)), label="Show secrets", id="cfg-show-secrets")
                yield Label("[display] page_size")
                yield Input(value=str(disp.get("page_size", 20)), placeholder="20", id="cfg-page-size")
            yield Static("", id="tui-config-status")
            with Horizontal():
                yield Button("Save", id="btn-tui-cfg-save", variant="primary")
                yield Button("Cancel", id="btn-tui-cfg-cancel", variant="default")

    @on(Button.Pressed, "#btn-tui-cfg-save")
    def on_save(self) -> None:
        try:
            from client import _get_app_dir
            import pathlib
            cfg_path = pathlib.Path(_get_app_dir()) / "config.toml"
            # Read existing to preserve [[servers]] etc.
            existing: Dict[str, Any] = {}
            if cfg_path.exists():
                try:
                    import tomllib
                    with open(cfg_path, "rb") as f:
                        existing = tomllib.load(f)
                except ImportError:
                    import tomli as tomllib  # type: ignore
                    with open(cfg_path, "rb") as f:
                        existing = tomllib.load(f)
            # Update [server]
            url = self.query_one("#cfg-url", Input).value.strip()
            api_key = self.query_one("#cfg-api-key", Input).value.strip()
            password = self.query_one("#cfg-password", Input).value.strip()
            timeout_s = self.query_one("#cfg-timeout", Input).value.strip()
            try:
                timeout = int(timeout_s) if timeout_s else 15
            except Exception:
                self.query_one("#tui-config-status", Static).update("[red]Invalid timeout[/]")
                return
            auto_login = self.query_one("#cfg-auto-login", Checkbox).value
            theme = self.query_one("#cfg-theme", Select).value or "dark"
            default_page = self.query_one("#cfg-default-page", Select).value or "dashboard"
            show_secrets = self.query_one("#cfg-show-secrets", Checkbox).value
            page_size_s = self.query_one("#cfg-page-size", Input).value.strip()
            try:
                page_size = int(page_size_s) if page_size_s else 20
            except Exception:
                self.query_one("#tui-config-status", Static).update("[red]Invalid page_size[/]")
                return
            existing["server"] = {"url": url, "api_key": api_key, "password": password, "timeout": timeout}
            existing["ui"] = {**existing.get("ui", {}), "theme": theme, "auto_login": bool(auto_login), "default_page": default_page}
            # Preserve refresh_interval if exists
            if "refresh_interval" in existing.get("ui", {}):
                existing["ui"]["refresh_interval"] = existing["ui"]["refresh_interval"]
            existing["display"] = {"show_secrets": bool(show_secrets), "page_size": page_size}
            # Write TOML — simple manual writer to preserve [[servers]]
            servers = existing.get("servers", [])
            # Build TOML text
            lines = []
            lines.append("[server]")
            lines.append(f'url = "{url}"')
            lines.append(f'api_key = "{api_key}"')
            lines.append(f'password = "{password}"')
            lines.append(f'timeout = {timeout}')
            lines.append("")
            lines.append("[ui]")
            for k, v in existing["ui"].items():
                if isinstance(v, bool):
                    lines.append(f'{k} = {str(v).lower()}')
                elif isinstance(v, int):
                    lines.append(f'{k} = {v}')
                else:
                    lines.append(f'{k} = "{v}"')
            lines.append("")
            lines.append("[display]")
            lines.append(f'show_secrets = {str(bool(show_secrets)).lower()}')
            lines.append(f'page_size = {page_size}')
            if servers:
                lines.append("")
                for s in servers:
                    lines.append("[[servers]]")
                    for sk, sv in s.items():
                        if isinstance(sv, bool):
                            lines.append(f'{sk} = {str(sv).lower()}')
                        elif isinstance(sv, int):
                            lines.append(f'{sk} = {sv}')
                        else:
                            lines.append(f'{sk} = "{sv}"')
                    lines.append("")
            cfg_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.dismiss(True)
            self._cb(True)
        except Exception as e:
            try:
                self.query_one("#tui-config-status", Static).update(f"[red]{e}[/]")
            except Exception:
                pass

    @on(Button.Pressed, "#btn-tui-cfg-cancel")
    def on_cancel(self) -> None:
        self.dismiss(False)
        self._cb(False)
