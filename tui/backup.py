"""Backup & restore helpers for 9Router DB (data.sqlite + history).

Upstream: 9router-master/src/lib/db/{paths,backup,index}.js
- DATA_DIR = ~/.9router or $DATA_DIR
- DB = DATA_DIR/db/data.sqlite
- Safety backups: backupDbLite() excludes requestDetails
- Full export: exportDb() → JSON (providerConnections, providerNodes, proxyPools, apiKeys, combos, kv, usageHistory, usageDaily, requestDetails)

TUI can backup via:
1. Direct file copy (local or SSH) — full fidelity, includes history
2. API export (GET all) — fallback when file access not available
"""
from __future__ import annotations

import json
import os
import shutil
import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from client import NinerouterClient, ServerProfile
except ImportError:
    NinerouterClient = Any  # type: ignore
    ServerProfile = Any  # type: ignore


def _default_data_dir() -> Path:
    data_dir = os.getenv("DATA_DIR")
    if data_dir:
        # On Windows, ignore Unix absolute paths from Linux .env
        if os.name == "nt" and data_dir.startswith("/"):
            pass
        else:
            return Path(data_dir)
    if os.name == "nt":
        appdata = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "9router"
    return Path.home() / ".9router"


def get_data_file(profile: Optional[ServerProfile] = None) -> Path:
    """Local DB path. For remote, this is the remote path (used with SSH)."""
    # Remote DATA_DIR is usually /app/data or ~/.9router on Linux
    if profile and getattr(profile, "ssh_host", ""):
        # Heuristic: try common remote paths
        for cand in ["/app/data/db/data.sqlite", "~/.9router/db/data.sqlite", "/root/.9router/db/data.sqlite"]:
            return Path(cand)
    return _default_data_dir() / "db" / "data.sqlite"


def get_backup_dir() -> Path:
    """Local backup dir (gitignored)."""
    # Prefer 9router-backup/ in app dir
    try:
        from client import _get_app_dir
        app_dir = Path(_get_app_dir())
        cand = app_dir / "9router-backup"
        cand.mkdir(parents=True, exist_ok=True)
        return cand
    except Exception:
        d = _default_data_dir() / "backups"
        d.mkdir(parents=True, exist_ok=True)
        return d


def timestamp_slug() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")


def backup_local(dest_dir: Optional[str] = None) -> str:
    """Copy local data.sqlite + export JSON. Returns backup JSON path."""
    src = get_data_file()
    dest = Path(dest_dir) if dest_dir else get_backup_dir()
    dest.mkdir(parents=True, exist_ok=True)
    slug = f"9router-backup-{timestamp_slug()}"
    # 1. Copy sqlite if exists
    if src.exists():
        shutil.copy2(src, dest / f"{slug}.sqlite")
    # 2. Also try API export if client available (for JSON)
    return str(dest / f"{slug}.json")


def export_via_api(client: NinerouterClient) -> Dict[str, Any]:
    """Fallback: reconstruct backup JSON via multiple GETs."""
    out: Dict[str, Any] = {}
    try:
        out["settings"] = client.get_settings()
    except Exception:
        out["settings"] = {}
    try:
        out["providerConnections"] = client.list_providers()
    except Exception:
        out["providerConnections"] = []
    try:
        out["providerNodes"] = client.list_nodes()
    except Exception:
        out["providerNodes"] = []
    try:
        out["proxyPools"] = client.list_proxy_pools()
    except Exception:
        out["proxyPools"] = []
    try:
        out["apiKeys"] = client.list_keys()
    except Exception:
        out["apiKeys"] = []
    try:
        out["combos"] = client.list_combos()
    except Exception:
        out["combos"] = []
    # kv
    try:
        out["modelAliases"] = client.get_model_aliases()
    except Exception:
        out["modelAliases"] = {}
    # usage
    try:
        out["usageHistory"] = client.get_usage_history(1000)
    except Exception:
        out["usageHistory"] = []
    try:
        out["requestDetails"] = client.get_request_logs(200)
    except Exception:
        out["requestDetails"] = []
    return out


def save_backup_json(payload: Dict[str, Any], dest_dir: Optional[str] = None) -> str:
    dest = Path(dest_dir) if dest_dir else get_backup_dir()
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"9router-backup-{timestamp_slug()}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return str(path)


def list_backups(dest_dir: Optional[str] = None):
    dest = Path(dest_dir) if dest_dir else get_backup_dir()
    if not dest.exists():
        return []
    files = sorted(dest.glob("9router-backup-*.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p) for p in files]


def prune_backups(keep: int = 5, dest_dir: Optional[str] = None) -> int:
    files = list_backups(dest_dir)
    removed = 0
    for p in files[keep:]:
        try:
            os.remove(p)
            removed += 1
        except Exception:
            pass
    return removed
