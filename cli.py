"""
9Router TUI — Rich CLI (non-interactive)
Standalone, no omnexsync dependency.

Usage:
  python cli.py health
  python cli.py providers
  python cli.py nodes
  python cli.py combos
  python cli.py models
  python cli.py keys
  python cli.py usage --period 7d
  python cli.py settings
  python cli.py test --mode all
  python cli.py dashboard   # launch Textual TUI

Env:
  NINEROUTER_URL=http://localhost:20128
  NINEROUTER_KEY=sk-...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON

from client import NinerouterClient, load_config_from_env_and_file, _load_servers_from_file, save_servers_to_file, ServerProfile, DEFAULT_SERVERS, probe_server, detect_host_info
from updater import get_version_via_api, get_local_version, compare_versions, detect_install_method, detect_install_method_remote, docker_status, docker_status_remote, docker_logs, docker_logs_remote, run_update, run_update_remote, build_update_plan, is_local_url, fetch_npm_latest

try:
    from _version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "1.0.0"

console = Console()


def mask_key(k: str) -> str:
    if not k:
        return "—"
    if len(k) <= 12:
        return k[:4] + "****"
    return k[:8] + "****" + k[-4:]


def print_json(data: Any, title: str = ""):
    if title:
        console.print(Panel(JSON(json.dumps(data, indent=2, ensure_ascii=False)), title=title))
    else:
        console.print(JSON(json.dumps(data, indent=2, ensure_ascii=False)))


def cmd_health(client: NinerouterClient, args):
    data = client.health()
    console.print(Panel(f"[green]OK[/] {data}" if data.get("ok") else f"[red]FAIL[/] {data}", title="Health"))
    console.print(f"URL: {client.base}")


def cmd_providers(client: NinerouterClient, args):
    data = client.list_providers()
    table = Table(title=f"Providers — {len(data)} connections", show_lines=False)
    table.add_column("Name", style="cyan")
    table.add_column("Provider", style="magenta")
    table.add_column("Priority", justify="right")
    table.add_column("Active", justify="center")
    table.add_column("Status")
    table.add_column("ID", style="dim")
    for p in data:
        if args.filter and args.filter.lower() not in f"{p.get('name','')} {p.get('provider','')}".lower():
            continue
        table.add_row(
            p.get("name", "—"),
            p.get("provider", "—"),
            str(p.get("priority", "—")),
            "✓" if p.get("isActive") else "✗",
            p.get("testStatus", p.get("status", "—")),
            p.get("id", "")[:12],
        )
    console.print(table)
    if args.json:
        print_json(data, "Providers JSON")


def cmd_nodes(client: NinerouterClient, args):
    data = client.list_nodes()
    table = Table(title=f"Provider Nodes — {len(data)} nodes", show_lines=False)
    table.add_column("Name", style="cyan")
    table.add_column("Prefix", style="yellow")
    table.add_column("Type")
    table.add_column("API Type")
    table.add_column("Base URL", style="dim")
    table.add_column("ID", style="dim")
    for n in data:
        if args.filter and args.filter.lower() not in f"{n.get('name','')} {n.get('prefix','')} {n.get('id','')}".lower():
            continue
        table.add_row(
            n.get("name", "—"),
            n.get("prefix", "—"),
            n.get("type", "—"),
            n.get("apiType", n.get("api_type", "—")),
            n.get("baseUrl", n.get("base_url", "—")),
            n.get("id", "")[:16],
        )
    console.print(table)
    if args.json:
        print_json(data, "Nodes JSON")


def cmd_combos(client: NinerouterClient, args):
    data = client.list_combos()
    table = Table(title=f"Combos — {len(data)}", show_lines=False)
    table.add_column("Name", style="cyan")
    table.add_column("Kind")
    table.add_column("Models", style="dim")
    table.add_column("ID", style="dim")
    for c in data:
        models = c.get("models", [])
        table.add_row(
            c.get("name", "—"),
            c.get("kind", "—") or "—",
            ", ".join(models[:3]) + (f" +{len(models)-3} more" if len(models) > 3 else ""),
            c.get("id", "")[:8],
        )
    console.print(table)
    if args.json:
        print_json(data, "Combos JSON")


def cmd_models(client: NinerouterClient, args):
    data = client.list_models()
    models = data.get("models", []) if isinstance(data, dict) else data
    table = Table(title=f"Models — {len(models)}", show_lines=False)
    table.add_column("Model", style="cyan")
    table.add_column("Provider", style="magenta")
    table.add_column("Alias", style="yellow")
    table.add_column("Caps", style="dim")
    for m in models[: args.limit]:
        if args.filter and args.filter.lower() not in f"{m.get('model','')} {m.get('provider','')} {m.get('alias','')}".lower():
            continue
        caps = m.get("caps", {})
        cap_str = ",".join(k for k, v in caps.items() if v) if isinstance(caps, dict) else str(caps)[:24]
        table.add_row(
            m.get("model", m.get("id", "—")),
            m.get("provider", "—"),
            m.get("alias", "—"),
            cap_str,
        )
    console.print(table)
    if args.json:
        print_json(data, "Models JSON")


def cmd_keys(client: NinerouterClient, args):
    data = client.list_keys()
    table = Table(title=f"API Keys — {len(data)}", show_lines=False)
    table.add_column("Name", style="cyan")
    table.add_column("Key", style="dim")
    table.add_column("Machine ID", style="dim")
    table.add_column("Created")
    table.add_column("ID", style="dim")
    for k in data:
        table.add_row(
            k.get("name", "—"),
            mask_key(k.get("key", "")),
            k.get("machineId", k.get("machine_id", "—"))[:16],
            k.get("createdAt", k.get("created_at", "—"))[:19],
            k.get("id", "")[:8],
        )
    console.print(table)
    if args.json:
        print_json(data, "Keys JSON")


def cmd_usage(client: NinerouterClient, args):
    stats = client.get_usage_stats(args.period)
    console.print(Panel(JSON(json.dumps(stats, indent=2, ensure_ascii=False)), title=f"Usage Stats — {args.period}"))
    try:
        hist = client.get_usage_history(limit=args.limit)
        items = hist.get("history", hist.get("items", hist.get("data", []))) if isinstance(hist, dict) else hist
        if isinstance(items, list) and items:
            table = Table(title=f"History — {len(items)} records", show_lines=False)
            table.add_column("Time", style="dim")
            table.add_column("Model", style="cyan")
            table.add_column("Provider", style="magenta")
            table.add_column("Tokens", justify="right")
            table.add_column("Cost", justify="right")
            for h in items[: args.limit]:
                table.add_row(
                    h.get("createdAt", h.get("timestamp", h.get("time", "—")))[:19],
                    h.get("model", "—")[:28],
                    h.get("provider", "—")[:16],
                    str(h.get("totalTokens", h.get("tokens", "—"))),
                    str(h.get("cost", "—")),
                )
            console.print(table)
    except Exception as e:
        console.print(f"[yellow]History unavailable: {e}[/]")
    if args.json:
        print_json(stats, "Usage JSON")


def cmd_settings(client: NinerouterClient, args):
    data = client.get_settings()
    console.print(Panel(JSON(json.dumps(data, indent=2, ensure_ascii=False)), title="Settings"))


def cmd_test(client: NinerouterClient, args):
    data = client.test_providers(mode=args.mode, provider_id=args.provider)
    console.print(Panel(JSON(json.dumps(data, indent=2, ensure_ascii=False)), title=f"Test — mode={args.mode}"))


def cmd_v1_models(client: NinerouterClient, args):
    data = client.list_v1_models()
    console.print(Panel(JSON(json.dumps(data, indent=2, ensure_ascii=False)), title="GET /v1/models"))


def cmd_servers(client, args):
    servers = _load_servers_from_file()
    if not servers:
        servers = DEFAULT_SERVERS
    table = Table(title=f"Saved Servers — {len(servers)}", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="magenta")
    table.add_column("Kind", style="yellow")
    table.add_column("API Key", style="dim")
    table.add_column("Description", style="dim")
    for i, s in enumerate(servers, 1):
        hi = detect_host_info(s.url)
        kind = hi["label"] + (" +SSH" if s.ssh_host else "")
        table.add_row(str(i), s.name, s.url, kind, mask_key(s.api_key), s.description)
    console.print(table)
    if args.probe:
        console.print("[dim]Probing...[/]")
        for s in servers:
            res = probe_server(s.url, s.api_key, 5)
            status = "[green]OK[/]" if res["ok"] else f"[red]{res['error'] or res['status']}[/]"
            console.print(f"  {s.name} ({s.url}): {status} {res['latency_ms']}ms")


def cmd_server_add(client, args):
    url = args.url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "http://" + url
    name = args.name or url
    servers = _load_servers_from_file()
    # dedup by url
    for s in servers:
        if s.url == url:
            console.print(f"[yellow]Server already exists: {s.name} — {s.url}[/]")
            if args.force:
                s.name = name
                s.api_key = args.api_key or s.api_key
                save_servers_to_file(servers)
                console.print(f"[green]Updated: {name} — {url}[/]")
            return
    servers.append(ServerProfile(name=name, url=url, api_key=args.api_key or "", description=args.description or ""))
    save_servers_to_file(servers)
    console.print(f"[green]Added: {name} — {url}[/]")
    if args.probe:
        res = probe_server(url, args.api_key or "", 5)
        console.print(f"  Probe: {'[green]OK[/]' if res['ok'] else '[red]FAIL[/]'} {res['error'] or res['status']} {res['latency_ms']}ms")


def cmd_server_remove(client, args):
    servers = _load_servers_from_file()
    target = args.target.strip()
    # match by name or url or index
    new_list = []
    removed = None
    for i, s in enumerate(servers, 1):
        if str(i) == target or s.name == target or s.url == target or s.url.rstrip("/") == target.rstrip("/"):
            removed = s
            continue
        new_list.append(s)
    if not removed:
        console.print(f"[red]Not found: {target}[/]")
        return
    save_servers_to_file(new_list)
    console.print(f"[green]Removed: {removed.name} — {removed.url}[/]")


def cmd_server_use(client, args):
    # Interactive picker if no target, else switch by name/url/index
    servers = _load_servers_from_file()
    if not servers:
        servers = DEFAULT_SERVERS
    target = (args.target or "").strip()
    if not target:
        # interactive
        console.print("[bold]Select server:[/]")
        for i, s in enumerate(servers, 1):
            console.print(f"  [cyan]{i}[/]. [bold]{s.name}[/] — {s.url}  [dim]{s.description}[/]")
        console.print("  [dim]Enter number, name, or URL (or 'q' to cancel)[/]")
        try:
            choice = input("Select> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("[dim]Cancelled[/]")
            return
        if not choice or choice.lower() in ("q", "quit", "exit"):
            console.print("[dim]Cancelled[/]")
            return
        target = choice
    # resolve
    chosen = None
    for i, s in enumerate(servers, 1):
        if str(i) == target or s.name == target or s.url == target or s.url.rstrip("/") == target.rstrip("/"):
            chosen = s
            break
    if not chosen:
        # treat as raw URL
        url = target
        if not url.startswith("http"):
            url = "http://" + url
        url = url.rstrip("/")
        chosen = ServerProfile(name=url, url=url, api_key="", description="Ad-hoc")
    console.print(f"[bold]Selected:[/] {chosen.name} — {chosen.url}")
    res = probe_server(chosen.url, chosen.api_key, 5)
    if res["ok"]:
        console.print(f"[green]Health OK[/] {res['latency_ms']}ms")
    else:
        console.print(f"[yellow]Health check failed:[/] {res['error'] or res['status']}")
    console.print(f"[dim]To use: export NINEROUTER_URL={chosen.url}[/]")
    if chosen.api_key:
        console.print(f"[dim]        export NINEROUTER_KEY={mask_key(chosen.api_key)}[/]")
    console.print(f"[dim]Or: python cli.py --url {chosen.url} providers[/]")
    console.print(f"[dim]Or: python app.py --url {chosen.url}[/]")


def _resolve_profile_for_cli(client, args) -> tuple:
    """Resolve ServerProfile for remote ops. Returns (profile or None, is_remote)."""
    # --server name/url/index
    target = getattr(args, 'server', '') or ''
    if target:
        servers = _load_servers_from_file()
        if not servers:
            servers = DEFAULT_SERVERS
        for i, s in enumerate(servers, 1):
            if str(i) == target or s.name == target or s.url == target or s.url.rstrip('/') == target.rstrip('/'):
                return s, bool(s.ssh_host)
        # not found — treat as URL
        console.print(f"[yellow]Server not found: {target}, using current client URL[/]")
    # fallback: try to find profile matching current client URL
    servers = _load_servers_from_file()
    for s in servers:
        if s.url.rstrip('/') == client.base.rstrip('/'):
            return s, bool(s.ssh_host)
    # no profile — local
    return None, False

def cmd_version(client, args):
    info = get_version_via_api(client)
    table = Table(title="9Router Version", show_lines=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Current", info.current)
    table.add_row("Latest (npm)", info.latest)
    table.add_row("Has Update", "[green]Yes[/]" if info.has_update else "[dim]No[/]")
    table.add_row("Source", info.source)
    if info.error:
        table.add_row("Error", f"[red]{info.error}[/]")
    console.print(table)
    local = get_local_version()
    if local:
        console.print(f"[dim]Local package.json: {local}[/]")
    console.print(f"[dim]URL: {client.base}  Local: {is_local_url(client.base)}[/]")
    # remote SSH info
    profile, is_remote = _resolve_profile_for_cli(client, args)
    if profile and is_remote:
        console.print(f"[dim]Remote SSH: {profile.ssh_target()}  compose: {profile.compose_path or 'auto'}  method: {profile.install_method or 'auto'}[/]")
    elif profile:
        console.print(f"[dim]Profile: {profile.name} — {profile.url}[/]")
    if args.json:
        print_json({"current": info.current, "latest": info.latest, "hasUpdate": info.has_update, "source": info.source}, "Version JSON")


def cmd_update(client, args):
    info = get_version_via_api(client)
    console.print(f"[bold]Current:[/] {info.current}  [bold]Latest:[/] {info.latest}  [bold]Has Update:[/] {info.has_update}")
    profile, is_remote = _resolve_profile_for_cli(client, args)
    if is_remote:
        console.print(f"[bold]Remote:[/] {profile.ssh_target()}  [dim](via SSH)[/]")
        method = args.method or profile.install_method or detect_install_method_remote(profile)
        console.print(f"[bold]Method (remote):[/] {method}")
        plan = build_update_plan(method, args.compose_file or profile.compose_path)
        if isinstance(plan, tuple):
            plan = plan[0] if isinstance(plan[0], list) else []
        if not plan:
            console.print("[red]No update plan for method[/]")
            return
        console.print("[bold]Plan (remote via SSH):[/]")
        for cmd in plan:
            if isinstance(cmd, list):
                console.print(f"  [dim]$[/] {' '.join(cmd)}")
            elif isinstance(cmd, tuple):
                console.print(f"  [dim]$[/] {' '.join(cmd[0])}  [dim](cwd={cmd[1]})[/]")
        if args.dry_run:
            console.print("[yellow]Dry-run — not executing[/]")
            return
        if not args.yes:
            try:
                ans = input(f"Proceed remote update on {profile.ssh_target()}? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print("[dim]Cancelled[/]")
                return
            if ans not in ("y", "yes"):
                console.print("[dim]Cancelled[/]")
                return
        steps = run_update_remote(profile, method, dry_run=False, compose_file=args.compose_file or profile.compose_path)
        for s in steps:
            status = "[green]OK[/]" if s["rc"] == 0 else f"[red]FAIL rc={s['rc']}[/]"
            console.print(Panel(f"[bold]$ {s['cmd']}[/]  [dim]({s['cwd']})[/]  {status}  [dim]remote[/]\n[dim]{s['stdout'][-1500:]}[/]\n[red]{s['stderr'][-1500:]}[/]" if s["stderr"] else f"[bold]$ {s['cmd']}[/]  {status}  [dim]remote[/]\n[dim]{s['stdout'][-1500:]}[/]", title="Step"))
            if s["rc"] != 0:
                console.print("[red]Update stopped due to error[/]")
                break
        else:
            console.print("[green]Remote update completed[/]")
        return
    if not is_local_url(client.base) and not args.force:
        console.print("[yellow]Remote server detected — update must be run on the host where 9Router is installed.[/]")
        console.print("[dim]For remote with SSH: add ssh_host to servers.json and run: python cli.py --server <name> update[/]")
        console.print("[dim]Or ssh manually: npm install -g 9router@latest  OR  docker pull decolua/9router:latest[/]")
        if not info.has_update:
            console.print("[dim]No update available (or cannot determine). Use --force to run anyway.[/]")
            return
        console.print("[dim]Use --force to run update commands anyway (if this host also has 9Router).[/]")
        return
    method = args.method or detect_install_method()
    if method == "unknown":
        console.print("[yellow]Could not detect install method. Specify --method npm|source|docker[/]")
        method = "npm"
    console.print(f"[bold]Method:[/] {method}")
    plan = build_update_plan(method, args.compose_file)
    # build_update_plan for source returns tuple, handle
    if isinstance(plan, tuple):
        plan = plan[0] if isinstance(plan[0], list) else []
    if not plan:
        console.print("[red]No update plan for method[/]")
        return
    console.print("[bold]Plan:[/]")
    for cmd in plan:
        if isinstance(cmd, list):
            console.print(f"  [dim]$[/] {' '.join(cmd)}")
        elif isinstance(cmd, tuple):
            console.print(f"  [dim]$[/] {' '.join(cmd[0])}  [dim](cwd={cmd[1]})[/]")
    if args.dry_run:
        console.print("[yellow]Dry-run — not executing[/]")
        return
    if not args.yes:
        try:
            ans = input("Proceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("[dim]Cancelled[/]")
            return
        if ans not in ("y", "yes"):
            console.print("[dim]Cancelled[/]")
            return
    steps = run_update(method, dry_run=False, compose_file=args.compose_file)
    for s in steps:
        status = "[green]OK[/]" if s["rc"] == 0 else f"[red]FAIL rc={s['rc']}[/]"
        console.print(Panel(f"[bold]$ {s['cmd']}[/]  [dim]({s['cwd']})[/]  {status}\n[dim]{s['stdout'][-1500:]}[/]\n[red]{s['stderr'][-1500:]}[/]" if s["stderr"] else f"[bold]$ {s['cmd']}[/]  {status}\n[dim]{s['stdout'][-1500:]}[/]", title="Step"))
        if s["rc"] != 0:
            console.print("[red]Update stopped due to error[/]")
            break
    else:
        console.print("[green]Update completed[/]")
        # re-check version
        try:
            info2 = get_version_via_api(client)
            console.print(f"[bold]Now:[/] {info2.current}  Latest: {info2.latest}  Has Update: {info2.has_update}")
        except Exception:
            pass


def cmd_docker(client, args):
    # resolve remote profile if --server given
    profile, is_remote = _resolve_profile_for_cli(client, args)
    sub = args.docker_cmd
    if sub == "status":
        info = docker_status_remote(profile) if is_remote else docker_status()
        if not info["available"]:
            console.print(f"[red]Docker not available: {info['error']}[/]")
            return
        console.print(Panel(f"[bold]Compose:[/] {info['compose'] or '—'}", title="Docker Status"))
        table = Table(title="Containers", show_lines=False)
        table.add_column("Name", style="cyan")
        table.add_column("Image", style="magenta")
        table.add_column("Status")
        for c in info["containers"]:
            table.add_row(c.get("name", "—"), c.get("image", "—"), c.get("status", c.get("raw", "—")))
        console.print(table)
        if info["images"]:
            console.print("[bold]Images:[/]")
            for img in info["images"]:
                console.print(f"  {img}")
        if args.json:
            print_json(info, "Docker JSON")
    elif sub == "logs":
        if is_remote:
            rc, out, err = docker_logs_remote(profile, args.container, args.tail)
        else:
            rc, out, err = docker_logs(args.container, args.tail)
        if rc != 0:
            console.print(f"[red]docker logs failed rc={rc}: {err[:500]}[/]")
        else:
            console.print(Panel(out[-6000:] or "[dim]No logs[/]", title=f"docker logs {args.container} --tail {args.tail}"))
            if err:
                console.print(f"[yellow]{err[-1000:]}[/]")
    elif sub == "pull":
        method = "docker"
        console.print(f"[bold]Pulling {args.image}...[/]" + (" [dim](remote)[/]" if is_remote else ""))
        if is_remote:
            from updater import _run_remote
            rc, out, err = _run_remote(profile, f"docker pull {args.image}", timeout=300)
        else:
            from updater import run_cmd
            rc, out, err = run_cmd(["docker", "pull", args.image], timeout=300)
        status = "[green]OK[/]" if rc == 0 else f"[red]FAIL rc={rc}[/]"
        console.print(Panel(f"{status}\n[dim]{out[-2000:]}[/]\n[red]{err[-2000:]}[/]" if err else f"{status}\n[dim]{out[-2000:]}[/]", title=f"docker pull {args.image}"))
    elif sub == "restart":
        if is_remote:
            from updater import _run_remote
            target = args.container or "9router"
            # remote: try compose then docker restart
            compose = profile.compose_path if profile and profile.compose_path else None
            if not compose:
                rc_tmp, out_tmp, _ = _run_remote(profile, "ls -1 docker-compose.yml 9router-master/docker-compose.yml 9router-master/9router-master/docker-compose.yml 2>/dev/null | head -1", timeout=10)
                if rc_tmp == 0 and out_tmp.strip():
                    compose = out_tmp.strip()
            if compose:
                console.print(f"[bold]Restart via compose (remote):[/] {compose}")
                rc, out, err = _run_remote(profile, f"docker compose -f {compose} restart {target}", timeout=60)
                if rc == 0:
                    console.print(f"[green]Restarted via compose (remote): {target}[/]")
                    return
                console.print(f"[yellow]Compose restart failed, trying docker restart...[/] {err[:300]}")
            rc, out, err = _run_remote(profile, f"docker restart {target}", timeout=30)
            status = "[green]OK[/]" if rc == 0 else f"[red]FAIL rc={rc}[/]"
            console.print(Panel(f"{status} {target} [dim](remote)[/]\n[dim]{out[-1000:]}[/]\n[red]{err[-1000:]}[/]" if err else f"{status} {target} [dim](remote)[/]\n[dim]{out[-1000:]}[/]", title="docker restart"))
            return
        from updater import run_cmd
        target = args.container or "9router"
        # try compose first
        compose = None
        for p in [__import__("pathlib").Path.cwd() / "docker-compose.yml", __import__("pathlib").Path.cwd() / "9router-master" / "docker-compose.yml", __import__("pathlib").Path.cwd() / "9router-master" / "9router-master" / "docker-compose.yml"]:
            if p.exists():
                compose = str(p)
                break
        if compose and not args.no_compose:
            console.print(f"[bold]Restart via compose:[/] {compose}")
            rc, out, err = run_cmd(["docker", "compose", "-f", compose, "restart", target], timeout=60)
            if rc == 0:
                console.print(f"[green]Restarted via compose: {target}[/]")
                return
            console.print(f"[yellow]Compose restart failed, trying docker restart...[/] {err[:300]}")
        rc, out, err = run_cmd(["docker", "restart", target], timeout=30)
        status = "[green]OK[/]" if rc == 0 else f"[red]FAIL rc={rc}[/]"
        console.print(Panel(f"{status} {target}\n[dim]{out[-1000:]}[/]\n[red]{err[-1000:]}[/]" if err else f"{status} {target}\n[dim]{out[-1000:]}[/]", title="docker restart"))
    elif sub == "update":
        # docker update = pull + up -d (remote via SSH if profile is remote)
        if is_remote:
            compose = args.compose_file or (profile.compose_path if profile else None)
            if args.dry_run:
                console.print("[yellow]Dry-run (remote)[/]")
                plan = build_update_plan("docker", compose)
                for cmd in plan:
                    console.print(f"  [dim]$[/] {' '.join(cmd)} [dim](remote)[/]")
                return
            steps = run_update_remote(profile, "docker", dry_run=False, compose_file=compose)
            for s in steps:
                status = "[green]OK[/]" if s["rc"] == 0 else f"[red]FAIL rc={s['rc']}[/]"
                console.print(Panel(f"[bold]$ {s['cmd']}[/]  {status} [dim](remote)[/]\n[dim]{s['stdout'][-1500:]}[/]\n[red]{s['stderr'][-1500:]}[/]" if s["stderr"] else f"[bold]$ {s['cmd']}[/]  {status} [dim](remote)[/]\n[dim]{s['stdout'][-1500:]}[/]", title="Step"))
                if s["rc"] != 0:
                    break
            else:
                console.print("[green]Docker update completed (remote)[/]")
            return
        compose = args.compose_file
        if not compose:
            for p in [__import__("pathlib").Path.cwd() / "docker-compose.yml", __import__("pathlib").Path.cwd() / "9router-master" / "docker-compose.yml", __import__("pathlib").Path.cwd() / "9router-master" / "9router-master" / "docker-compose.yml"]:
                if p.exists():
                    compose = str(p)
                    break
        if args.dry_run:
            console.print("[yellow]Dry-run[/]")
            plan = build_update_plan("docker", compose)
            for cmd in plan:
                console.print(f"  [dim]$[/] {' '.join(cmd)}")
            return
        steps = run_update("docker", dry_run=False, compose_file=compose)
        for s in steps:
            status = "[green]OK[/]" if s["rc"] == 0 else f"[red]FAIL rc={s['rc']}[/]"
            console.print(Panel(f"[bold]$ {s['cmd']}[/]  {status}\n[dim]{s['stdout'][-1500:]}[/]\n[red]{s['stderr'][-1500:]}[/]" if s["stderr"] else f"[bold]$ {s['cmd']}[/]  {status}\n[dim]{s['stdout'][-1500:]}[/]", title="Step"))
            if s["rc"] != 0:
                break
        else:
            console.print("[green]Docker update completed[/]")


def cmd_detect(client, args):
    from updater import auto_detect_servers, detect_host_info
    from client import detect_host_info as c_dhi
    console.print("[bold]Auto-detecting local 9Router instances...[/]")
    found = auto_detect_servers(timeout=3)
    if not found:
        console.print("[yellow]No local instances found (tried localhost:20128, 20127, 3000, host.docker.internal, LAN IP)[/]")
        console.print("[dim]Make sure 9Router is running: cd 9router-master/9router-master && npm run dev[/]")
        return
    table = Table(title=f"Detected — {len(found)} reachable", show_lines=False)
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="magenta")
    table.add_column("Kind", style="yellow")
    table.add_column("Status", style="green")
    for f in found:
        hi = c_dhi(f["url"])
        table.add_row(f["name"], f["url"], hi["label"], "OK")
    console.print(table)
    # Also show current servers.json classification
    servers = _load_servers_from_file()
    if servers:
        console.print("\n[bold]Saved servers classification:[/]")
        table2 = Table(show_lines=False)
        table2.add_column("Name", style="cyan")
        table2.add_column("URL", style="magenta")
        table2.add_column("Kind", style="yellow")
        table2.add_column("SSH", style="dim")
        for s in servers:
            hi = c_dhi(s.url)
            table2.add_row(s.name, s.url, hi["label"], s.ssh_host or "—")
        console.print(table2)
    if args.json:
        print_json({"detected": found, "saved": [{"name": s.name, "url": s.url, "kind": c_dhi(s.url)["kind"]} for s in servers]}, "Detect JSON")

def main():
    parser = argparse.ArgumentParser(description=f"9Router CLI Dashboard v{APP_VERSION} (standalone, Rich)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    parser.add_argument("--url", default=None, help="9Router base URL (env NINEROUTER_URL)")
    parser.add_argument("--api-key", default=None, help="API key (env NINEROUTER_KEY)")
    parser.add_argument("--config", default=None, help="Path to config.toml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_health = sub.add_parser("health", help="GET /api/health")
    p_health.set_defaults(func=cmd_health)

    p_prov = sub.add_parser("providers", help="GET /api/providers")
    p_prov.add_argument("--filter", default="", help="Filter by name/provider")
    p_prov.add_argument("--json", action="store_true", help="Also dump JSON")
    p_prov.set_defaults(func=cmd_providers)

    p_nodes = sub.add_parser("nodes", help="GET /api/provider-nodes")
    p_nodes.add_argument("--filter", default="", help="Filter")
    p_nodes.add_argument("--json", action="store_true")
    p_nodes.set_defaults(func=cmd_nodes)

    p_combos = sub.add_parser("combos", help="GET /api/combos")
    p_combos.add_argument("--json", action="store_true")
    p_combos.set_defaults(func=cmd_combos)

    p_models = sub.add_parser("models", help="GET /api/models")
    p_models.add_argument("--filter", default="", help="Filter")
    p_models.add_argument("--limit", type=int, default=100, help="Max rows")
    p_models.add_argument("--json", action="store_true")
    p_models.set_defaults(func=cmd_models)

    p_v1 = sub.add_parser("v1-models", help="GET /v1/models")
    p_v1.set_defaults(func=cmd_v1_models)

    p_keys = sub.add_parser("keys", help="GET /api/keys")
    p_keys.add_argument("--json", action="store_true")
    p_keys.set_defaults(func=cmd_keys)

    p_usage = sub.add_parser("usage", help="GET /api/usage/*")
    p_usage.add_argument("--period", default="7d", choices=["today", "24h", "7d", "30d", "60d", "all"])
    p_usage.add_argument("--limit", type=int, default=20)
    p_usage.add_argument("--json", action="store_true")
    p_usage.set_defaults(func=cmd_usage)

    p_settings = sub.add_parser("settings", help="GET /api/settings")
    p_settings.set_defaults(func=cmd_settings)

    p_test = sub.add_parser("test", help="POST /api/providers/test-batch")
    p_test.add_argument("--mode", default="all", choices=["all", "provider", "oauth", "free", "apikey", "compatible"])
    p_test.add_argument("--provider", default=None, help="Provider ID (for mode=provider)")
    p_test.set_defaults(func=cmd_test)

    p_dash = sub.add_parser("dashboard", help="Launch Textual TUI dashboard")
    p_dash.set_defaults(func=lambda c, a: _launch_tui(c))

    p_servers = sub.add_parser("servers", help="List saved servers (servers.json / config.toml [[servers]])")
    p_servers.add_argument("--probe", action="store_true", help="Probe each server health")
    p_servers.set_defaults(func=cmd_servers)

    p_sadd = sub.add_parser("server-add", help="Add a server to servers.json")
    p_sadd.add_argument("url", help="Server URL (e.g. http://localhost:20128 or https://...trycloudflare.com)")
    p_sadd.add_argument("--name", default="", help="Display name")
    p_sadd.add_argument("--api-key", default="", help="API key if requireApiKey=true")
    p_sadd.add_argument("--description", default="", help="Description")
    p_sadd.add_argument("--probe", action="store_true", help="Probe after add")
    p_sadd.add_argument("--force", action="store_true", help="Update if exists")
    p_sadd.set_defaults(func=cmd_server_add)

    p_srem = sub.add_parser("server-remove", help="Remove a server from servers.json")
    p_srem.add_argument("target", help="Name, URL, or index (from servers list)")
    p_srem.set_defaults(func=cmd_server_remove)

    p_suse = sub.add_parser("server-use", help="Pick a server (interactive if no target)")
    p_suse.add_argument("target", nargs="?", default="", help="Name, URL, or index; empty = interactive picker")
    p_suse.set_defaults(func=cmd_server_use)

    p_detect = sub.add_parser("detect", help="Auto-detect local 9Router instances (localhost, LAN IP, Docker)")
    p_detect.add_argument("--json", action="store_true", help="Dump JSON")
    p_detect.set_defaults(func=cmd_detect)

    p_ver = sub.add_parser("version", help="Show 9Router version (GET /api/version + npm latest)")
    p_ver.add_argument("--json", action="store_true", help="Dump JSON")
    p_ver.add_argument("--server", default="", help="Server name/url/index from servers.json (for remote SSH info)")
    p_ver.set_defaults(func=cmd_version)

    p_up = sub.add_parser("update", help="Update 9Router (npm / source / docker) — local or remote via SSH")
    p_up.add_argument("--method", choices=["npm", "source", "docker"], default=None, help="Install method (auto-detect if omitted)")
    p_up.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    p_up.add_argument("--yes", action="store_true", help="Skip confirmation")
    p_up.add_argument("--force", action="store_true", help="Run even if remote URL without SSH")
    p_up.add_argument("--compose-file", default=None, help="Path to docker-compose.yml (for docker method)")
    p_up.add_argument("--server", default="", help="Server name/url/index from servers.json (for remote SSH)")
    p_up.set_defaults(func=cmd_update)

    p_docker = sub.add_parser("docker", help="Docker management for 9router (local or remote via SSH)")
    p_docker.add_argument("--server", default="", help="Server name/url/index from servers.json (for remote SSH)")
    dsub = p_docker.add_subparsers(dest="docker_cmd", required=True)
    p_dstat = dsub.add_parser("status", help="docker ps + images + compose")
    p_dstat.add_argument("--json", action="store_true")
    p_dstat.set_defaults(func=cmd_docker)
    p_dlogs = dsub.add_parser("logs", help="docker logs")
    p_dlogs.add_argument("--container", default="9router", help="Container name")
    p_dlogs.add_argument("--tail", type=int, default=100, help="Tail lines")
    p_dlogs.set_defaults(func=cmd_docker)
    p_dpull = dsub.add_parser("pull", help="docker pull")
    p_dpull.add_argument("--image", default="decolua/9router:latest", help="Image to pull")
    p_dpull.set_defaults(func=cmd_docker)
    p_drest = dsub.add_parser("restart", help="docker restart (or compose restart)")
    p_drest.add_argument("--container", default="9router", help="Container name")
    p_drest.add_argument("--no-compose", action="store_true", help="Force docker restart, not compose")
    p_drest.set_defaults(func=cmd_docker)
    p_dup = dsub.add_parser("update", help="docker compose pull + up -d (or docker pull)")
    p_dup.add_argument("--compose-file", default=None, help="Path to docker-compose.yml")
    p_dup.add_argument("--dry-run", action="store_true")
    p_dup.set_defaults(func=cmd_docker)

    args = parser.parse_args()

    cfg = load_config_from_env_and_file(args.config)
    if args.url:
        cfg.url = args.url
    if args.api_key:
        cfg.api_key = args.api_key
    if os.getenv("NINEROUTER_URL"):
        cfg.url = os.getenv("NINEROUTER_URL", cfg.url)
    if os.getenv("NINEROUTER_KEY"):
        cfg.api_key = os.getenv("NINEROUTER_KEY", cfg.api_key)

    client = NinerouterClient(cfg)

    # health check hint (skip for servers management, detect, dashboard)
    if args.cmd not in ("dashboard", "servers", "server-add", "server-remove", "server-use", "detect", "version", "update", "docker"):
        try:
            h = client.health()
            if not h.get("ok"):
                console.print(f"[yellow]Warning: health check returned {h}[/]")
        except Exception as e:
            console.print(f"[red]Cannot reach 9Router at {client.base}: {e}[/]")
            console.print("[dim]Set NINEROUTER_URL or --url, and NINEROUTER_KEY if requireApiKey=true[/]")
            sys.exit(1)

    args.func(client, args)


def _launch_tui(client: NinerouterClient):
    from app import NineRouterTUI
    app = NineRouterTUI(client)
    app.run()


if __name__ == "__main__":
    main()
