from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Label, Static, Select

from client import NinerouterClient
from tui.helpers import _store_plain, fmt_time, mask_key, status_style

class UpdatePane(Static):
    def __init__(self, client, **kw):
        super().__init__(**kw)
        self.client = client
        self._version_info = None
        self._docker_info = None

    def compose(self) -> ComposeResult:
        yield Label("Update & Docker — 9Router Version & Container Management", id="update-title")
        yield Horizontal(
            Button("Check Version", id="btn-update-check", variant="primary"),
            Button("Update (dry-run)", id="btn-update-dry", variant="default"),
            Button("Update Now", id="btn-update-now", variant="success"),
            Select([("auto", "auto"), ("npm", "npm"), ("source", "source"), ("docker", "docker")], value="auto", id="select-update-method"),
        )
        yield Static("", id="update-version-body")
        yield Horizontal(
            Button("Docker Status", id="btn-docker-status", variant="primary"),
            Button("Docker Logs", id="btn-docker-logs", variant="default"),
            Button("Docker Pull", id="btn-docker-pull", variant="default"),
            Button("Docker Restart", id="btn-docker-restart", variant="default"),
            Button("Docker Update", id="btn-docker-update", variant="success"),
        )
        yield Static("", id="update-docker-body")
        yield Label("Backup & Restore — data.sqlite + history (local & SSH)", id="backup-title")
        yield Horizontal(
            Button("Backup Now", id="btn-backup-now", variant="success"),
            Button("List Backups", id="btn-backup-list", variant="default"),
            Button("Restore…", id="btn-backup-restore", variant="default"),
        )
        yield Static("", id="backup-body")
        yield Horizontal(Button("Copy Log", id="btn-update-copy", variant="default"))
        yield Static("", id="update-log")

    def on_mount(self) -> None:
        self.refresh_version()

    def _get_profile(self):
        # find ServerProfile matching current client URL
        try:
            from client import _load_servers_from_file
            for s in _load_servers_from_file():
                if s.url.rstrip('/') == self.client.base.rstrip('/'):
                    return s
        except Exception:
            pass
        return None

    @work(exclusive=True)
    async def refresh_version(self) -> None:
        body = self.query_one("#update-version-body", Static)
        body.update("Checking version...")
        try:
            from updater import get_version_via_api, get_local_version, detect_host_info
            info = await asyncio.to_thread(get_version_via_api, self.client)
            self._version_info = info
            local = get_local_version()
            host_info = detect_host_info(self.client.base)
            kind = host_info["kind"]
            label = host_info["label"]
            profile = self._get_profile()
            is_remote_ssh = bool(profile and profile.ssh_host)
            # color by kind
            kind_color = {"local": "green", "private-ip": "cyan", "public-ip": "yellow", "domain": "yellow", "tunnel": "magenta"}.get(kind, "white")
            lines = []
            lines.append(f"[bold]Current:[/] {info.current}   [bold]Latest:[/] {info.latest}   [bold]Has Update:[/] {'[green]Yes[/]' if info.has_update else '[dim]No[/]'}")
            lines.append(f"[bold]Source:[/] {info.source}   [bold]Local pkg:[/] {local or '—'}")
            lines.append(f"[bold]URL:[/] {self.client.base}  [{kind_color}]({label}: {kind})[/]  host={host_info['host'] or '—'}")
            if profile and is_remote_ssh:
                lines.append(f"[bold]SSH:[/] {profile.ssh_target()}  [green](remote Docker via SSH)[/]  compose: {profile.compose_path or 'auto'}")
            elif profile:
                lines.append(f"[bold]Profile:[/] {profile.name} — {profile.description}")
            if info.error:
                lines.append(f"[red]Error: {info.error}[/]")
            if kind in ("public-ip", "domain") and not is_remote_ssh:
                lines.append("[yellow]Public VPS detected — add ssh_host to servers.json for remote Docker/update via SSH.[/]")
                lines.append("[dim]CLI: python cli.py --server VPS docker status  |  python cli.py --server VPS update[/]")
            elif kind == "tunnel":
                lines.append("[dim]Tunnel — remote, no Docker SSH. Use VPS SSH for Docker management.[/]")
            body.update("\n".join(lines))
        except Exception as e:
            body.update(f"[red]{e}[/]")

    @work(exclusive=True)
    async def refresh_docker(self) -> None:
        body = self.query_one("#update-docker-body", Static)
        body.update("Checking docker...")
        try:
            profile = self._get_profile()
            is_remote = bool(profile and profile.ssh_host)
            if is_remote:
                from updater import docker_status_remote
                info = await asyncio.to_thread(docker_status_remote, profile)
            else:
                from updater import docker_status
                info = await asyncio.to_thread(docker_status)
            self._docker_info = info
            if not info["available"]:
                body.update(f"[red]Docker not available: {info['error']}[/] {'[dim](remote)[/]' if is_remote else ''}")
                return
            lines = []
            prefix = "[dim](remote)[/] " if is_remote else ""
            lines.append(f"{prefix}[bold]Compose:[/] {info['compose'] or '—'}")
            if info["containers"]:
                for c in info["containers"]:
                    lines.append(f"  {c.get('name','—')}  {c.get('image','—')}  {c.get('status','—')}")
            else:
                lines.append("  [dim]No 9router containers found[/]")
            if info["images"]:
                lines.append(f"[bold]Images:[/] {', '.join(info['images'][:3])}")
            body.update("\n".join(lines))
        except Exception as e:
            body.update(f"[red]{e}[/]")

    def _get_method(self) -> str:
        try:
            sel = self.query_one("#select-update-method", Select)
            v = sel.value or "auto"
            if v == "auto":
                profile = self._get_profile()
                if profile and profile.ssh_host:
                    from updater import detect_install_method_remote
                    return detect_install_method_remote(profile)
                from updater import detect_install_method
                return detect_install_method()
            return v
        except Exception:
            return "npm"

    @on(Button.Pressed, "#btn-update-check")
    def on_check(self) -> None:
        self.refresh_version()

    @on(Button.Pressed, "#btn-update-dry")
    async def on_dry(self) -> None:
        log = self.query_one("#update-log", Static)
        method = self._get_method()
        log.update(f"[dim]Dry-run plan for {method}...[/]")
        try:
            from updater import build_update_plan
            plan = await asyncio.to_thread(build_update_plan, method, None)
            if isinstance(plan, tuple):
                plan = plan[0] if isinstance(plan[0], list) else []
            lines = [f"[bold]Method:[/] {method}  [dim](dry-run)[/]"]
            for cmd in plan:
                if isinstance(cmd, list):
                    lines.append(f"  $ {' '.join(cmd)}")
                elif isinstance(cmd, tuple):
                    lines.append(f"  $ {' '.join(cmd[0])}  (cwd={cmd[1]})")
            if not lines[1:]:
                lines.append("  [dim]No plan[/]")
            log.update("\n".join(lines))
        except Exception as e:
            log.update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-update-now")
    async def on_update_now(self) -> None:
        log = self.query_one("#update-log", Static)
        method = self._get_method()
        profile = self._get_profile()
        is_remote = bool(profile and profile.ssh_host)
        if is_remote:
            log.update(f"[yellow]Updating remote {profile.ssh_target()} via {method} (SSH)...[/]")
            try:
                from updater import run_update_remote
                steps = await asyncio.to_thread(run_update_remote, profile, method, False, None, None)
                lines = []
                for s in steps:
                    status = "[green]OK[/]" if s["rc"] == 0 else f"[red]FAIL rc={s['rc']}[/]"
                    lines.append(f"$ {s['cmd']}  {status}  [dim](remote)[/]")
                    if s["stdout"]:
                        lines.append(f"[dim]{s['stdout'][-800:]}[/]")
                    if s["stderr"]:
                        lines.append(f"[red]{s['stderr'][-800:]}[/]")
                    if s["rc"] != 0:
                        break
                else:
                    lines.append("[green]Remote update completed[/]")
                log.update("\n".join(lines))
                self.refresh_version()
            except Exception as e:
                log.update(f"[red]{e}[/]")
            return
        else:
            from updater import is_local_url
            if not is_local_url(self.client.base):
                log.update("[red]Remote server without SSH — cannot update from here. Add ssh_host to servers.json.[/]")
                return
            log.update(f"[yellow]Updating via {method}...[/]")
            try:
                from updater import run_update
                steps = await asyncio.to_thread(run_update, method, False, None, None)
                lines = []
                for s in steps:
                    status = "[green]OK[/]" if s["rc"] == 0 else f"[red]FAIL rc={s['rc']}[/]"
                    lines.append(f"$ {s['cmd']}  {status}")
                    if s["stdout"]:
                        lines.append(f"[dim]{s['stdout'][-800:]}[/]")
                    if s["stderr"]:
                        lines.append(f"[red]{s['stderr'][-800:]}[/]")
                    if s["rc"] != 0:
                        break
                else:
                    lines.append("[green]Update completed[/]")
                log.update("\n".join(lines))
                self.refresh_version()
            except Exception as e:
                log.update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-update-copy")
    def on_copy(self) -> None:
        try:
            w = self.query_one("#update-log", Static)
            plain = getattr(w, "_plain_text", "") or ""
            if plain:
                self.app._copy_text(plain)  # type: ignore[attr-defined]
            else:
                self.app.notify("Nothing to copy", severity="warning")  # type: ignore[attr-defined]
        except Exception:
            pass

    @on(Button.Pressed, "#btn-docker-status")
    def on_docker_status(self) -> None:
        self.refresh_docker()

    @on(Button.Pressed, "#btn-docker-logs")
    async def on_docker_logs(self) -> None:
        log = self.query_one("#update-log", Static)
        log.update("[dim]Fetching docker logs...[/]")
        try:
            profile = self._get_profile()
            is_remote = bool(profile and profile.ssh_host)
            if is_remote:
                from updater import docker_logs_remote
                rc, out, err = await asyncio.to_thread(docker_logs_remote, profile, "9router", 100)
            else:
                from updater import docker_logs
                rc, out, err = await asyncio.to_thread(docker_logs, "9router", 100)
            if rc != 0:
                log.update(f"[red]docker logs failed rc={rc}: {err[:800]}[/]")
            else:
                log.update(f"[dim]{out[-4000:] or 'No logs'}[/]")
        except Exception as e:
            log.update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-docker-pull")
    async def on_docker_pull(self) -> None:
        log = self.query_one("#update-log", Static)
        profile = self._get_profile()
        is_remote = bool(profile and profile and profile.ssh_host)
        log.update(f"[dim]docker pull decolua/9router:latest ...{' (remote)' if is_remote else ''}[/]")
        try:
            if is_remote:
                from updater import _run_remote
                rc, out, err = await asyncio.to_thread(_run_remote, profile, "docker pull decolua/9router:latest", 300)
            else:
                from updater import run_cmd
                rc, out, err = await asyncio.to_thread(run_cmd, ["docker", "pull", "decolua/9router:latest"], None, 300)
            status = "[green]OK[/]" if rc == 0 else f"[red]FAIL rc={rc}[/]"
            log.update(f"{status}\n[dim]{out[-2000:]}[/]\n[red]{err[-2000:]}[/]" if err else f"{status}\n[dim]{out[-2000:]}[/]")
        except Exception as e:
            log.update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-docker-restart")
    async def on_docker_restart(self) -> None:
        log = self.query_one("#update-log", Static)
        profile = self._get_profile()
        is_remote = bool(profile and profile.ssh_host)
        log.update(f"[dim]Restarting 9router...{' (remote)' if is_remote else ''}[/]")
        try:
            if is_remote:
                from updater import _run_remote
                compose = profile.compose_path
                if not compose:
                    rc_tmp, out_tmp, _ = await asyncio.to_thread(_run_remote, profile, "ls -1 docker-compose.yml 9router-master/docker-compose.yml 9router-master/9router-master/docker-compose.yml 2>/dev/null | head -1", 10)
                    if rc_tmp == 0 and out_tmp.strip():
                        compose = out_tmp.strip()
                if compose:
                    rc, out, err = await asyncio.to_thread(_run_remote, profile, f"docker compose -f {compose} restart 9router", 60)
                    if rc == 0:
                        log.update(f"[green]Restarted via compose (remote): 9router[/]\n[dim]{out[-800:]}[/]")
                        return
                rc, out, err = await asyncio.to_thread(_run_remote, profile, "docker restart 9router", 30)
            else:
                from updater import run_cmd
                import pathlib
                compose = None
                for p in [pathlib.Path.cwd() / "docker-compose.yml", pathlib.Path.cwd() / "9router-master" / "docker-compose.yml", pathlib.Path.cwd() / "9router-master" / "9router-master" / "docker-compose.yml"]:
                    if p.exists():
                        compose = str(p)
                        break
                if compose:
                    rc, out, err = await asyncio.to_thread(run_cmd, ["docker", "compose", "-f", compose, "restart", "9router"], None, 60)
                    if rc == 0:
                        log.update(f"[green]Restarted via compose: 9router[/]\n[dim]{out[-800:]}[/]")
                        return
                rc, out, err = await asyncio.to_thread(run_cmd, ["docker", "restart", "9router"], None, 30)
            status = "[green]OK[/]" if rc == 0 else f"[red]FAIL rc={rc}[/]"
            log.update(f"{status} 9router\n[dim]{out[-800:]}[/]\n[red]{err[-800:]}[/]" if err else f"{status} 9router\n[dim]{out[-800:]}[/]")
        except Exception as e:
            log.update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-docker-update")
    async def on_docker_update(self) -> None:
        log = self.query_one("#update-log", Static)
        profile = self._get_profile()
        is_remote = bool(profile and profile.ssh_host)
        log.update(f"[dim]Docker update: compose pull + up -d ...{' (remote)' if is_remote else ''}[/]")
        try:
            if is_remote:
                from updater import run_update_remote
                steps = await asyncio.to_thread(run_update_remote, profile, "docker", False, None, None)
            else:
                from updater import run_update
                steps = await asyncio.to_thread(run_update, "docker", False, None, None)
            lines = []
            for s in steps:
                status = "[green]OK[/]" if s["rc"] == 0 else f"[red]FAIL rc={s['rc']}[/]"
                lines.append(f"$ {s['cmd']}  {status}")
                if s["stdout"]:
                    lines.append(f"[dim]{s['stdout'][-800:]}[/]")
                if s["stderr"]:
                    lines.append(f"[red]{s['stderr'][-800:]}[/]")
                if s["rc"] != 0:
                    break
            else:
                lines.append("[green]Docker update completed[/]")
            log.update("\n".join(lines))
        except Exception as e:
            log.update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-backup-now")
    async def on_backup_now(self) -> None:
        body = self.query_one("#backup-body", Static)
        body.update("[dim]Backing up...[/]")
        try:
            from tui.backup import export_via_api, save_backup_json, get_data_file, get_backup_dir
            import shutil
            profile = self._get_profile()
            is_remote = bool(profile and profile.ssh_host)
            # 1. API export (always works)
            payload = await asyncio.to_thread(export_via_api, self.client)
            path = await asyncio.to_thread(save_backup_json, payload)
            lines = [f"[green]Backup JSON:[/] {path}"]
            # 2. Try file copy for .sqlite (local or SSH)
            try:
                if is_remote:
                    from updater import _run_remote
                    remote_path = str(get_data_file(profile))
                    local_path = str(get_backup_dir() / f"{path.replace('.json','.sqlite')}")
                    # Use ssh cat > local
                    rc, out, err = await asyncio.to_thread(_run_remote, profile, f"cat {remote_path} 2>&1 | base64 -w0 | head -c 100", timeout=10)
                    # For now just note remote path — full binary copy needs scp
                    lines.append(f"[dim]Remote DB: {remote_path} (use scp for full .sqlite)[/]")
                else:
                    src = get_data_file()
                    if src.exists():
                        dst = str(get_backup_dir() / f"{path.replace('.json','').split('/')[-1]}.sqlite")
                        # path already has .json, derive sqlite name
                        import pathlib
                        sqlite_dst = pathlib.Path(path).with_suffix(".sqlite")
                        shutil.copy2(src, sqlite_dst)
                        lines.append(f"[green]DB copied:[/] {sqlite_dst}")
            except Exception as e:
                lines.append(f"[yellow]DB copy skipped: {e}[/]")
            body.update("\n".join(lines))
            self.query_one("#update-log", Static).update("\n".join(lines))
        except Exception as e:
            body.update(f"[red]Backup failed: {e}[/]")

    @on(Button.Pressed, "#btn-backup-list")
    def on_backup_list(self) -> None:
        try:
            from tui.backup import list_backups
            files = list_backups()
            body = self.query_one("#backup-body", Static)
            if not files:
                body.update("[dim]No backups found in 9router-backup/[/]")
            else:
                lines = [f"[bold]{len(files)} backup(s):[/]"]
                for f in files[:10]:
                    lines.append(f"  {f}")
                body.update("\n".join(lines))
        except Exception as e:
            self.query_one("#backup-body", Static).update(f"[red]{e}[/]")

    @on(Button.Pressed, "#btn-backup-restore")
    def on_backup_restore(self) -> None:
        from tui.screens.backup_restore import BackupRestoreScreen
        self.app.push_screen(BackupRestoreScreen(self.client, self._get_profile(), self._on_restore_done))

    def _on_restore_done(self, ok: bool) -> None:
        if ok:
            self.query_one("#backup-body", Static).update("[green]Restore completed — restart 9Router if needed[/]")
            self.refresh_version()
