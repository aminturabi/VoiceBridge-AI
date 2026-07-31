"""Performance Report Generator.

Analyzes pipeline benchmarking metrics, hardware resource utilization, and model load
startup statistics to produce comprehensive performance reports.

Features:
- Automated Bottleneck Analysis (identifies slowest pipeline stages)
- Actionable Optimization Recommendations
- Exports in three formats: Markdown (.md), JSON (.json), and CSV (.csv)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from voicebridge.logging_conf import get_logger
from voicebridge.metrics.collector import MetricsCollector
from voicebridge.metrics.model_tracker import ModelLoadTracker
from voicebridge.metrics.resource_monitor import ResourceMonitor

logger = get_logger(__name__)


class PerformanceReporter:
    """Generates structured benchmark and performance reports."""

    def __init__(
        self,
        collector: Optional[MetricsCollector] = None,
        resource_monitor: Optional[ResourceMonitor] = None,
        model_tracker: Optional[ModelLoadTracker] = None,
    ):
        self.collector = collector or MetricsCollector.get_instance()
        self.resource_monitor = resource_monitor
        self.model_tracker = model_tracker or ModelLoadTracker.get_instance()

    def analyze_bottlenecks(self) -> Dict[str, Any]:
        """Identifies pipeline bottleneck stages and generates recommendations."""
        stages = self.collector.get_stage_averages()
        if not stages:
            return {
                "slowest_stage": "N/A",
                "slowest_stage_ms": 0.0,
                "percentage_of_total": 0.0,
                "recommendations": ["No benchmark data collected."],
            }

        sorted_stages = sorted(stages.items(), key=lambda x: x[1], reverse=True)
        slowest_stage, slowest_ms = sorted_stages[0]
        total_ms = sum(stages.values())
        pct = (slowest_ms / total_ms * 100.0) if total_ms > 0 else 0.0

        recommendations: List[str] = []

        if slowest_stage in ("Lip Sync Generation", "lipsync"):
            recommendations.append(
                "Lip sync is the primary bottleneck. Consider using GPU acceleration for Wav2Lip or switching lipsync.backend to 'demo' or 'null' for minimal latency during live calls."
            )
        elif slowest_stage in ("Speech-to-Text", "stt"):
            recommendations.append(
                "STT is the primary bottleneck. Consider lowering stt.cpu.model_size (e.g. from 'tiny'/'base' to 'tiny') or enabling CUDA GPU acceleration."
            )
        elif slowest_stage in ("Translation", "translation"):
            recommendations.append(
                "Translation latency is high. Ensure stable internet connection for Google translate or pre-load Argos offline packages to eliminate network round-trips."
            )
        elif slowest_stage in ("Text-to-Speech", "tts"):
            recommendations.append(
                "TTS latency is high. Optimize network bandwidth for edge-tts synthesis."
            )

        if total_ms > 2000.0:
            recommendations.append(
                "Total end-to-end latency exceeds 2.0s. Run VoiceBridge with GPU hardware or enable concurrent chunk processing."
            )

        return {
            "slowest_stage": slowest_stage,
            "slowest_stage_ms": round(slowest_ms, 2),
            "percentage_of_total": round(pct, 1),
            "stage_rankings": [
                {"stage": s, "avg_ms": lat, "pct": round(lat / total_ms * 100.0, 1) if total_ms > 0 else 0.0}
                for s, lat in sorted_stages
            ],
            "recommendations": recommendations,
        }

    def generate_report_dict(self) -> Dict[str, Any]:

        stages = self.collector.get_stage_averages()
        e2e = self.collector.get_e2e_latency_stats()
        tp = self.collector.get_throughput_stats()
        fps = self.collector.get_fps_stats()
        res = self.resource_monitor.get_summary() if self.resource_monitor else {}
        model_summary = self.model_tracker.get_summary()
        bottlenecks = self.analyze_bottlenecks()

        return {
            "latency_summary": {
                "e2e_stats_ms": e2e,
                "stage_latencies_ms": stages,
            },
            "throughput_summary": tp,
            "fps_summary": fps,
            "resource_summary": res,
            "model_load_summary": model_summary,
            "bottleneck_analysis": bottlenecks,
        }

    def export_markdown(self, output_path: Path) -> Path:
        """Exports performance report in Markdown format."""
        data = self.generate_report_dict()
        e2e = data["latency_summary"]["e2e_stats_ms"]
        stages = data["latency_summary"]["stage_latencies_ms"]
        tp = data["throughput_summary"]
        fps = data["fps_summary"]
        res = data.get("resource_summary", {})
        bottlenecks = data["bottleneck_analysis"]

        lines = [
            "# VoiceBridge AI Performance & Benchmark Report",
            "",
            "## Executive Latency Summary",
            "",
            "| Latency Metric | Execution Time (ms) |",
            "| :--- | :--- |",
            f"| **Average E2E Latency** | {e2e.get('avg_ms', 0):.2f} ms |",
            f"| **Minimum Latency** | {e2e.get('min_ms', 0):.2f} ms |",
            f"| **Maximum Latency** | {e2e.get('max_ms', 0):.2f} ms |",
            f"| **Median Latency** | {e2e.get('median_ms', 0):.2f} ms |",
            f"| **95th Percentile (P95)** | {e2e.get('p95_ms', 0):.2f} ms |",
            f"| **Standard Deviation** | {e2e.get('std_dev_ms', 0):.2f} ms |",
            "",
            "## Pipeline Stage Breakdown",
            "",
            "| Pipeline Stage | Average Latency (ms) | Percentage |",
            "| :--- | :--- | :--- |",
        ]

        total_stage = sum(stages.values()) if stages else 1.0
        for stage, lat in stages.items():
            pct = (lat / total_stage * 100.0)
            lines.append(f"| {stage} | {lat:.2f} ms | {pct:.1f}% |")

        lines.extend([
            "",
            "## Throughput & Lip-Sync Metrics",
            "",
            f"- **Requests per Second (RPS)**: {tp.get('requests_per_sec', 0):.3f}",
            f"- **Sentences Processed / Minute**: {tp.get('sentences_per_min', 0):.2f}",
            f"- **Audio Minutes Processed / Minute**: {tp.get('audio_min_per_min', 0):.2f}",
            f"- **Average Lip-Sync FPS**: {fps.get('avg_fps', 0):.2f} FPS (Min: {fps.get('min_fps', 0):.1f}, Max: {fps.get('max_fps', 0):.1f})",
            "",
            "## Hardware Resource Utilization",
            "",
        ])

        if res:
            cpu = res.get("cpu", {})
            mem = res.get("memory", {})
            gpu = res.get("gpu", {})
            disk = res.get("disk", {})
            lines.extend([
                f"- **CPU Usage**: Current {cpu.get('current_percent', 0)}% | Avg {cpu.get('avg_percent', 0)}% | Peak {cpu.get('peak_percent', 0)}%",
                f"- **RAM Usage**: Current {mem.get('current_ram_mb', 0):.1f} MB | Peak {mem.get('peak_ram_mb', 0):.1f} MB | Growth {mem.get('ram_growth_mb', 0):.1f} MB",
                f"- **VRAM Usage**: {gpu.get('vram_used_mb', 0):.1f} MB",
                f"- **Disk Storage**: Temp {disk.get('temp_dir_size_mb', 0):.2f} MB | Generated Speech {disk.get('output_dir_size_mb', 0):.2f} MB",
                "",
            ])

        lines.extend([
            "## Bottleneck Analysis & Optimization Recommendations",
            "",
            f"> **Primary Bottleneck**: `{bottlenecks.get('slowest_stage', 'N/A')}` ({bottlenecks.get('slowest_stage_ms', 0)} ms, {bottlenecks.get('percentage_of_total', 0)}% of total pipeline latency)",
            "",
            "### Recommendations:",
        ])
        for rec in bottlenecks.get("recommendations", []):
            lines.append(f"- {rec}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Exported Markdown report -> %s", output_path)
        return output_path

    def export_json(self, output_path: Path) -> Path:
        """Exports performance report in JSON format."""
        data = self.generate_report_dict()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Exported JSON report -> %s", output_path)
        return output_path

    def export_csv(self, output_path: Path) -> Path:
        """Exports per-utterance timing data in CSV format."""
        records = self.collector.get_records()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "session_id", "direction", "sentence_id", "source_lang", "target_lang",
                "audio_capture_ms", "vad_ms", "stt_ms", "buffer_ms", "translation_ms",
                "tts_ms", "lipsync_ms", "playback_ms", "total_latency_ms", "fps", "is_synced"
            ])
            for r in records:
                st = r.stage_latencies_ms
                writer.writerow([
                    r.session_id, r.direction, r.sentence_id, r.source_lang, r.target_lang,
                    st.get("Audio Capture", 0.0), st.get("VAD", 0.0), st.get("STT", 0.0),
                    st.get("Sentence Buffer", 0.0), st.get("Translation", 0.0),
                    st.get("TTS", 0.0), st.get("Lip Sync", 0.0), st.get("Playback", 0.0),
                    r.total_latency_ms, r.fps, r.is_synced,
                ])
        logger.info("Exported CSV report -> %s", output_path)
        return output_path
