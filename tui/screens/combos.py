from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Static, Select, TextArea

from client import NinerouterClient

class ComboEditScreen(ModalScreen):
    DEFAULT_CSS = """
    ComboEditScreen { align: center middle; }
    #combo-edit-container { width: 80; height: auto; max-height: 42; background: $surface; border: thick $primary; padding: 1 2; }
    #combo-edit-title { text-style: bold; color: $primary; margin-bottom: 1; }
    #combo-edit-status { height: auto; margin: 1 0; }
    #combo-edit-fields Input, #combo-edit-fields Select { margin: 1 0; }
    #combo-models-table { height: 10; }
    """
    def __init__(self, client, rec, callback, **kw):
        super().__init__(**kw)
        self._client = client
        self._rec = rec
        self._cb = callback
        self._available_models: List[str] = []
        self._selected_models: set[str] = set(rec.get("models", []) if rec else [])
        self._strategy: str = "fallback"
        self._judge_model: str = ""
        self._filter_text: str = ""
        self._filter_used: str = "all"

    def compose(self):
        from textual.containers import Vertical, Horizontal
        from textual.widgets import Label, Static, Input, Button, Checkbox, DataTable, Select
        is_edit = self._rec is not None
        rec = self._rec or {}
        models_val = ", ".join(rec.get("models", [])) if rec.get("models") else ""
        with Vertical(id="combo-edit-container"):
            yield Label("Edit Combo" if is_edit else "Add Combo", id="combo-edit-title")
            with Vertical(id="combo-edit-fields"):
                yield Label("Name (a-z, 0-9, -, _, .)")
                yield Input(value=rec.get("name", ""), placeholder="e.g. my-combo", id="combo-name")
                yield Label("Kind (optional)")
                yield Input(value=rec.get("kind", "") or "", placeholder="kind (e.g. llm)", id="combo-kind")
                yield Label("Strategy")
                yield Select(
                    [("Fallback — try in order", "fallback"), ("Round Robin — rotate", "round-robin"), ("Fusion — panel + judge", "fusion")],
                    value=self._strategy,
                    id="combo-strategy",
                    allow_blank=False,
                )
                yield Label("Judge model (for Fusion, empty = Auto = first model)")
                yield Input(value=self._judge_model, placeholder="e.g. openai/gpt-4o  (only for Fusion)", id="combo-judge")
                yield Label("Filter models")
                with Horizontal():
                    yield Input(placeholder="Filter (e.g. gpt, claude)...", id="combo-filter")
                    yield Select(
                        [("All", "all"), ("Used", "used"), ("Unused", "unused")],
                        value="all",
                        id="combo-filter-used",
                        allow_blank=False,
                    )
                yield Label("Available models (Enter to toggle, ✓ = used in this combo)")
                yield DataTable(id="combo-models-table", cursor_type="row", zebra_stripes=True)
                yield Label("Selected models (comma-separated, also editable)")
                yield Input(value=models_val, placeholder="model1, model2, ...", id="combo-models")
            yield Static("", id="combo-edit-status")
            with Horizontal():
                yield Button("Save", id="btn-combo-save", variant="primary")
                yield Button("Cancel", id="btn-combo-cancel", variant="default")

    def on_mount(self) -> None:
        try:
            table = self.query_one("#combo-models-table", DataTable)
            table.add_columns("✓", "Model", "Status")
            self._refresh_models_table()
        except Exception:
            pass
        self._load_models_and_strategy()

    @work(exclusive=True)
    async def _load_models_and_strategy(self) -> None:
        # Load available models
        try:
            data = await asyncio.to_thread(self._client.list_models)
            models_data = data.get("models", []) if isinstance(data, dict) else data if isinstance(data, list) else []
            available: List[str] = []
            for m in models_data:
                mid = m.get("fullModel") or m.get("routedModel") or m.get("model") or m.get("id") or ""
                if mid:
                    available.append(mid)
            if not available:
                try:
                    v1 = await asyncio.to_thread(self._client.list_v1_models)
                    v1_data = v1.get("data", []) if isinstance(v1, dict) else []
                    for m in v1_data:
                        mid = m.get("id", "")
                        if mid:
                            available.append(mid)
                except Exception:
                    pass
            self._available_models = sorted(set(available))[:500]
        except Exception as e:
            self._available_models = []
            try:
                self.query_one("#combo-edit-status", Static).update(f"[yellow]Failed to load models: {e}[/]")
            except Exception:
                pass
        # Load strategy from settings
        try:
            settings = await asyncio.to_thread(self._client.get_settings)
            combo_strategies = settings.get("comboStrategies", {}) if isinstance(settings, dict) else {}
            rec_name = (self._rec or {}).get("name", "")
            if rec_name and rec_name in combo_strategies:
                strat = combo_strategies[rec_name] or {}
                self._strategy = strat.get("fallbackStrategy", "fallback") or "fallback"
                self._judge_model = strat.get("judgeModel", "") or ""
                try:
                    self.query_one("#combo-strategy", Select).value = self._strategy
                    self.query_one("#combo-judge", Input).value = self._judge_model
                    self.query_one("#combo-judge", Input).disabled = self._strategy != "fusion"
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self._refresh_models_table()
            used = len(self._selected_models)
            total = len(self._available_models)
            self.query_one("#combo-edit-status", Static).update(f"[dim]{used} used / {total} available[/]")
        except Exception:
            pass

    def _refresh_models_table(self, q: str | None = None, used_filter: str | None = None) -> None:
        try:
            table = self.query_one("#combo-models-table", DataTable)
            table.clear()
            if q is None:
                try:
                    q = self.query_one("#combo-filter", Input).value
                except Exception:
                    q = self._filter_text
            if used_filter is None:
                try:
                    used_filter = self.query_one("#combo-filter-used", Select).value or "all"
                except Exception:
                    used_filter = self._filter_used
            q = (q or "").lower().strip()
            used_filter = (used_filter or "all").lower()
            for mid in self._available_models:
                if q and q not in mid.lower():
                    continue
                is_used = mid in self._selected_models
                if used_filter == "used" and not is_used:
                    continue
                if used_filter == "unused" and is_used:
                    continue
                checked = "✓" if is_used else " "
                status = "used" if is_used else "unused"
                table.add_row(checked, mid, status)
            if table.row_count == 0:
                if not self._available_models:
                    table.add_row(" ", "[dim]No models loaded — check connection[/]", "")
                else:
                    table.add_row(" ", "[dim]No match[/]", "")
        except Exception:
            pass

    @on(Input.Changed, "#combo-filter")
    def on_filter(self, event: Input.Changed) -> None:
        self._filter_text = event.value
        self._refresh_models_table(q=event.value)

    @on(Select.Changed, "#combo-filter-used")
    def on_filter_used(self, event: Select.Changed) -> None:
        self._filter_used = str(event.value) if event.value else "all"
        self._refresh_models_table(used_filter=self._filter_used)

    @on(Select.Changed, "#combo-strategy")
    def on_strategy_changed(self, event: Select.Changed) -> None:
        self._strategy = str(event.value) if event.value else "fallback"
        try:
            judge_input = self.query_one("#combo-judge", Input)
            judge_input.disabled = self._strategy != "fusion"
            if self._strategy != "fusion":
                judge_input.placeholder = "only for Fusion"
            else:
                judge_input.placeholder = "e.g. openai/gpt-4o  (judge for Fusion)"
        except Exception:
            pass

    @on(DataTable.RowSelected, "#combo-models-table")
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            table = self.query_one("#combo-models-table", DataTable)
            row = table.get_row_at(event.cursor_row)
            mid = row[1]
            if mid.startswith("[dim]"):
                return
            if mid in self._selected_models:
                self._selected_models.remove(mid)
            else:
                self._selected_models.add(mid)
            self.query_one("#combo-models", Input).value = ", ".join(sorted(self._selected_models))
            self._refresh_models_table()
            used = len(self._selected_models)
            total = len(self._available_models)
            self.query_one("#combo-edit-status", Static).update(f"[dim]{used} used / {total} available[/]")
        except Exception:
            pass

    @on(Input.Changed, "#combo-models")
    def on_models_input_changed(self, event: Input.Changed) -> None:
        try:
            raw = event.value.strip()
            models = [m.strip() for m in raw.split(",") if m.strip()] if raw else []
            self._selected_models = set(models)
            self._refresh_models_table()
        except Exception:
            pass

    @on(Button.Pressed, "#btn-combo-save")
    def on_save(self) -> None:
        try:
            name = self.query_one("#combo-name", Input).value.strip()
            kind = self.query_one("#combo-kind", Input).value.strip() or None
            strategy = self.query_one("#combo-strategy", Select).value or "fallback"
            judge = self.query_one("#combo-judge", Input).value.strip()
            models_raw = self.query_one("#combo-models", Input).value.strip()
            models = [m.strip() for m in models_raw.split(",") if m.strip()] if models_raw else []
            if not models and self._selected_models:
                models = sorted(self._selected_models)
            if not name:
                self.query_one("#combo-edit-status", Static).update("[red]Name is required[/]")
                return
            import re
            if not re.match(r"^[a-zA-Z0-9_.\-]+$", name):
                self.query_one("#combo-edit-status", Static).update("[red]Name can only contain letters, numbers, -, _, .[/]")
                return
            payload = {"name": name, "models": models}
            if kind:
                payload["kind"] = kind
            import asyncio as _aio
            async def _do():
                try:
                    if self._rec:
                        await _aio.to_thread(self._client.update_combo, self._rec["id"], payload)
                    else:
                        await _aio.to_thread(self._client.create_combo, payload)
                    try:
                        settings = await _aio.to_thread(self._client.get_settings)
                        combo_strategies = dict(settings.get("comboStrategies", {}) or {})
                        old_name = (self._rec or {}).get("name", "")
                        if old_name and old_name != name and old_name in combo_strategies:
                            del combo_strategies[old_name]
                        if strategy == "fallback" and not judge:
                            if name in combo_strategies:
                                del combo_strategies[name]
                        else:
                            entry: Dict[str, Any] = {}
                            if strategy != "fallback":
                                entry["fallbackStrategy"] = strategy
                            if judge:
                                entry["judgeModel"] = judge
                            if name in combo_strategies:
                                entry = {**combo_strategies[name], **entry}
                                if strategy == "fallback" and "fallbackStrategy" in entry:
                                    del entry["fallbackStrategy"]
                                if not judge and "judgeModel" in entry:
                                    del entry["judgeModel"]
                            combo_strategies[name] = entry
                            if not entry:
                                del combo_strategies[name]
                        await _aio.to_thread(self._client.patch_settings, {"comboStrategies": combo_strategies})
                    except Exception as e:
                        self.app.notify(f"Combo saved but strategy not saved: {e}", severity="warning", timeout=3)
                    self.app.notify("Saved", timeout=2)
                    self.dismiss(True)
                    self._cb(True)
                except Exception as e:
                    self.query_one("#combo-edit-status", Static).update(f"[red]{e}[/]")
            _aio.create_task(_do())
        except Exception as e:
            try:
                self.query_one("#combo-edit-status", Static).update(f"[red]{e}[/]")
            except Exception:
                pass
    @on(Button.Pressed, "#btn-combo-cancel")
    def on_cancel(self) -> None:
        self.dismiss(False)
        self._cb(False)
