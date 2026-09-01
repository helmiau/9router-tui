from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Label, Static, Select

from client import NinerouterClient
from tui.helpers import _store_plain, fmt_time, mask_key

class UsagePane(Static):
    def __init__(self, client: NinerouterClient, **kw):
        super().__init__(**kw)
        self.client = client

    def compose(self) -> ComposeResult:
        yield Label("Usage — Stats & History", id="usage-title")
        yield Horizontal(
            Button("Refresh", id="btn-usage-refresh", variant="primary"),
            Select([("7d", "7d"), ("24h", "24h"), ("30d", "30d"), ("today", "today"), ("all", "all")], value="7d", id="select-usage-period"),
        )
        yield Static("", id="usage-summary")
        yield Static("", id="usage-chart")
        yield Static("", id="usage-body")
        yield DataTable(id="table-usage-history", cursor_type="row", zebra_stripes=True)
        yield Static("", id="usage-detail")
        yield Horizontal(Button("Copy Detail", id="btn-usage-copy", variant="default"))

    def on_mount(self) -> None:
        table = self.query_one("#table-usage-history", DataTable)
        table.add_columns("Time", "Model", "Provider", "Tokens", "Cost")
        self.refresh_data()

    def _fmt_tokens(self, n: int) -> str:
        if n >= 1_000_000:
            return f"{n/1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n/1_000:.1f}K"
        return str(n)

    def _fmt_cost(self, c: float) -> str:
        if c == 0:
            return "$0"
        if c < 0.01:
            return f"${c:.4f}"
        return f"${c:.2f}"

    def _bar(self, val: float, max_val: float, width: int = 20) -> str:
        if max_val <= 0:
            return "░" * width
        filled = int(val / max_val * width)
        return "█" * filled + "░" * (width - filled)

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        period = "7d"
        try:
            sel = self.query_one("#select-usage-period", Select)
            period = sel.value or "7d"
        except Exception:
            pass
        summary = self.query_one("#usage-summary", Static)
        chart_w = self.query_one("#usage-chart", Static)
        body = self.query_one("#usage-body", Static)
        table = self.query_one("#table-usage-history", DataTable)
        table.clear()
        summary.update("Loading...")
        chart_w.update("")
        body.update("")
        try:
            stats = await asyncio.to_thread(self.client.get_usage_stats, period)
            total_req = stats.get("totalRequests", 0)
            total_prompt = stats.get("totalPromptTokens", 0)
            total_comp = stats.get("totalCompletionTokens", 0)
            total_cached = stats.get("totalCachedTokens", 0)
            total_cost = stats.get("totalCost", 0)
            total_tokens = total_prompt + total_comp

            # Summary line like web dashboard
            lines = []
            lines.append(f"[bold]Period: {period}[/]  [cyan]{total_req:,}[/] req  [green]{self._fmt_tokens(total_tokens)}[/] tokens  [yellow]{self._fmt_cost(total_cost)}[/]  [dim]prompt {self._fmt_tokens(total_prompt)} / completion {self._fmt_tokens(total_comp)} / cached {self._fmt_tokens(total_cached)}[/]")
            summary.update("  ".join(lines))

            # Chart — horizontal bar per day (from /api/usage/chart)
            try:
                chart_data = await asyncio.to_thread(self.client.get_usage_chart, period if period != "all" else "30d")
                if isinstance(chart_data, list) and chart_data:
                    max_tokens = max((c.get("tokens", 0) for c in chart_data), default=1)
                    max_cost = max((c.get("cost", 0) for c in chart_data), default=1)
                    chart_lines = []
                    for c in chart_data:
                        label = c.get("label", "")[:6]
                        tokens = c.get("tokens", 0)
                        cost = c.get("cost", 0)
                        bar = self._bar(tokens, max_tokens, 16)
                        chart_lines.append(f"[dim]{label:>6}[/] {bar} {self._fmt_tokens(tokens):>7}  {self._fmt_cost(cost):>8}")
                    chart_w.update("\n".join(chart_lines))
                else:
                    chart_w.update("[dim]No chart data[/]")
            except Exception:
                chart_w.update("")

            # Breakdown by provider (top 5)
            by_provider = stats.get("byProvider", {})
            if by_provider:
                sorted_providers = sorted(by_provider.items(), key=lambda x: x[1].get("requests", 0), reverse=True)[:5]
                max_req = max((v.get("requests", 0) for _, v in sorted_providers), default=1)
                provider_lines = ["[bold]By Provider:[/]"]
                for name, vals in sorted_providers:
                    req = vals.get("requests", 0)
                    cost = vals.get("cost", 0)
                    bar = self._bar(req, max_req, 12)
                    provider_lines.append(f"  {bar} [cyan]{name[:18]:<18}[/] {req:>4} req  {self._fmt_cost(cost):>8}")
                body.update("\n".join(provider_lines))
                _store_plain(body, "\n".join(provider_lines))
            else:
                body.update("[dim]No provider breakdown[/]")
                _store_plain(body, "")

            # Also store full stats for copy
            full_txt = json.dumps(stats, indent=2, ensure_ascii=False)[:4000]
            _store_plain(body, full_txt)

        except Exception as e:
            summary.update(f"[red]Stats error: {e}[/]")
            chart_w.update("")
            body.update(f"[red]{e}[/]")
            _store_plain(body, str(e))
        try:
            hist = await asyncio.to_thread(self.client.get_usage_history, 50)
            items = hist.get("history", hist.get("items", hist.get("data", []))) if isinstance(hist, dict) else hist
            if isinstance(items, list):
                for h in items[:50]:
                    table.add_row(
                        fmt_time(h.get("createdAt", h.get("timestamp", h.get("time", "")))),
                        h.get("model", "—")[:24],
                        h.get("provider", "—")[:16],
                        str(h.get("totalTokens", h.get("tokens", h.get("promptTokens", 0) + h.get("completionTokens", 0) if h.get("promptTokens") else "—"))),
                        str(h.get("cost", "—")),
                    )
                self.query_one("#usage-detail", Static).update(f"[dim]{len(items)} records[/]")
        except Exception as e:
            self.query_one("#usage-detail", Static).update(f"[red]History error: {e}[/]")

    @on(Button.Pressed, "#btn-usage-refresh")
    def on_refresh(self) -> None:
        self.refresh_data()

    @on(Button.Pressed, "#btn-usage-copy")
    def on_copy(self) -> None:
        try:
            w = self.query_one("#usage-detail", Static)
            plain = getattr(w, "_plain_text", "") or ""
            if plain:
                self.app._copy_text(plain)  # type: ignore[attr-defined]
            else:
                self.app.notify("Nothing to copy", severity="warning")  # type: ignore[attr-defined]
        except Exception:
            pass

    @on(Select.Changed, "#select-usage-period")
    def on_period_changed(self, event: Select.Changed) -> None:
        self.refresh_data()
