"""
metrics_collector.py — Registra todas as métricas de streaming em CSV.
"""

from __future__ import annotations
import csv
import os
from datetime import datetime


class MetricsCollector:
    """Coleta e salva métricas de streaming em arquivo CSV."""

    FIELDS = [
        "segment",
        "timestamp",
        "server_id",
        "quality",
        "bitrate_kbps",
        "vazão_kbps",
        "download_time_s",
        "jitter_network_ms",   # delay bruto do segmento (ms)
        "jitter_ewma_ms",      # EWMA do jitter — preenchido pela Política 3
        "buffer_level_s",
        "buffer_can_play",
        "rebuffer_event",
        "stall_duration_s",
        "failover_total",
    ]

    def __init__(self, output_path: str) -> None:
        self.output_path = output_path
        self._initialize_csv()

    def _initialize_csv(self) -> None:
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        with open(self.output_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDS)
            writer.writeheader()

    def log_metric(self, data: dict) -> None:
        """Acrescenta uma linha de dados ao CSV."""
        row = {field: data.get(field, 0) for field in self.FIELDS}
        row["timestamp"] = datetime.now().isoformat()
        with open(self.output_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDS)
            writer.writerow(row)
