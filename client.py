"""
9Router TUI — API Client
Covers all management APIs from 9router-master/src/app/api/*.
No dependency on omnexsync; standalone.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

def _get_app_dir() -> str:
    """Return writable app dir — exe dir when frozen, else file dir."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller onefile: sys.executable is dist/9Router-TUI.exe
        return os.path.dirname(os.path.abspath(sys.executable))
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


@dataclass
class NinerouterConfig:
    url: str = "http://localhost:20128"
    api_key: str = ""
    timeout: int = 15
    password: str = ""  # dashboard cookie auth (optional)
    name: str = ""  # display name for this server profile


@dataclass
class ServerProfile:
    name: str
    url: str
    api_key: str = ""
    timeout: int = 15
    description: str = ""
    password: str = ""  # dashboard cookie auth (optional)
    # ── remote Docker / SSH (for external VPS) ──
    ssh_host: str = ""  # e.g. "1.2.3.4" or "vps.example.com"
    ssh_user: str = ""  # e.g. "root" or "ubuntu"
    ssh_port: int = 22
    ssh_key: str = ""  # path to private key, e.g. "~/.ssh/id_rsa"
    ssh_password: str = ""  # optional, not recommended
    compose_path: str = ""  # remote path to docker-compose.yml, e.g. "/opt/9router/docker-compose.yml"
    install_method: str = ""  # override auto-detect: npm|source|docker

    def is_remote(self) -> bool:
        return bool(self.ssh_host.strip())

    def ssh_target(self) -> str:
        if not self.ssh_host:
            return ""
        user = self.ssh_user or "root"
        return f"{user}@{self.ssh_host}:{self.ssh_port}"


class NinerouterClient:
    """Thin wrapper over 9Router REST APIs."""

    def __init__(self, cfg: NinerouterConfig):
        self.cfg = cfg
        self.base = cfg.url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        if cfg.api_key:
            self.session.headers.update({"Authorization": f"Bearer {cfg.api_key}"})
        # Cookie auth (if password login needed)
        self._cookies: Dict[str, str] = {}
        # Auto-login if password is set
        if cfg.password:
            try:
                self.login(cfg.password)
            except Exception:
                pass

    # ── helpers ──
    def _url(self, path: str) -> str:
        return f"{self.base}{path}"

    def _request_with_relogin(self, method: str, path: str, **kw) -> requests.Response:
        """Do request, if 401 and password is set, try re-login once."""
        kw.setdefault("timeout", self.cfg.timeout)
        func = getattr(self.session, method)
        r = func(self._url(path), cookies=self._cookies, **kw)
        if r.status_code == 401 and self.cfg.password:
            try:
                if self.login(self.cfg.password):
                    r = func(self._url(path), cookies=self._cookies, **kw)
            except Exception:
                pass
        return r

    def _get(self, path: str, **kw) -> requests.Response:
        return self._request_with_relogin("get", path, **kw)

    def _post(self, path: str, **kw) -> requests.Response:
        return self._request_with_relogin("post", path, **kw)

    def _put(self, path: str, **kw) -> requests.Response:
        return self._request_with_relogin("put", path, **kw)

    def _patch(self, path: str, **kw) -> requests.Response:
        return self._request_with_relogin("patch", path, **kw)

    def _delete(self, path: str, **kw) -> requests.Response:
        return self._request_with_relogin("delete", path, **kw)

    # ── health ──
    def health(self) -> Dict[str, Any]:
        r = self._get("/api/health")
        r.raise_for_status()
        return r.json()

    # ── providers (connections) ──
    def list_providers(self) -> List[Dict[str, Any]]:
        r = self._get("/api/providers")
        r.raise_for_status()
        return r.json().get("connections", r.json().get("providers", []))

    def get_provider(self, provider_id: str) -> Dict[str, Any]:
        r = self._get(f"/api/providers/{provider_id}")
        r.raise_for_status()
        return r.json()

    def create_provider(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._post("/api/providers", json=payload)
        r.raise_for_status()
        return r.json()

    def update_provider(self, provider_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._put(f"/api/providers/{provider_id}", json=payload)
        r.raise_for_status()
        return r.json()

    def delete_provider(self, provider_id: str) -> Dict[str, Any]:
        r = self._delete(f"/api/providers/{provider_id}")
        r.raise_for_status()
        return r.json() if r.text else {}

    def test_providers(self, mode: str = "all", provider_id: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"mode": mode}
        if provider_id:
            body["providerId"] = provider_id
        r = self._post("/api/providers/test-batch", json=body)
        r.raise_for_status()
        return r.json()

    # ── provider nodes ──
    def list_nodes(self) -> List[Dict[str, Any]]:
        r = self._get("/api/provider-nodes")
        r.raise_for_status()
        return r.json().get("nodes", [])

    def create_node(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._post("/api/provider-nodes", json=payload)
        r.raise_for_status()
        return r.json()

    def update_node(self, node_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._put(f"/api/provider-nodes/{node_id}", json=payload)
        r.raise_for_status()
        return r.json()

    def delete_node(self, node_id: str) -> Dict[str, Any]:
        r = self._delete(f"/api/provider-nodes/{node_id}")
        r.raise_for_status()
        return r.json() if r.text else {}

    # ── combos ──
    def list_combos(self) -> List[Dict[str, Any]]:
        r = self._get("/api/combos")
        r.raise_for_status()
        return r.json().get("combos", [])

    def create_combo(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._post("/api/combos", json=payload)
        r.raise_for_status()
        return r.json()

    def update_combo(self, combo_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._put(f"/api/combos/{combo_id}", json=payload)
        r.raise_for_status()
        return r.json()

    def delete_combo(self, combo_id: str) -> Dict[str, Any]:
        r = self._delete(f"/api/combos/{combo_id}")
        r.raise_for_status()
        return r.json() if r.text else {}

    # ── models / aliases ──
    def list_models(self) -> Dict[str, Any]:
        r = self._get("/api/models")
        r.raise_for_status()
        return r.json()

    def list_v1_models(self) -> Dict[str, Any]:
        r = self._get("/v1/models")
        r.raise_for_status()
        return r.json()

    def get_model_aliases(self) -> Dict[str, Any]:
        r = self._get("/api/models/alias")
        r.raise_for_status()
        return r.json()

    def set_model_alias(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._post("/api/models/alias", json=payload)
        r.raise_for_status()
        return r.json()

    def delete_model_alias(self, alias: str) -> Dict[str, Any]:
        r = self._delete(f"/api/models/alias/{alias}")
        r.raise_for_status()
        return r.json() if r.text else {}

    # ── keys ──
    def list_keys(self) -> List[Dict[str, Any]]:
        r = self._get("/api/keys")
        r.raise_for_status()
        data = r.json()
        return data.get("keys", data if isinstance(data, list) else [])

    def create_key(self, name: str) -> Dict[str, Any]:
        r = self._post("/api/keys", json={"name": name})
        r.raise_for_status()
        return r.json()

    def update_key(self, key_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._put(f"/api/keys/{key_id}", json=payload)
        r.raise_for_status()
        return r.json() if r.text else {}

    def delete_key(self, key_id: str) -> Dict[str, Any]:
        r = self._delete(f"/api/keys/{key_id}")
        r.raise_for_status()
        return r.json() if r.text else {}

    # ── settings ──
    def get_settings(self) -> Dict[str, Any]:
        r = self._get("/api/settings")
        r.raise_for_status()
        return r.json()

    def patch_settings(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._patch("/api/settings", json=payload)
        r.raise_for_status()
        return r.json()

    # ── usage ──
    def get_usage_stats(self, period: str = "7d") -> Dict[str, Any]:
        r = self._get(f"/api/usage/stats?period={period}")
        r.raise_for_status()
        return r.json()

    def get_usage_history(self, limit: int = 50) -> Dict[str, Any]:
        r = self._get(f"/api/usage/history?limit={limit}")
        r.raise_for_status()
        return r.json()

    def get_usage_chart(self, period: str = "7d") -> Dict[str, Any]:
        r = self._get(f"/api/usage/chart?period={period}")
        r.raise_for_status()
        return r.json()

    def get_request_logs(self, limit: int = 50) -> Dict[str, Any]:
        r = self._get(f"/api/usage/logs?limit={limit}")
        r.raise_for_status()
        return r.json()

    # ── proxy pools ──
    def list_proxy_pools(self) -> List[Dict[str, Any]]:
        r = self._get("/api/proxy-pools")
        r.raise_for_status()
        data = r.json()
        return data.get("pools", data.get("proxyPools", [] if isinstance(data, dict) else data))

    # ── tunnel / tailscale ──
    def tunnel_status(self) -> Dict[str, Any]:
        """GET /api/tunnel/status → {tunnel, tailscale, download}."""
        r = self._get("/api/tunnel/status")
        r.raise_for_status()
        return r.json()

    def tunnel_enable(self) -> Dict[str, Any]:
        r = self._post("/api/tunnel/enable")
        r.raise_for_status()
        return r.json()

    def tunnel_disable(self) -> Dict[str, Any]:
        r = self._post("/api/tunnel/disable")
        r.raise_for_status()
        return r.json()

    def tailscale_enable(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        r = self._post("/api/tunnel/tailscale-enable", json=payload or {})
        r.raise_for_status()
        return r.json()

    def tailscale_disable(self) -> Dict[str, Any]:
        r = self._post("/api/tunnel/tailscale-disable")
        r.raise_for_status()
        return r.json()

    def tailscale_install(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        r = self._post("/api/tunnel/tailscale-install", json=payload or {})
        r.raise_for_status()
        return r.json()

    def tailscale_check(self) -> Dict[str, Any]:
        r = self._post("/api/tunnel/tailscale-check")
        r.raise_for_status()
        return r.json()

    # ── provider strategies / thinking (settings PATCH) ──
    def patch_provider_strategies(self, strategies: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH /api/settings {providerStrategies: {providerId: {fallbackStrategy, stickyRoundRobinLimit}}}."""
        return self.patch_settings({"providerStrategies": strategies})

    def patch_provider_thinking(self, thinking: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH /api/settings {providerThinking: {providerId: {mode}}}."""
        return self.patch_settings({"providerThinking": thinking})

    def patch_combo_strategies(self, strategies: Dict[str, Any]) -> Dict[str, Any]:
        return self.patch_settings({"comboStrategies": strategies})

    def patch_sticky_limits(self, provider_limit: Optional[int] = None,
                            combo_limit: Optional[int] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if provider_limit is not None:
            payload["stickyRoundRobinLimit"] = provider_limit
        if combo_limit is not None:
            payload["comboStickyRoundRobinLimit"] = combo_limit
        return self.patch_settings(payload)

    # ── provider models ──
    def list_provider_models(self, provider_id: str) -> List[Dict[str, Any]]:
        """GET /api/providers/:id/models — fetch models for a provider connection."""
        r = self._get(f"/api/providers/{provider_id}/models")
        r.raise_for_status()
        data = r.json()
        return data.get("models", data.get("data", [] if isinstance(data, dict) else data))

    def list_suggested_models(self, url: str, type: str) -> List[Dict[str, Any]]:
        """GET /api/providers/suggested-models?url=..&type=.. — fetch + filter remote model list."""
        from urllib.parse import quote
        q = f"/api/providers/suggested-models?url={quote(url)}&type={quote(type)}"
        r = self._get(q)
        r.raise_for_status()
        return r.json().get("data", [])

    def test_model(self, model: str, kind: str = "llm") -> Dict[str, Any]:
        """POST /api/models/test — ping a single model."""
        r = self._post("/api/models/test", json={"model": model, "kind": kind})
        r.raise_for_status()
        return r.json()

    # ── custom models ──
    def list_custom_models(self) -> List[Dict[str, Any]]:
        r = self._get("/api/models/custom")
        r.raise_for_status()
        return r.json().get("models", [])

    def create_custom_model(self, provider_alias: str, model_id: str,
                            type: str = "llm", name: str = "") -> Dict[str, Any]:
        r = self._post("/api/models/custom",
                       json={"providerAlias": provider_alias, "id": model_id,
                             "type": type, "name": name})
        r.raise_for_status()
        return r.json()

    def delete_custom_model(self, provider_alias: str, model_id: str, type: str = "llm") -> Dict[str, Any]:
        from urllib.parse import quote
        q = f"/api/models/custom?providerAlias={quote(provider_alias)}&id={quote(model_id)}&type={quote(type)}"
        r = self._delete(q)
        r.raise_for_status()
        return r.json() if r.text else {}

    # ── disabled models ──
    def list_disabled_models(self, provider_alias: Optional[str] = None) -> Dict[str, Any]:
        q = f"/api/models/disabled?providerAlias={provider_alias}" if provider_alias else "/api/models/disabled"
        r = self._get(q)
        r.raise_for_status()
        return r.json()

    def disable_models(self, provider_alias: str, ids: List[str]) -> Dict[str, Any]:
        r = self._post("/api/models/disabled", json={"providerAlias": provider_alias, "ids": ids})
        r.raise_for_status()
        return r.json()

    def enable_models(self, provider_alias: str, ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """DELETE /api/models/disabled?providerAlias=..[&id=..] — re-enable model(s)."""
        from urllib.parse import quote
        if ids and len(ids) == 1:
            q = f"/api/models/disabled?providerAlias={quote(provider_alias)}&id={quote(ids[0])}"
        else:
            q = f"/api/models/disabled?providerAlias={quote(provider_alias)}"
        r = self._delete(q)
        r.raise_for_status()
        return r.json() if r.text else {}

    # ── version ──
    def get_version(self) -> Dict[str, Any]:
        r = self._get("/api/version")
        r.raise_for_status()
        return r.json()

    # ── auth (dashboard cookie) ──
    def login(self, password: str) -> bool:
        try:
            r = self._post("/api/auth/login", json={"password": password})
            if r.status_code == 200:
                # capture cookies
                for k, v in r.cookies.items():
                    self._cookies[k] = v
                # also from headers
                for c in r.headers.get("set-cookie", "").split(","):
                    if "=" in c:
                        kv = c.strip().split(";")[0]
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            self._cookies[k.strip()] = v.strip()
                return True
            return False
        except Exception:
            return False


DEFAULT_SERVERS: List[ServerProfile] = [
    ServerProfile(name="Local", url="http://localhost:20128", description="Local 9Router (npm run dev)"),
    ServerProfile(name="Tunnel", url="https://distribute-jimmy-church-audit.trycloudflare.com", description="Cloudflare Tunnel (from backup)"),
]

SERVERS_FILE = "servers.json"
SERVERS_TOML_SECTION = "servers"  # [[servers]] in config.toml


def _load_servers_from_file(base_dir: Optional[str] = None) -> List[ServerProfile]:
    """Load saved servers from servers.json or config.toml [[servers]]."""
    base = base_dir or _get_app_dir()
    # 1. servers.json
    jpath = os.path.join(base, SERVERS_FILE)
    if os.path.exists(jpath):
        try:
            data = json.loads(open(jpath, encoding="utf-8").read())
            out: List[ServerProfile] = []
            for item in data if isinstance(data, list) else data.get("servers", []):
                if isinstance(item, dict) and item.get("url"):
                    out.append(ServerProfile(
                        name=item.get("name", item["url"]),
                        url=item["url"],
                        api_key=item.get("api_key", item.get("apiKey", "")),
                        timeout=int(item.get("timeout", 15)),
                        description=item.get("description", ""),
                        password=item.get("password", ""),
                    ))
            if out:
                return out
        except Exception:
            pass
    # 2. config.toml [[servers]]
    cfg_path = os.path.join(base, "config.toml")
    if os.path.exists(cfg_path):
        try:
            try:
                import tomllib
                with open(cfg_path, "rb") as f:
                    data = tomllib.load(f)
            except ImportError:
                import tomli as tomllib  # type: ignore
                with open(cfg_path, "rb") as f:
                    data = tomllib.load(f)
            raw = data.get(SERVERS_TOML_SECTION, [])
            if isinstance(raw, list) and raw:
                out = []
                for item in raw:
                    if isinstance(item, dict) and item.get("url"):
                        out.append(ServerProfile(
                            name=item.get("name", item["url"]),
                            url=item["url"],
                            api_key=item.get("api_key", item.get("apiKey", "")),
                            timeout=int(item.get("timeout", 15)),
                            description=item.get("description", ""),
                            password=item.get("password", ""),
                        ))
                if out:
                    return out
        except Exception:
            pass
    return []


def save_servers_to_file(servers: List[ServerProfile], base_dir: Optional[str] = None) -> None:
    base = base_dir or _get_app_dir()
    jpath = os.path.join(base, SERVERS_FILE)
    payload = [
        {
            "name": s.name,
            "url": s.url,
            "api_key": s.api_key,
            "timeout": s.timeout,
            "description": s.description,
            "password": s.password,
        }
        for s in servers
    ]
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def has_any_config(config_path: Optional[str] = None) -> bool:
    """True if env or config.toml or servers.json provides a URL."""
    if os.getenv("NINEROUTER_URL"):
        return True
    app_dir = _get_app_dir()
    base = os.path.dirname(config_path) if config_path and os.path.dirname(config_path) else app_dir
    if os.path.exists(os.path.join(base, SERVERS_FILE)):
        return True
    cfg_path = config_path or os.path.join(app_dir, "config.toml")
    if os.path.exists(cfg_path):
        return True
    if os.path.exists(os.path.join(app_dir, ".env")):
        return True
    return False


def load_config_from_env_and_file(config_path: Optional[str] = None) -> NinerouterConfig:
    """Load config with precedence: env > config.toml > defaults."""
    # Try .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    url = os.getenv("NINEROUTER_URL", "")
    api_key = os.getenv("NINEROUTER_KEY", "")
    password = os.getenv("NINEROUTER_PASSWORD", "")

    # Try config.toml
    app_dir = _get_app_dir()
    cfg_path = config_path or os.path.join(app_dir, "config.toml")
    if os.path.exists(cfg_path):
        try:
            # Python 3.11+ has tomllib
            try:
                import tomllib
                with open(cfg_path, "rb") as f:
                    data = tomllib.load(f)
            except ImportError:
                import tomli as tomllib  # type: ignore
                with open(cfg_path, "rb") as f:
                    data = tomllib.load(f)
            server = data.get("server", {})
            if not url:
                url = server.get("url", "")
            if not api_key:
                api_key = server.get("api_key", "")
            if not password:
                password = server.get("password", "")
            timeout = server.get("timeout", 15)
            return NinerouterConfig(
                url=url or "http://localhost:20128",
                api_key=api_key,
                timeout=timeout,
                password=password,
            )
        except Exception:
            pass

    return NinerouterConfig(
        url=url or "http://localhost:20128",
        api_key=api_key,
        timeout=15,
        password=password,
    )


def classify_url(url: str) -> str:
    """Classify URL kind. Re-export from updater for convenience."""
    try:
        from updater import classify_url as _cu
        return _cu(url)
    except Exception:
        u = (url or "").lower()
        if any(h in u for h in ["localhost", "127.0.0.1", "::1"]):
            return "local"
        if "trycloudflare.com" in u or "ngrok" in u:
            return "tunnel"
        return "domain"

def detect_host_info(url: str) -> dict:
    try:
        from updater import detect_host_info as _dhi
        return _dhi(url)
    except Exception:
        return {"kind": classify_url(url), "host": url, "label": classify_url(url)}

def auto_detect_servers(timeout: int = 3) -> list:
    try:
        from updater import auto_detect_servers as _ads
        return _ads(timeout=timeout)
    except Exception:
        return []

def probe_server(url: str, api_key: str = "", timeout: int = 5) -> Dict[str, Any]:
    """Quick probe: GET /api/health. Returns {ok, status, error, latency_ms}."""
    import time
    start = time.monotonic()
    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        r = requests.get(url.rstrip("/") + "/api/health", headers=headers, timeout=timeout)
        latency = int((time.monotonic() - start) * 1000)
        if r.status_code == 200:
            try:
                j = r.json()
                ok = bool(j.get("ok", True))
            except Exception:
                ok = True
            return {"ok": ok, "status": r.status_code, "latency_ms": latency, "error": None}
        return {"ok": False, "status": r.status_code, "latency_ms": latency, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        latency = int((time.monotonic() - start) * 1000)
        return {"ok": False, "status": None, "latency_ms": latency, "error": str(e)[:120]}
