"""
Nboost - core/system_monitor.py
Background poller for CPU / RAM / Disk usage, feeding the live gauges.
Runs on a QThread so the UI never blocks on psutil's sampling interval.
"""

from __future__ import annotations
import psutil
from PyQt6.QtCore import QThread, pyqtSignal


class SystemMonitor(QThread):
    stats_ready = pyqtSignal(dict)  # {"cpu": float, "ram": float, "ram_used_gb": float,
                                     #  "ram_total_gb": float, "disk": float,
                                     #  "disk_free_gb": float, "disk_total_gb": float}

    def __init__(self, interval_ms: int = 1000, disk_path: str = "C:\\", parent=None):
        super().__init__(parent)
        self._interval_s = max(0.25, interval_ms / 1000.0)
        self._disk_path = disk_path
        self._running = False

    def run(self):
        self._running = True
        # First call to cpu_percent with no interval just primes the internal counter.
        psutil.cpu_percent(interval=None)
        while self._running:
            cpu = psutil.cpu_percent(interval=self._interval_s)
            vm = psutil.virtual_memory()
            du = psutil.disk_usage(self._disk_path)
            self.stats_ready.emit({
                "cpu": cpu,
                "ram": vm.percent,
                "ram_used_gb": vm.used / (1024 ** 3),
                "ram_total_gb": vm.total / (1024 ** 3),
                "disk": du.percent,
                "disk_free_gb": du.free / (1024 ** 3),
                "disk_total_gb": du.total / (1024 ** 3),
            })

    def stop(self):
        self._running = False
        self.wait(2000)
