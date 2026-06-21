"""
generate_graphs.py — Gera gráficos comparativos das 3 políticas ABR.

Uso:
  python3 graphs/generate_graphs.py
  python3 graphs/generate_graphs.py ../metrics/streaming_metrics_heuristic.csv

Gráficos gerados (pasta graphs/):
  1. vazao_vs_qualidade_<policy>.png  — Vazão medida vs Bitrate selecionado
  2. nivel_buffer_<policy>.png        — Nível de buffer por segmento
  3. jitter_ewma_<policy>.png         — Jitter EWMA ao longo dos segmentos (Política 3)
  4. comparativo_3_politicas.png      — Subplots lado a lado das 3 políticas
"""

from __future__ import annotations
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec


# ── Mapa de bitrates → labels de qualidade ───────────────────
MANIFEST_QUALITIES = {200: "240p", 400: "360p", 700: "480p", 1500: "720p", 3000: "1080p"}
BITRATE_THRESHOLDS = sorted(MANIFEST_QUALITIES.keys())
QUALITY_LABELS     = [MANIFEST_QUALITIES[b] for b in BITRATE_THRESHOLDS]

POLICY_COLORS = {
    "baseline":  "tab:blue",
    "buffer":    "tab:orange",
    "heuristic": "tab:green",
}
POLICY_LABELS = {
    "baseline":  "Política 1 — Baseline (Rate-Based)",
    "buffer":    "Política 2 — Buffer-Based (Histerese)",
    "heuristic": "Política 3 — Heurística (EWMA + Jitter)",
}


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _detect_failovers(df: pd.DataFrame) -> list[int]:
    if "server_id" not in df.columns:
        return []
    changed = df["server_id"] != df["server_id"].shift(1)
    return df[changed & (df.index > 0)]["segment"].tolist()


def _add_failover_lines(ax, failover_segs: list[int]) -> None:
    for idx, seg in enumerate(failover_segs):
        ax.axvline(x=seg, color="red", linestyle="--", linewidth=1.5,
                   label="Failover" if idx == 0 else "")


# ─────────────────────────────────────────────────────────────
# Gráficos individuais por política
# ─────────────────────────────────────────────────────────────

def generate_graphs(csv_path: str, output_dir: str, policy_name: str = "baseline") -> None:
    if not os.path.exists(csv_path):
        print(f"[Graphs] CSV não encontrado: {csv_path}")
        return

    df = pd.read_csv(csv_path)
    os.makedirs(output_dir, exist_ok=True)
    failover_segs = _detect_failovers(df)
    color = POLICY_COLORS.get(policy_name, "tab:blue")

    # ── Gráfico 1: Vazão vs Qualidade ────────────────────────
    fig, ax1 = plt.subplots(figsize=(12, 6))

    ax1.plot(df["segment"], df["vazão_kbps"],
             label="Vazão Medida (kbps)", color=color, marker="o",
             linestyle="--", alpha=0.5)
    ax1.step(df["segment"], df["bitrate_kbps"],
             label="Bitrate Selecionado (kbps)", color="tab:red",
             where="post", linewidth=2.5)

    for t in BITRATE_THRESHOLDS:
        ax1.axhline(y=t, color="gray", linestyle=":", alpha=0.3)

    _add_failover_lines(ax1, failover_segs)

    ax2 = ax1.twinx()
    ax2.set_ylim(ax1.get_ylim())
    ax2.set_yticks(BITRATE_THRESHOLDS)
    ax2.set_yticklabels(QUALITY_LABELS)
    ax2.set_ylabel("Qualidade")
    ax2.tick_params(axis="y", labelcolor="tab:red")

    ax1.set_xlabel("Segmento")
    ax1.set_ylabel("Vazão / Bitrate (kbps)")
    ax1.set_title(f"Vazão vs Qualidade — {POLICY_LABELS.get(policy_name, policy_name)}")
    ax1.legend(loc="upper left")
    ax1.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    plt.savefig(os.path.join(output_dir, f"vazao_vs_qualidade_{policy_name}.png"), dpi=150)
    plt.close()

    # ── Gráfico 2: Nível de buffer ────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df["segment"], df["buffer_level_s"],
            label="Buffer (s)", color="green", linewidth=2)
    ax.axhline(y=2.0, color="r", linestyle="--", label="Mínimo (1 segmento)")
    _add_failover_lines(ax, failover_segs)
    ax.set_xlabel("Segmento")
    ax.set_ylabel("Segundos")
    ax.set_title(f"Nível do Buffer — {POLICY_LABELS.get(policy_name, policy_name)}")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    plt.savefig(os.path.join(output_dir, f"nivel_buffer_{policy_name}.png"), dpi=150)
    plt.close()

    # ── Gráfico 3: Jitter EWMA (só para política heurística) ──
    if "jitter_ewma_ms" in df.columns and policy_name == "heuristic":
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(df["segment"], df["jitter_ewma_ms"],
                label="Jitter EWMA (ms)", color="purple", linewidth=2)
        ax.plot(df["segment"], df["jitter_network_ms"],
                label="Jitter Bruto (ms)", color="plum",
                linestyle="--", alpha=0.6)
        ax.set_xlabel("Segmento")
        ax.set_ylabel("Jitter (ms)")
        ax.set_title("Jitter de Rede — EWMA vs Bruto (Política 3)")
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.4)
        fig.tight_layout()
        plt.savefig(os.path.join(output_dir, f"jitter_ewma_{policy_name}.png"), dpi=150)
        plt.close()

    print(f"[Graphs] Gráficos de '{policy_name}' salvos em: {output_dir}")


# ─────────────────────────────────────────────────────────────
# Gráfico comparativo — 3 políticas sobrepostas em subplots
# ─────────────────────────────────────────────────────────────

def generate_comparative(metrics_dir: str, output_dir: str) -> None:
    """
    Gera um único arquivo comparativo com subplots das 3 políticas.
    Requer que os 3 CSVs já existam.
    """
    policies = ["baseline", "buffer", "heuristic"]
    dfs: dict[str, pd.DataFrame] = {}
    for p in policies:
        path = os.path.join(metrics_dir, f"streaming_metrics_{p}.csv")
        if os.path.exists(path):
            dfs[p] = pd.read_csv(path)

    if not dfs:
        print("[Graphs] Nenhum CSV encontrado para o comparativo.")
        return

    os.makedirs(output_dir, exist_ok=True)

    fig = plt.figure(figsize=(16, 14))
    gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.5, wspace=0.35)

    for row_idx, policy in enumerate(policies):
        if policy not in dfs:
            continue
        df    = dfs[policy]
        color = POLICY_COLORS[policy]
        label = POLICY_LABELS[policy]
        failover_segs = _detect_failovers(df)

        # Coluna esquerda: Vazão vs Bitrate
        ax_left = fig.add_subplot(gs[row_idx, 0])
        ax_left.plot(df["segment"], df["vazão_kbps"],
                     color=color, linestyle="--", alpha=0.5, label="Vazão")
        ax_left.step(df["segment"], df["bitrate_kbps"],
                     color="tab:red", where="post", linewidth=2, label="Bitrate")
        _add_failover_lines(ax_left, failover_segs)
        ax_left.set_title(f"{label}\nVazão vs Qualidade", fontsize=9)
        ax_left.set_xlabel("Segmento", fontsize=8)
        ax_left.set_ylabel("kbps", fontsize=8)
        ax_left.legend(fontsize=7)
        ax_left.grid(True, linestyle="--", alpha=0.3)

        # Coluna direita: Buffer
        ax_right = fig.add_subplot(gs[row_idx, 1])
        ax_right.plot(df["segment"], df["buffer_level_s"],
                      color="green", linewidth=1.8, label="Buffer")
        ax_right.axhline(y=2.0, color="r", linestyle="--", linewidth=1,
                         label="Mínimo")
        _add_failover_lines(ax_right, failover_segs)
        ax_right.set_title(f"{label}\nNível do Buffer", fontsize=9)
        ax_right.set_xlabel("Segmento", fontsize=8)
        ax_right.set_ylabel("Segundos", fontsize=8)
        ax_right.legend(fontsize=7)
        ax_right.grid(True, linestyle="--", alpha=0.3)

    fig.suptitle("Comparativo das 3 Políticas ABR — TR2 UnB", fontsize=13, y=0.98)
    out_path = os.path.join(output_dir, "comparativo_3_politicas.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"[Graphs] Comparativo salvo em: {out_path}")


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    current_dir  = os.path.dirname(os.path.abspath(__file__))
    metrics_dir  = os.path.join(current_dir, "../metrics")
    output_folder = os.path.join(current_dir, "./")

    if len(sys.argv) > 1:
        # Modo arquivo único passado por argumento
        csv_file = sys.argv[1]
        policy   = os.path.basename(csv_file).replace("streaming_metrics_", "").replace(".csv", "")
        generate_graphs(csv_file, output_folder, policy)
    else:
        # Gera gráficos individuais para cada CSV disponível
        for policy_name in ["baseline", "buffer", "heuristic"]:
            csv_file = os.path.join(metrics_dir, f"streaming_metrics_{policy_name}.csv")
            generate_graphs(csv_file, output_folder, policy_name)
        # Gera o comparativo
        generate_comparative(metrics_dir, output_folder)
