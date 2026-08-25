"""Shared helpers for TUI — extracted from app.py."""
from __future__ import annotations

from datetime import datetime
from typing import Optional


def mask_key(k: str) -> str:
    if not k:
        return "—"
    if len(k) <= 12:
        return k[:4] + "****"
    return k[:8] + "****" + k[-4:]


def fmt_time(s: Optional[str]) -> str:
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s[:19]


def _store_plain(widget, plain: str) -> None:
    """Store plain text on Static for clipboard copy."""
    try:
        widget._plain_text = plain  # type: ignore[attr-defined]
        try:
            app = widget.app  # type: ignore[attr-defined]
            if hasattr(app, "_detail_plain"):
                wid = getattr(widget, "id", "") or ""
                key_map = {
                    "overview-body": "overview",
                    "providers-detail": "providers",
                    "nodes-detail": "nodes",
                    "combos-detail": "combos",
                    "models-detail": "models",
                    "keys-detail": "keys",
                    "usage-detail": "usage",
                    "usage-body": "usage",
                    "settings-body": "settings",
                    "update-log": "update",
                    "update-version-body": "update",
                    "update-docker-body": "update",
                }
                k = key_map.get(wid)
                if k:
                    app._detail_plain[k] = plain  # type: ignore[attr-defined]
        except Exception:
            pass
    except Exception:
        pass


def status_style(s: str) -> str:
    s = (s or "").lower()
    if s in ("active", "ok", "success"):
        return "green"
    if s in ("unavailable", "error", "failed"):
        return "red"
    if s in ("testing", "pending"):
        return "yellow"
    return "white"


# ── UID helpers (provider node IDs) ──
UID_PATTERNS = {
    "openai-compatible-chat": r"^openai-compatible-chat-[a-zA-Z0-9_-]+$",
    "openai-compatible-responses": r"^openai-compatible-responses-[a-zA-Z0-9_-]+$",
    "openai-compatible": r"^openai-compatible-(?:chat|responses)-[a-zA-Z0-9_-]+$",
    "anthropic-compatible": r"^anthropic-compatible-[a-zA-Z0-9_-]+$",
    "custom-embedding": r"^custom-embedding-[a-zA-Z0-9_-]+$",
}
UID_PREFIXES = {
    "openai-compatible": "openai-compatible-",
    "anthropic-compatible": "anthropic-compatible-",
    "custom-embedding": "custom-embedding-",
}


def uid_prefix_for_type(node_type: str, api_type: str = "") -> str:
    if node_type == "openai-compatible":
        if api_type == "responses":
            return "openai-compatible-responses-"
        return "openai-compatible-chat-"
    if node_type == "anthropic-compatible":
        return "anthropic-compatible-"
    if node_type == "custom-embedding":
        return "custom-embedding-"
    return ""


def validate_uid(node_type: str, api_type: str, uid: str) -> tuple[bool, str]:
    if not uid or not uid.strip():
        return False, "ID cannot be empty"
    uid = uid.strip()
    if len(uid) < 8:
        return False, "ID too short (min 8 chars)"
    if not all(c.isalnum() or c in "-_" for c in uid.replace("openai-compatible-", "").replace("anthropic-compatible-", "").replace("custom-embedding-", "")):
        return False, "ID may only contain a-z, 0-9, -, _"
    prefix = uid_prefix_for_type(node_type, api_type)
    if prefix and not uid.startswith(prefix):
        return False, f"ID must start with '{prefix}'"
    import re
    pat = UID_PATTERNS.get(f"{node_type}-{api_type}" if node_type == "openai-compatible" and api_type else node_type, r"^[a-zA-Z0-9_-]+$")
    if not re.match(pat, uid):
        return False, f"ID does not match pattern {pat}"
    return True, ""


def extract_uid_suffix(full_id: str, node_type: str, api_type: str = "") -> str:
    prefix = uid_prefix_for_type(node_type, api_type)
    if prefix and full_id.startswith(prefix):
        return full_id[len(prefix):]
    return full_id.split("-")[-1] if "-" in full_id else full_id
