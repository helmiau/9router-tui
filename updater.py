"""
9Router TUI — Updater & Docker Manager
Standalone helpers for checking and applying 9Router updates.

Supports:
  - npm global (npm install -g 9router@latest)
  - source (git pull + npm install + npm run build)
  - docker (docker pull / docker compose pull + up -d)

Local operations run directly; remote VPS via SSH (ServerProfile.ssh_host).
Remote without SSH only shows version info + instructions.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


@dataclass
class VersionInfo:
    current: str
    latest: str
    has_update: bool
    source: str  # "api" | "npm" | "local"
    error: Optional[str] = None


def is_local_url(url: str) -> bool:
    u = url.lower()
    return any(h in u for h in ["localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"]) or u.startswith("http://192.168.") or u.startswith("http://10.") or u.startswith("http://172.")

def classify_url(url: str) -> str:
    """Classify URL as 'local' | 'private-ip' | 'public-ip' | 'domain' | 'tunnel' | 'unknown'."""
    import re
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        host = (parsed.hostname or "").lower()
        if not host:
            return "unknown"
        # local
        if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"):
            return "local"
        # tunnel (cloudflare, ngrok, etc)
        if any(d in host for d in ["trycloudflare.com", "ngrok.io", "ngrok-free.app", "loca.lt", "serveo.net"]):
            return "tunnel"
        # IP?
        ipv4_re = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
        if ipv4_re.match(host):
            parts = [int(x) for x in host.split(".")]
            if parts[0] == 10:
                return "private-ip"
            if parts[0] == 172 and 16 <= parts[1] <= 31:
                return "private-ip"
            if parts[0] == 192 and parts[1] == 168:
                return "private-ip"
            if host.startswith("127."):
                return "local"
            return "public-ip"
        # IPv6
        if ":" in host:
            if host == "::1" or host.startswith("fe80:") or host.startswith("fc00:") or host.startswith("fd00:"):
                return "private-ip" if ":" in host and host != "::1" else "local"
            return "public-ip"
        # domain
        return "domain"
    except Exception:
        return "unknown"

def detect_host_info(url: str) -> dict:
    """Return {kind, host, port, is_local, is_private, is_public, is_tunnel, label}."""
    from urllib.parse import urlparse
    kind = classify_url(url)
    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        host = parsed.hostname or ""
        port = parsed.port
    except Exception:
        host = ""
        port = None
    is_local = kind == "local"
    is_private = kind == "private-ip"
    is_tunnel = kind == "tunnel"
    is_public = kind in ("public-ip", "domain")
    label_map = {
        "local": "Local",
        "private-ip": "Private IP (LAN)",
        "public-ip": "Public IP (VPS)",
        "domain": "Domain (VPS)",
        "tunnel": "Tunnel (Cloudflare/ngrok)",
        "unknown": "Unknown",
    }
    return {
        "kind": kind,
        "host": host,
        "port": port,
        "is_local": is_local,
        "is_private": is_private,
        "is_tunnel": is_tunnel,
        "is_public": is_public,
        "label": label_map.get(kind, kind),
        "needs_ssh": kind in ("public-ip", "domain") and not is_tunnel,
    }

def auto_detect_servers(timeout: int = 3) -> list:
    """Probe common local endpoints and return reachable ServerProfiles."""
    candidates = [
        ("Local (20128)", "http://localhost:20128"),
        ("Local (20127)", "http://localhost:20127"),
        ("Local (3000)", "http://localhost:3000"),
        ("Docker host", "http://host.docker.internal:20128"),
    ]
    # also try LAN IPs via socket
    try:
        import socket
        hostname = socket.gethostname()
        # get LAN IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
            if lan_ip and not lan_ip.startswith("127."):
                candidates.append((f"LAN ({lan_ip})", f"http://{lan_ip}:20128"))
        except Exception:
            pass
        finally:
            s.close()
    except Exception:
        pass
    found = []
    for name, url in candidates:
        try:
            import requests as _rq
            r = _rq.get(url.rstrip("/") + "/api/health", timeout=timeout)
            if r.status_code == 200:
                try:
                    ok = bool(r.json().get("ok", True))
                except Exception:
                    ok = True
                if ok:
                    found.append({"name": name, "url": url, "ok": True})
        except Exception:
            pass
    return found


def fetch_npm_latest(package: str = "9router", timeout: int = 5) -> Optional[str]:
    try:
        r = requests.get(f"https://registry.npmjs.org/{package}/latest", timeout=timeout)
        if r.status_code == 200:
            return r.json().get("version")
    except Exception:
        pass
    return None


def fetch_docker_latest(image: str = "decolua/9router", timeout: int = 5) -> Optional[str]:
    """Try Docker Hub API for latest tag digest. Fallback to None."""
    try:
        # Docker Hub API: https://hub.docker.com/v2/repositories/decolua/9router/tags/latest
        r = requests.get(f"https://hub.docker.com/v2/repositories/{image}/tags/latest", timeout=timeout)
        if r.status_code == 200:
            j = r.json()
            # last_updated or digest
            return j.get("last_updated", "")[:19] or j.get("digest", "")[:12]
    except Exception:
        pass
    return None


def get_version_via_api(client) -> VersionInfo:
    try:
        data = client.get_version()
        cur = data.get("currentVersion", data.get("current", "—"))
        lat = data.get("latestVersion", data.get("latest", ""))
        has_up = bool(data.get("hasUpdate", False))
        if not lat:
            lat = fetch_npm_latest() or "—"
            # compare if we have both
            if cur != "—" and lat != "—":
                has_up = compare_versions(lat, cur) > 0
        return VersionInfo(current=cur, latest=lat or "—", has_update=has_up, source="api")
    except Exception as e:
        # fallback to npm
        cur = get_local_version() or "—"
        lat = fetch_npm_latest() or "—"
        has_up = False
        if cur != "—" and lat != "—":
            try:
                has_up = compare_versions(lat, cur) > 0
            except Exception:
                pass
        return VersionInfo(current=cur, latest=lat, has_update=has_up, source="npm", error=str(e)[:120])


def _get_app_dir_path() -> Path:
    """App dir — exe dir when frozen, else file dir."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def get_local_version(search_paths: Optional[List[str]] = None) -> Optional[str]:
    """Try to read version from local 9router-master/package.json or cli/package.json."""
    candidates = search_paths or []
    # default candidates relative to this file
    base = _get_app_dir_path()
    candidates += [
        str(base.parent / "9router-master" / "9router-master" / "package.json"),
        str(base.parent / "9router-master" / "package.json"),
        str(base / "package.json"),
        str(Path.cwd() / "package.json"),
        str(Path.cwd() / "9router-master" / "package.json"),
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                j = json.loads(Path(p).read_text(encoding="utf-8"))
                v = j.get("version")
                if v:
                    return v
        except Exception:
            continue
    return None


def compare_versions(a: str, b: str) -> int:
    """Return 1 if a>b, -1 if a<b, 0 if equal. Handles semver."""
    def parse(v: str) -> List[int]:
        # strip v prefix, take numeric parts
        v = v.strip().lstrip("v")
        parts = []
        for x in v.split("."):
            num = "".join(c for c in x if c.isdigit())
            try:
                parts.append(int(num) if num else 0)
            except Exception:
                parts.append(0)
        while len(parts) < 3:
            parts.append(0)
        return parts[:3]
    pa, pb = parse(a), parse(b)
    for x, y in zip(pa, pb):
        if x > y:
            return 1
        if x < y:
            return -1
    return 0


def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def run_cmd(cmd: List[str], cwd: Optional[str] = None, timeout: int = 120) -> Tuple[int, str, str]:
    """Run command, return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", f"timeout after {timeout}s"
    except FileNotFoundError as e:
        return 127, "", str(e)
    except Exception as e:
        return 1, "", str(e)


def _ssh_base_args(profile) -> List[str]:
    """Build ssh base args for profile. Returns [] if not remote."""
    if not profile or not getattr(profile, 'ssh_host', ''):
        return []
    args = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10"]
    if getattr(profile, 'ssh_port', 22) and profile.ssh_port != 22:
        args += ["-p", str(profile.ssh_port)]
    if getattr(profile, 'ssh_key', ''):
        key = os.path.expanduser(profile.ssh_key)
        args += ["-i", key]
    # user@host
    user = getattr(profile, 'ssh_user', '') or "root"
    args.append(f"{user}@{profile.ssh_host}")
    return args

def _run_remote(profile, remote_cmd: str, timeout: int = 120) -> Tuple[int, str, str]:
    """Run remote_cmd via ssh. remote_cmd is a shell string."""
    base = _ssh_base_args(profile)
    if not base:
        return 127, "", "no ssh_host configured for this server"
    # ssh user@host "remote_cmd"
    cmd = base + [remote_cmd]
    return run_cmd(cmd, timeout=timeout)

def _run_remote_or_local(profile, cmd: List[str], cwd: Optional[str] = None, timeout: int = 120) -> Tuple[int, str, str]:
    """If profile is remote, run via ssh; else run locally."""
    if profile and getattr(profile, 'ssh_host', ''):
        # build remote shell command
        # cwd handling: cd <cwd> && <cmd>
        shell = " ".join(cmd)
        if cwd:
            # escape single quotes for shell
            cwd_esc = cwd.replace("'", "'\\''")
            shell = f"cd '{cwd_esc}' && {shell}"
        return _run_remote(profile, shell, timeout=timeout)
    return run_cmd(cmd, cwd=cwd, timeout=timeout)

def detect_install_method_remote(profile=None) -> str:
    """Detect install method, via SSH if profile is remote."""
    if profile and getattr(profile, 'ssh_host', ''):
        # remote detection
        # check docker ps
        rc, out, _ = _run_remote(profile, "docker ps -a --format '{{.Names}}' 2>&1 || echo __no_docker__", timeout=10)
        if rc == 0 and "9router" in out and "__no_docker__" not in out:
            return "docker"
        # check compose file
        rc2, out2, _ = _run_remote(profile, "ls -1 docker-compose.yml 9router-master/docker-compose.yml 9router-master/9router-master/docker-compose.yml 2>/dev/null | head -1", timeout=10)
        if rc2 == 0 and out2.strip():
            return "docker"
        rc3, out3, _ = _run_remote(profile, "npm list -g 9router 2>&1 | grep -q 9router && echo npm || echo no", timeout=10)
        if "npm" in out3:
            return "npm"
        rc4, out4, _ = _run_remote(profile, "ls -1 9router-master/package.json 9router-master/9router-master/package.json 2>/dev/null | head -1", timeout=10)
        if rc4 == 0 and out4.strip():
            return "source"
        return "unknown"
    return detect_install_method()

def docker_status_remote(profile=None) -> Dict[str, Any]:
    """Get docker status, via SSH if remote."""
    if profile and getattr(profile, 'ssh_host', ''):
        result: Dict[str, Any] = {"available": False, "containers": [], "images": [], "compose": False, "error": None, "remote": True}
        # check docker exists
        rc, out, err = _run_remote(profile, "which docker 2>&1 || echo __no_docker__", timeout=10)
        if "__no_docker__" in out or rc != 0:
            result["error"] = "docker not found on remote host"
            return result
        result["available"] = True
        rc, out, err = _run_remote(profile, "docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}' 2>&1", timeout=10)
        if rc == 0:
            for line in out.strip().splitlines():
                if not line.strip():
                    continue
                parts = line.split("|")
                if len(parts) >= 3:
                    result["containers"].append({"name": parts[0], "image": parts[1], "status": parts[2]})
                else:
                    result["containers"].append({"raw": line})
        else:
            result["error"] = err[:200] if err else f"docker ps failed rc={rc}"
        rc2, out2, _ = _run_remote(profile, "docker images decolua/9router --format '{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedSince}}' 2>&1", timeout=10)
        if rc2 == 0:
            for line in out2.strip().splitlines():
                if line.strip():
                    result["images"].append(line.strip())
        # compose
        rc3, out3, _ = _run_remote(profile, "ls -1 docker-compose.yml 9router-master/docker-compose.yml 9router-master/9router-master/docker-compose.yml 2>/dev/null | head -1", timeout=10)
        if rc3 == 0 and out3.strip():
            result["compose"] = out3.strip()
        # also check profile.compose_path
        if getattr(profile, 'compose_path', ''):
            result["compose"] = profile.compose_path
        return result
    return docker_status()

def docker_logs_remote(profile=None, container: str = "9router", tail: int = 100) -> Tuple[int, str, str]:
    if profile and getattr(profile, 'ssh_host', ''):
        return _run_remote(profile, f"docker logs --tail {tail} {container} 2>&1", timeout=15)
    return docker_logs(container, tail)

def detect_install_method() -> str:
    """Heuristic: docker > npm > source > unknown."""
    # docker: check if 9router container exists or docker-compose.yml nearby
    if which("docker"):
        # check docker ps for 9router
        rc, out, _ = run_cmd(["docker", "ps", "-a", "--format", "{{.Names}}"], timeout=10)
        if rc == 0 and "9router" in out:
            return "docker"
        # check compose file nearby
        for p in [Path.cwd() / "docker-compose.yml", Path.cwd() / "9router-master" / "docker-compose.yml", Path.cwd() / "9router-master" / "9router-master" / "docker-compose.yml"]:
            if p.exists():
                return "docker"
    if which("npm"):
        rc, out, _ = run_cmd(["npm", "list", "-g", "9router"], timeout=10)
        if rc == 0 and "9router" in out:
            return "npm"
        # also check npx
        if which("9router"):
            return "npm"
    # source: check for 9router-master
    for p in [Path.cwd() / "9router-master" / "package.json", Path.cwd() / "9router-master" / "9router-master" / "package.json"]:
        if p.exists():
            return "source"
    return "unknown"


def docker_status() -> Dict[str, Any]:
    """Get docker status for 9router."""
    result: Dict[str, Any] = {"available": False, "containers": [], "images": [], "compose": False, "error": None}
    if not which("docker"):
        result["error"] = "docker not found in PATH"
        return result
    result["available"] = True
    # ps
    rc, out, err = run_cmd(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Image}}|{{.Status}}"], timeout=10)
    if rc == 0:
        for line in out.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                result["containers"].append({"name": parts[0], "image": parts[1], "status": parts[2]})
            else:
                result["containers"].append({"raw": line})
    else:
        result["error"] = err[:200] if err else f"docker ps failed rc={rc}"
    # images
    rc2, out2, _ = run_cmd(["docker", "images", "decolua/9router", "--format", "{{.Repository}}:{{.Tag}} {{.ID}} {{.CreatedSince}}"], timeout=10)
    if rc2 == 0:
        for line in out2.strip().splitlines():
            if line.strip():
                result["images"].append(line.strip())
    # compose
    for p in [Path.cwd() / "docker-compose.yml", Path.cwd() / "9router-master" / "docker-compose.yml", Path.cwd() / "9router-master" / "9router-master" / "docker-compose.yml"]:
        if p.exists():
            result["compose"] = str(p)
            break
    return result


def docker_logs(container: str = "9router", tail: int = 100) -> Tuple[int, str, str]:
    return run_cmd(["docker", "logs", "--tail", str(tail), container], timeout=15)


def build_update_plan(method: str, compose_file: Optional[str] = None) -> List[List[str]]:
    """Return list of commands to run for update."""
    method = method.lower()
    if method == "npm":
        return [["npm", "install", "-g", "9router@latest"]]
    if method == "source":
        # find source dir
        src = None
        for p in [Path.cwd() / "9router-master", Path.cwd() / "9router-master" / "9router-master", Path.cwd()]:
            if (p / "package.json").exists():
                src = str(p)
                break
        src = src or "."
        return [
            ["git", "pull"],
            ["npm", "install"],
            ["npm", "run", "build"],
        ], src  # type: ignore
    if method == "docker":
        if compose_file and os.path.exists(compose_file):
            return [
                ["docker", "compose", "-f", compose_file, "pull"],
                ["docker", "compose", "-f", compose_file, "up", "-d"],
            ]
        # try auto-detect compose
        for p in [Path.cwd() / "docker-compose.yml", Path.cwd() / "9router-master" / "docker-compose.yml", Path.cwd() / "9router-master" / "9router-master" / "docker-compose.yml"]:
            if p.exists():
                return [
                    ["docker", "compose", "-f", str(p), "pull"],
                    ["docker", "compose", "-f", str(p), "up", "-d"],
                ]
        return [
            ["docker", "pull", "decolua/9router:latest"],
            ["docker", "pull", "ghcr.io/decolua/9router:latest"],
        ]
    return []


def run_update_remote(profile, method: str, dry_run: bool = False, compose_file: Optional[str] = None, cwd: Optional[str] = None) -> List[Dict[str, Any]]:
    """Run update via SSH if profile is remote, else locally."""
    # resolve compose_path from profile
    if not compose_file and profile and getattr(profile, 'compose_path', ''):
        compose_file = profile.compose_path
    method = method.lower()
    steps: List[Dict[str, Any]] = []
    is_remote = bool(profile and getattr(profile, 'ssh_host', ''))
    runner = lambda cmd, c, to: _run_remote_or_local(profile, cmd, cwd=c, timeout=to)
    if method == "source":
        src = cwd or (compose_file and os.path.dirname(compose_file)) or None
        if not src:
            # try to find source dir
            if is_remote:
                rc, out, _ = _run_remote(profile, "ls -d 9router-master/9router-master 9router-master 2>/dev/null | head -1", timeout=10)
                src = out.strip() or "."
            else:
                for p in [Path.cwd() / "9router-master" / "9router-master", Path.cwd() / "9router-master", Path.cwd()]:
                    if (p / "package.json").exists():
                        src = str(p)
                        break
                src = src or str(Path.cwd())
        plan = [
            (["git", "pull"], src),
            (["npm", "install"], src),
            (["npm", "run", "build"], src),
        ]
        for cmd, c in plan:
            if dry_run:
                steps.append({"cmd": " ".join(cmd), "cwd": c, "rc": 0, "stdout": "[dry-run]", "stderr": "", "dry_run": True, "remote": is_remote})
                continue
            rc, out, err = runner(cmd, c, 300)
            steps.append({"cmd": " ".join(cmd), "cwd": c, "rc": rc, "stdout": out[-2000:], "stderr": err[-2000:], "dry_run": False, "remote": is_remote})
            if rc != 0:
                break
        return steps
    plan = build_update_plan(method, compose_file)
    if method == "source" and isinstance(plan, tuple):
        pass
    normalized: List[Tuple[List[str], Optional[str]]] = []
    for item in plan:  # type: ignore
        if isinstance(item, list):
            normalized.append((item, cwd))
        elif isinstance(item, tuple):
            normalized.append(item)
    for cmd, c in normalized:
        if dry_run:
            steps.append({"cmd": " ".join(cmd), "cwd": c or cwd or ".", "rc": 0, "stdout": "[dry-run]", "stderr": "", "dry_run": True, "remote": is_remote})
            continue
        rc, out, err = runner(cmd, c, 300)
        steps.append({"cmd": " ".join(cmd), "cwd": c or cwd or ".", "rc": rc, "stdout": out[-3000:], "stderr": err[-3000:], "dry_run": False, "remote": is_remote})
        if rc != 0:
            break
    return steps


def run_update(method: str, dry_run: bool = False, compose_file: Optional[str] = None, cwd: Optional[str] = None) -> List[Dict[str, Any]]:
    """Execute update plan, return list of step results."""
    method = method.lower()
    steps: List[Dict[str, Any]] = []
    if method == "source":
        # special handling: need cwd
        src = cwd
        if not src:
            for p in [Path.cwd() / "9router-master" / "9router-master", Path.cwd() / "9router-master", Path.cwd()]:
                if (p / "package.json").exists():
                    src = str(p)
                    break
            src = src or str(Path.cwd())
        plan = [
            (["git", "pull"], src),
            (["npm", "install"], src),
            (["npm", "run", "build"], src),
        ]
        for cmd, c in plan:
            if dry_run:
                steps.append({"cmd": " ".join(cmd), "cwd": c, "rc": 0, "stdout": "[dry-run]", "stderr": "", "dry_run": True})
                continue
            rc, out, err = run_cmd(cmd, cwd=c, timeout=300)
            steps.append({"cmd": " ".join(cmd), "cwd": c, "rc": rc, "stdout": out[-2000:], "stderr": err[-2000:], "dry_run": False})
            if rc != 0:
                break
        return steps

    plan = build_update_plan(method, compose_file)
    # handle source returning tuple
    if method == "source" and isinstance(plan, tuple):
        # already handled above
        pass
    # normalize plan to list of (cmd, cwd)
    normalized: List[Tuple[List[str], Optional[str]]] = []
    for item in plan:  # type: ignore
        if isinstance(item, list):
            normalized.append((item, cwd))
        elif isinstance(item, tuple):
            normalized.append(item)

    for cmd, c in normalized:
        if dry_run:
            steps.append({"cmd": " ".join(cmd), "cwd": c or cwd or ".", "rc": 0, "stdout": "[dry-run]", "stderr": "", "dry_run": True})
            continue
        rc, out, err = run_cmd(cmd, cwd=c, timeout=300)
        steps.append({"cmd": " ".join(cmd), "cwd": c or cwd or ".", "rc": rc, "stdout": out[-3000:], "stderr": err[-3000:], "dry_run": False})
        if rc != 0:
            break
    return steps
