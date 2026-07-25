"""
Módulo Coletor de Métricas de Streaming.

Este módulo é responsável por registrar e exportar os dados estatísticos de cada
segmento baixado durante a simulação de streaming para um arquivo no formato CSV.
"""

from __future__ import annotations
import csv
import os
from datetime import datetime


class MetricsCollector:
    """
    Coleta e armazena estatísticas detalhadas do streaming de vídeo em formato CSV.

    Attributes:
        output_path (str): Caminho do arquivo CSV de saída.
        FIELDS (list[str]): Lista de campos/colunas gravados no CSV.
    """

    FIELDS = [
        "segment",
        "timestamp",
        "server_id",
        "quality",
        "bitrate_kbps",
        "vazão_kbps",
        "download_time_s",
        "jitter_network_ms",   # Jitter bruto de rede do segmento (ms)
        "jitter_ewma_ms",      # EWMA do jitter (estimativa suavizada)
        "buffer_level_s",
        "buffer_can_play",
        "rebuffer_event",
        "stall_duration_s",
        "failover_total",
    ]

    def __init__(self, output_path: str) -> None:
        """
        Inicializa o coletor de métricas e cria o arquivo CSV com o cabeçalho.

        Args:
            output_path (str): Caminho completo onde o CSV será salvo.
        """
        self.output_path = output_path
        self._initialize_csv()

    def _initialize_csv(self) -> None:
        """Cria o diretório pai (se não existir) e escreve o cabeçalho das colunas no CSV."""
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        with open(self.output_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDS)
            writer.writeheader()

    def log_metric(self, data: dict) -> None:
        """
        Registra uma nova amostra/segmento baixado no arquivo CSV.

        Args:
            data (dict): Dicionário contendo os valores das métricas do segmento atual.
        """
        row = {field: data.get(field, 0) for field in self.FIELDS}
        row["timestamp"] = datetime.now().isoformat()
        with open(self.output_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDS)
            writer.writerow(row)

