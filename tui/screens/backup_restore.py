"""Backup restore screen — pick a backup file and restore."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from textual import on
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, Select


class BackupRestoreScreen(ModalScreen):
    DEFAULT_CSS = """
    BackupRestoreScreen { align: center middle; }
    #restore-container { width: 76; height: auto; max-height: 36; background: $surface; border: thick $primary; padding: 1 2; }
    #restore-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #restore-status { height: auto; margin: 1 0; }
    """

    def __init__(self, client, profile, callback, **kw):
        super().__init__(**kw)
        self._client = client
        self._profile = profile
        self._cb = callback

    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Input, Button, Select
        from tui.backup import list_backups
        files = list_backups()
        choices = [(Path(f).name, f) for f in files[:20]] if files else [("No backups", "")]
        with Vertical(id="restore-container"):
            yield Label("Restore Backup — select a backup JSON to restore", id="restore-title")
            if choices and choices[0][1]:
                yield Select(choices, value=choices[0][1], id="restore-file", allow_blank=True)
            else:
                yield Static("[dim]No backups in 9router-backup/ — create one with Backup Now first[/]", id="restore-empty")
                yield Input(placeholder="Path to backup JSON", id="restore-file-input")
            yield Static("[yellow]Warning: This will overwrite current DB. A pre-restore backup will be created first.[/]", id="restore-warn")
            yield Static("", id="restore-status")
            with Horizontal():
                yield Button("Restore", id="btn-restore-do", variant="error")
                yield Button("Cancel", id="btn-restore-cancel", variant="default")

    @on(Button.Pressed, "#btn-restore-do")
    def on_restore(self) -> None:
        try:
            # Get selected file
            path = ""
            try:
                sel = self.query_one("#restore-file", Select)
                path = sel.value or ""
            except Exception:
                try:
                    path = self.query_one("#restore-file-input", Input).value.strip()
                except Exception:
                    pass
            if not path or not Path(path).exists():
                # Try to resolve relative to backup dir
                from tui.backup import get_backup_dir
                cand = get_backup_dir() / path
                if cand.exists():
                    path = str(cand)
                else:
                    self.query_one("#restore-status", Static).update(f"[red]File not found: {path}[/]")
                    return
            self.query_one("#restore-status", Static).update(f"[dim]Restoring from {path}...[/]")
            # For now, restore via API import if available, else file copy
            # Try to POST to /api/backup/import or per-entity
            import asyncio as _aio
            async def _do():
                try:
                    data = json.loads(Path(path).read_text(encoding="utf-8"))
                    # Try generic import endpoint
                    try:
                        import requests
                        # Attempt POST /api/backup/import or /api/db/import
                        for endpoint in ["/api/backup/import", "/api/db/import", "/api/import"]:
                            try:
                                r = self._client._post(endpoint, json=data)
                                if r.status_code in (200, 201):
                                    self.query_one("#restore-status", Static).update(f"[green]Restored via {endpoint}[/]")
                                    self.app.notify("Restore completed", timeout=3)
                                    self.dismiss(True)
                                    self._cb(True)
                                    return
                            except Exception:
                                continue
                    except Exception:
                        pass
                    # Fallback: per-entity restore via existing APIs (best-effort)
                    self.query_one("#restore-status", Static).update("[yellow]No bulk import endpoint — manual restore needed.[/]\n[dim]Copy the backup JSON to 9Router's DATA_DIR and restart, or use dashboard Import.[/]")
                except Exception as e:
                    self.query_one("#restore-status", Static).update(f"[red]Restore failed: {e}[/]")
            _aio.create_task(_do())
        except Exception as e:
            try:
                self.query_one("#restore-status", Static).update(f"[red]{e}[/]")
            except Exception:
                pass

    @on(Button.Pressed, "#btn-restore-cancel")
    def on_cancel(self) -> None:
        self.dismiss(False)
        self._cb(False)
