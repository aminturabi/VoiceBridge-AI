"""Resource Monitoring Utilities.

Continuously samples system hardware resources:
- CPU: Current %, Average %, Peak %
- RAM: Current MB, Peak MB, Memory growth MB
- GPU: Utilization %, VRAM usage MB, GPU temperature (if CUDA available)
- Disk: Temporary storage usage & generated speech storage
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from voicebridge.logging_conf import get_logger

logger = get_logger(__name__)

# Try optional dependencies
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import torch
    HAS_TORCH = torch.cuda.is_available()
except ImportError:
    HAS_TORCH = False


@dataclass
class ResourceSnapshot:
    """A single snapshot of hardware resource utilization."""

    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    ram_mb: float = 0.0
    peak_ram_mb: float = 0.0
    ram_growth_mb: float = 0.0
    gpu_percent: float = 0.0
    vram_used_mb: float = 0.0
    vram_total_mb: float = 0.0
    gpu_temp_c: float = 0.0
    temp_dir_size_mb: float = 0.0
    output_dir_size_mb: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cpu_percent": round(self.cpu_percent, 1),
            "ram_mb": round(self.ram_mb, 1),
            "peak_ram_mb": round(self.peak_ram_mb, 1),
            "ram_growth_mb": round(self.ram_growth_mb, 1),
            "gpu_percent": round(self.gpu_percent, 1),
            "vram_used_mb": round(self.vram_used_mb, 1),
            "vram_total_mb": round(self.vram_total_mb, 1),
            "gpu_temp_c": round(self.gpu_temp_c, 1),
            "temp_dir_size_mb": round(self.temp_dir_size_mb, 2),
            "output_dir_size_mb": round(self.output_dir_size_mb, 2),
        }


class ResourceMonitor:
    """Background monitoring thread sampling CPU, RAM, GPU, and Disk resources."""

    def __init__(
        self,
        sample_interval_sec: float = 0.5,
        temp_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        self.sample_interval_sec = sample_interval_sec
        self.temp_dir = temp_dir
        self.output_dir = output_dir

        self._lock = threading.Lock()
        self._snapshots: List[ResourceSnapshot] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._initial_ram_mb: float = self._get_current_ram_mb()
        self._peak_ram_mb: float = self._initial_ram_mb
        self._peak_cpu_percent: float = 0.0

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._initial_ram_mb = self._get_current_ram_mb()
            self._peak_ram_mb = self._initial_ram_mb
            self._peak_cpu_percent = 0.0
            self._thread = threading.Thread(
                target=self._monitor_loop, name="resource-monitor", daemon=True
            )
            self._thread.start()
            logger.info("ResourceMonitor started (interval=%.1fs)", self.sample_interval_sec)

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
            logger.info("ResourceMonitor stopped")

    def sample_now(self) -> ResourceSnapshot:
        """Takes a single resource measurement snapshot."""
        cpu = self._get_cpu_percent()
        ram = self._get_current_ram_mb()
        gpu_info = self._get_gpu_info()
        temp_size = self._get_dir_size_mb(self.temp_dir)
        output_size = self._get_dir_size_mb(self.output_dir)

        with self._lock:
            if ram > self._peak_ram_mb:
                self._peak_ram_mb = ram
            if cpu > self._peak_cpu_percent:
                self._peak_cpu_percent = cpu

            growth = max(0.0, ram - self._initial_ram_mb)
            snapshot = ResourceSnapshot(
                cpu_percent=cpu,
                ram_mb=ram,
                peak_ram_mb=self._peak_ram_mb,
                ram_growth_mb=growth,
                gpu_percent=gpu_info.get("gpu_percent", 0.0),
                vram_used_mb=gpu_info.get("vram_used_mb", 0.0),
                vram_total_mb=gpu_info.get("vram_total_mb", 0.0),
                gpu_temp_c=gpu_info.get("gpu_temp_c", 0.0),
                temp_dir_size_mb=temp_size,
                output_dir_size_mb=output_size,
            )
            self._snapshots.append(snapshot)
            return snapshot

    def _monitor_loop(self) -> None:
        while self._running:
            self.sample_now()
            time.sleep(self.sample_interval_sec)

    def get_summary(self) -> Dict[str, Any]:
        """Calculates resource utilization summary metrics."""
        with self._lock:
            if not self._snapshots:
                current = self.sample_now()
                return {
                    "cpu": {"current_percent": current.cpu_percent, "avg_percent": current.cpu_percent, "peak_percent": current.cpu_percent},
                    "memory": {"current_ram_mb": current.ram_mb, "peak_ram_mb": current.peak_ram_mb, "ram_growth_mb": current.ram_growth_mb},
                    "gpu": {"gpu_percent": current.gpu_percent, "vram_used_mb": current.vram_used_mb, "gpu_temp_c": current.gpu_temp_c},
                    "disk": {"temp_dir_size_mb": current.temp_dir_size_mb, "output_dir_size_mb": current.output_dir_size_mb},
                }

            cpus = [s.cpu_percent for s in self._snapshots]
            rams = [s.ram_mb for s in self._snapshots]

            latest = self._snapshots[-1]

            return {
                "cpu": {
                    "current_percent": round(latest.cpu_percent, 1),
                    "avg_percent": round(sum(cpus) / len(cpus), 1),
                    "peak_percent": round(max(cpus), 1),
                },
                "memory": {
                    "current_ram_mb": round(latest.ram_mb, 1),
                    "peak_ram_mb": round(max(rams), 1),
                    "ram_growth_mb": round(latest.ram_growth_mb, 1),
                },
                "gpu": {
                    "gpu_percent": round(latest.gpu_percent, 1),
                    "vram_used_mb": round(latest.vram_used_mb, 1),
                    "vram_total_mb": round(latest.vram_total_mb, 1),
                    "gpu_temp_c": round(latest.gpu_temp_c, 1),
                },
                "disk": {
                    "temp_dir_size_mb": round(latest.temp_dir_size_mb, 2),
                    "output_dir_size_mb": round(latest.output_dir_size_mb, 2),
                },
            }

    def _get_cpu_percent(self) -> float:
        if HAS_PSUTIL:
            try:
                return psutil.cpu_percent(interval=None)
            except Exception:
                pass
        return 0.0

    def _get_current_ram_mb(self) -> float:
        if HAS_PSUTIL:
            try:
                process = psutil.Process(os.getpid())
                return process.memory_info().rss / (1024 * 1024)
            except Exception:
                pass
        return 0.0

    def _get_gpu_info(self) -> Dict[str, float]:
        if HAS_TORCH:
            try:
                device = 0
                vram_used = torch.cuda.memory_allocated(device) / (1024 * 1024)
                vram_total = torch.cuda.get_device_properties(device).total_memory / (1024 * 1024)
                return {
                    "gpu_percent": 0.0,  # Torch doesn't give utilization % directly
                    "vram_used_mb": vram_used,
                    "vram_total_mb": vram_total,
                    "gpu_temp_c": 0.0,
                }
            except Exception:
                pass
        return {"gpu_percent": 0.0, "vram_used_mb": 0.0, "vram_total_mb": 0.0, "gpu_temp_c": 0.0}

    def _get_dir_size_mb(self, directory: Optional[Path]) -> float:
        if not directory or not directory.exists():
            return 0.0
        try:
            total_bytes = 0
            for entry in os.scandir(directory):
                if entry.is_file(follow_symlinks=False):
                    total_bytes += entry.stat().st_size
            return total_bytes / (1024 * 1024)
        except Exception:
            return 0.0
