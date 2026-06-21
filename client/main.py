"""
main.py — Orquestrador principal do cliente DASH adaptativo.

Uso:
  python3 client/main.py [-n SEGMENTOS] [-p {baseline,buffer,heuristic}]

Políticas disponíveis:
  baseline   → Política 1: Rate-Based simples (safety_factor=0.8)
  buffer     → Política 2: Buffer-Based com histerese
  heuristic  → Política 3: EWMA de vazão com penalidade de jitter
"""

from __future__ import annotations
import time
import sys
import os
import argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from network          import NetworkManager
from buffer           import BufferManager
from abr              import BaselinePolicy, BufferBasedPolicy, HeuristicPolicy
from metrics_collector import MetricsCollector


def run_client(
    num_segments: int,
    policy_name: str,
    manifest_url: str = "http://137.131.178.229:8080/manifest",
) -> None:
    output_csv = os.path.join(
        os.path.dirname(__file__),
        f"../metrics/streaming_metrics_{policy_name}.csv",
    )

    # ── Rede e manifesto ──────────────────────────────────────
    network  = NetworkManager(manifest_url)
    manifest = network.fetch_manifest()
    if not manifest:
        print("[Main] Falha ao buscar manifesto. Abortando.")
        return

    # ── Componentes ───────────────────────────────────────────
    buffer  = BufferManager(manifest["segment_duration_s"])
    metrics = MetricsCollector(os.path.abspath(output_csv))

    # ── Seleção de política ───────────────────────────────────
    if policy_name == "buffer":
        policy = BufferBasedPolicy()
    elif policy_name == "heuristic":
        policy = HeuristicPolicy(
            alpha=0.3,
            beta=0.3,
            gamma=1.5,
            safety_factor=0.85,
        )
    else:
        policy = BaselinePolicy(safety_factor=0.8)

    print(f"[Main] Iniciando streaming | política={policy_name!r} | "
          f"servidor={network.current_server_url} | segmentos={num_segments}")

    last_throughput = 500.0  # estimativa inicial (kbps)

    # ── Loop principal ────────────────────────────────────────
    for i in range(1, num_segments + 1):
        current_buffer = buffer.get_level()

        # 1. Política 3: atualiza EWMA antes da decisão (com última medição)
        #    Para os segmentos seguintes ao primeiro já teremos dados reais.
        selected_repr = policy.select_quality(
            last_throughput, current_buffer, manifest["representations"]
        )

        # 2. Baixa segmento
        content, download_time, throughput, download_time_ms = network.download_segment(
            selected_repr["url_path"]
        )
        if content is None:
            print(f"[Main] Seg {i:03d}/{num_segments:03d} — falha no download. Pulando.")
            continue

        # 3. Atualiza EWMA da política heurística com os dados reais do segmento
        if isinstance(policy, HeuristicPolicy):
            policy.update_network_sample(throughput, download_time)
            jitter_ewma_ms = policy.ewma_jitter_ms
        else:
            jitter_ewma_ms = 0.0

        # 4. Atualiza buffer
        buffer_can_play_before = 1 if buffer.can_play() else 0
        buffer.add_segment()

        # 5. Atualiza throughput para próxima iteração
        last_throughput = throughput if throughput > 0 else last_throughput

        # 6. Status no terminal (uma linha)
        status = (
            f"Seg {i:03d}/{num_segments:03d} | "
            f"Qualidade={selected_repr['quality']:>5s} | "
            f"Vazão={throughput:7.1f} kbps | "
            f"Buffer={buffer.get_level():.2f}s | "
            f"Jitter_EWMA={jitter_ewma_ms:.1f}ms"
        )
        print(f"\r{status}", end="", flush=True)

        # 7. Registra métricas no CSV
        metric_data = {
            "segment":         i,
            "server_id":       network.current_server_id,
            "quality":         selected_repr["quality"],
            "bitrate_kbps":    selected_repr["bitrate_kbps"],
            "vazão_kbps":      throughput,
            "download_time_s": download_time,
            "jitter_network_ms": download_time_ms,         # delay bruto do segmento
            "jitter_ewma_ms":    jitter_ewma_ms,           # EWMA do jitter (Política 3)
            "buffer_level_s":  buffer.get_level(),
            "buffer_can_play": buffer_can_play_before,
            "rebuffer_event":  1 if (buffer_can_play_before == 0 and i > 1) else 0,
            "stall_duration_s": 0,
            "failover_total":  getattr(network, "failover_count", 0),
        }
        metrics.log_metric(metric_data)

        time.sleep(0.05)  # simula latência mínima entre segmentos

    print(f"\n[Main] Concluído. Métricas salvas em: {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DASH Adaptive Streaming Client")
    parser.add_argument("-n", "--segments",      type=int, default=20,
                        help="Número de segmentos a baixar")
    parser.add_argument("-p", "--policy",        type=str,
                        choices=["baseline", "buffer", "heuristic"],
                        default="baseline",
                        help="Política ABR: baseline | buffer | heuristic")
    parser.add_argument("--manifest",            type=str,
                        default="http://137.131.178.229:8080/manifest",
                        help="URL do manifesto JSON")
    args = parser.parse_args()
    run_client(args.segments, args.policy, args.manifest)
