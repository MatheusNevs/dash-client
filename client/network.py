"""
network.py — Camada de rede: HTTP, medição de vazão/jitter e failover automático.
"""

from __future__ import annotations
import time
import json
import requests


class NetworkManager:
    """
    Gerencia requisições HTTP, métricas de rede e failover entre servidores.

    Atributos públicos relevantes para o MetricsCollector:
      current_server_id  — id/nome do servidor ativo
      failover_count     — total de failovers ocorridos
    """

    def __init__(self, manifest_url: str) -> None:
        self.manifest_url    = manifest_url
        self.session         = requests.Session()
        self.all_servers: list[dict] = []
        self.current_server: dict | None = None
        self.manifest: dict | None = None
        self.failover_count: int = 0

    # ── Manifesto ─────────────────────────────────────────────

    def fetch_manifest(self) -> dict | None:
        """Baixa e analisa o manifesto JSON do servidor."""
        try:
            response = self.session.get(self.manifest_url, timeout=5)
            response.raise_for_status()
            self.manifest    = response.json()
            self.all_servers = sorted(
                self.manifest.get("servers", []),
                key=lambda x: x.get("priority", 99),
            )
            if self.all_servers:
                self.current_server = self.all_servers[0]
            return self.manifest
        except Exception as e:
            print(f"[Network] Erro ao buscar manifesto: {e}")
            return None

    # ── Propriedades de conveniência ──────────────────────────

    @property
    def current_server_url(self) -> str:
        return self.current_server.get("url", "") if self.current_server else ""

    @property
    def current_server_id(self) -> str:
        return self.current_server.get("id", "unknown") if self.current_server else "unknown"

    # ── Health check ─────────────────────────────────────────

    def check_health(self, server_url: str) -> bool:
        """Verifica se o servidor está saudável via GET /health."""
        try:
            response = self.session.get(f"{server_url}/health", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    # ── Failover ─────────────────────────────────────────────

    def try_failover(self) -> bool:
        """
        Tenta trocar para o próximo servidor disponível na lista de prioridade.
        Retorna True se o failover foi bem-sucedido.
        """
        current_id = self.current_server_id
        print(f"[Network] Failover acionado! Saindo de '{current_id}'...")

        for server in self.all_servers:
            if server.get("id") == current_id:
                continue  # pula o servidor que falhou
            if self.check_health(server.get("url", "")):
                self.current_server = server
                self.failover_count += 1
                print(f"[Network] Failover OK → '{self.current_server_id}'")
                return True

        print("[Network] Failover FALHOU — nenhum servidor disponível.")
        return False

    # ── Download de segmento ──────────────────────────────────

    def download_segment(
        self,
        quality_path: str,
    ) -> tuple[bytes | None, float, float, float]:
        """
        Baixa um segmento de vídeo e mede throughput e download_time.

        Retorna:
          (content, download_time_s, throughput_kbps, download_time_ms)
          Em caso de falha retorna (None, 0, 0, 0).

        Nota: download_time_ms é retornado para que o main.py passe ao
        HeuristicPolicy.update_network_sample() e calcule o jitter corretamente.
        """
        if not self.current_server:
            return None, 0.0, 0.0, 0.0

        url = f"{self.current_server_url}{quality_path}"
        try:
            start_time = time.perf_counter()
            response   = self.session.get(url, timeout=5)
            end_time   = time.perf_counter()
            response.raise_for_status()

            content       = response.content
            download_time = end_time - start_time                    # segundos
            throughput    = (len(content) * 8 / 1000) / download_time if download_time > 0 else 0.0

            return content, download_time, throughput, download_time * 1000.0  # ms
        except Exception as e:
            print(f"[Network] Falha no download: {e}")
            if self.try_failover():
                return self.download_segment(quality_path)  # retry no novo servidor
            return None, 0.0, 0.0, 0.0
