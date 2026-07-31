"""Live CLI Performance Dashboard.

Displays real-time pipeline performance metrics:
- Stage Latency Breakdown (Audio Capture, VAD, STT, Sentence Buffer, Translation, TTS, Lip Sync, Playback)
- Resource Utilization (CPU, RAM, GPU, Disk)
- Throughput Performance (RPS, Sentences/min, Audio min/min)
- End-to-End Latency Statistics (Avg, Median, P95, Max)
- Active Sessions & Lip-Sync FPS
"""

from __future__ import annotations

import os
import sys
import time
from typing import Optional

from voicebridge.metrics.collector import MetricsCollector
from voicebridge.metrics.model_tracker import ModelLoadTracker
from voicebridge.metrics.resource_monitor import ResourceMonitor

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, TextColumn
    from rich.table import Table
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class LiveDashboard:
    """CLI Dashboard for live VoiceBridge AI performance monitoring."""

    def __init__(
        self,
        collector: Optional[MetricsCollector] = None,
        resource_monitor: Optional[ResourceMonitor] = None,
        model_tracker: Optional[ModelLoadTracker] = None,
        refresh_rate_sec: float = 0.5,
    ):
        self.collector = collector or MetricsCollector.get_instance()
        self.resource_monitor = resource_monitor
        self.model_tracker = model_tracker or ModelLoadTracker.get_instance()
        self.refresh_rate_sec = refresh_rate_sec

    def render_console_text(self) -> str:
        """Fallback text renderer when rich is not available."""
        stages = self.collector.get_stage_averages()
        e2e = self.collector.get_e2e_latency_stats()
        tp = self.collector.get_throughput_stats()
        fps = self.collector.get_fps_stats()
        res = self.resource_monitor.get_summary() if self.resource_monitor else {}

        lines = [
            "============================================================",
            "                 VOICEBRIDGE AI LIVE DASHBOARD              ",
            "============================================================",
            f" Active Sessions: {self.collector.get_active_sessions_count()} | Sentences Processed: {tp.get('total_sentences', 0)}",
            "------------------------------------------------------------",
            " [STAGE LATENCIES (ms)]",
        ]
        for stage, lat in stages.items():
            lines.append(f"   {stage:<16}: {lat:>8.1f} ms")
        if not stages:
            lines.append("   (No utterances processed yet)")

        lines.extend([
            "------------------------------------------------------------",
            f" [E2E LATENCY]   Avg: {e2e.get('avg_ms', 0):>6.1f} ms | Median: {e2e.get('median_ms', 0):>6.1f} ms | P95: {e2e.get('p95_ms', 0):>6.1f} ms | Max: {e2e.get('max_ms', 0):>6.1f} ms",
            f" [THROUGHPUT]    RPS: {tp.get('requests_per_sec', 0):>6.2f} | Sentences/min: {tp.get('sentences_per_min', 0):>6.1f} | Audio-min/min: {tp.get('audio_min_per_min', 0):>6.2f}",
            f" [LIP-SYNC FPS]  Avg: {fps.get('avg_fps', 0):>6.1f} | Min: {fps.get('min_fps', 0):>6.1f} | Max: {fps.get('max_fps', 0):>6.1f}",
        ])

        if res:
            cpu = res.get("cpu", {})
            mem = res.get("memory", {})
            gpu = res.get("gpu", {})
            lines.extend([
                "------------------------------------------------------------",
                " [RESOURCE UTILIZATION]",
                f"   CPU Usage: {cpu.get('current_percent', 0):>5.1f}% (Avg: {cpu.get('avg_percent', 0):>5.1f}%, Peak: {cpu.get('peak_percent', 0):>5.1f}%)",
                f"   RAM Usage: {mem.get('current_ram_mb', 0):>7.1f} MB (Peak: {mem.get('peak_ram_mb', 0):>7.1f} MB, Growth: {mem.get('ram_growth_mb', 0):>6.1f} MB)",
                f"   VRAM Used: {gpu.get('vram_used_mb', 0):>7.1f} MB",
            ])
        lines.append("============================================================")
        return "\n".join(lines)

    def build_rich_layout(self) -> Layout:
        """Builds a rich terminal layout with tables and panels."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1),
        )

        # Header panel
        active_sessions = self.collector.get_active_sessions_count()
        header_text = Text(
            f" VoiceBridge AI Performance Monitor | Active Sessions: {active_sessions}",
            style="bold white on blue",
        )
        layout["header"].update(Panel(header_text, style="blue"))

        # Left panel: Stage Latency Breakdown
        stages = self.collector.get_stage_averages()
        stage_table = Table(title="Stage Latency Breakdown (ms)", expand=True)
        stage_table.add_column("Pipeline Stage", style="cyan", no_wrap=True)
        stage_table.add_column("Avg Latency (ms)", style="bold yellow", justify="right")

        total_stage_ms = sum(stages.values()) if stages else 0.0
        for stage, lat in stages.items():
            pct = (lat / total_stage_ms * 100.0) if total_stage_ms > 0 else 0.0
            stage_table.add_row(stage, f"{lat:.1f} ms ({pct:.1f}%)")

        if not stages:
            stage_table.add_row("Waiting for data...", "-")

        e2e = self.collector.get_e2e_latency_stats()
        stage_table.add_section()
        stage_table.add_row("[bold]Total Pipeline E2E Avg[/bold]", f"[bold green]{e2e.get('avg_ms', 0):.1f} ms[/bold green]")
        layout["left"].update(Panel(stage_table, title="Latency Metrics", border_style="cyan"))

        # Right panel: System Resources & Throughput
        tp = self.collector.get_throughput_stats()
        fps = self.collector.get_fps_stats()
        res = self.resource_monitor.get_summary() if self.resource_monitor else {}

        right_table = Table(title="System Resources & Throughput", expand=True)
        right_table.add_column("Metric", style="magenta")
        right_table.add_column("Value", style="bold white", justify="right")

        if res:
            cpu = res.get("cpu", {})
            mem = res.get("memory", {})
            gpu = res.get("gpu", {})
            disk = res.get("disk", {})
            right_table.add_row("CPU Current / Peak", f"{cpu.get('current_percent', 0)}% / {cpu.get('peak_percent', 0)}%")
            right_table.add_row("RAM Current / Peak", f"{mem.get('current_ram_mb', 0):.1f} MB / {mem.get('peak_ram_mb', 0):.1f} MB")
            right_table.add_row("VRAM Used", f"{gpu.get('vram_used_mb', 0):.1f} MB")
            right_table.add_row("Temp / Speech Storage", f"{disk.get('temp_dir_size_mb', 0):.2f} MB / {disk.get('output_dir_size_mb', 0):.2f} MB")
            right_table.add_section()

        right_table.add_row("Requests / sec", f"{tp.get('requests_per_sec', 0):.2f}")
        right_table.add_row("Sentences / min", f"{tp.get('sentences_per_min', 0):.1f}")
        right_table.add_row("Audio-minutes / min", f"{tp.get('audio_min_per_min', 0):.2f}")
        right_table.add_row("Lip-sync Avg FPS", f"{fps.get('avg_fps', 0):.1f} FPS")

        layout["right"].update(Panel(right_table, title="Hardware & Throughput", border_style="magenta"))

        # Footer panel
        footer_text = Text(
            f"E2E Median: {e2e.get('median_ms', 0):.1f}ms | E2E P95: {e2e.get('p95_ms', 0):.1f}ms | E2E Max: {e2e.get('max_ms', 0):.1f}ms",
            style="dim green",
        )
        layout["footer"].update(Panel(footer_text, border_style="green"))

        return layout

    def start_live(self, duration_sec: Optional[float] = None) -> None:
        """Starts live dashboard rendering loop."""
        start = time.time()
        if HAS_RICH:
            console = Console()
            with Live(self.build_rich_layout(), console=console, refresh_per_second=int(1.0 / self.refresh_rate_sec)) as live:
                while True:
                    live.update(self.build_rich_layout())
                    time.sleep(self.refresh_rate_sec)
                    if duration_sec and (time.time() - start) >= duration_sec:
                        break
        else:
            while True:
                os.system("cls" if os.name == "nt" else "clear")
                print(self.render_console_text())
                time.sleep(self.refresh_rate_sec)
                if duration_sec and (time.time() - start) >= duration_sec:
                    break
