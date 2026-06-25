import pandas as pd
import matplotlib.pyplot as plt
import os
import sys

def generate_individual_graphs(csv_path, output_base_dir, policy_name):
    """Gera gráficos individuais detalhados para uma política, incluindo marcas de Failover."""
    if not os.path.exists(csv_path): return
    df = pd.read_csv(csv_path)
    policy_dir = os.path.join(output_base_dir, 'individual', policy_name)
    os.makedirs(policy_dir, exist_ok=True)

    # Identificar segmentos de Failover (mudança de server_id)
    failover_segments = []
    if 'server_id' in df.columns:
        df['server_changed'] = df['server_id'] != df['server_id'].shift(1)
        failover_segments = df[df['server_changed'] & (df.index > 0)]['segment'].tolist()

    # --- 1. Vazão vs Qualidade (com dois eixos e marcas de Failover) ---
    fig, ax1 = plt.subplots(figsize=(12, 7))
    manifest_qualities = {200: '240p', 400: '360p', 600: '480p', 900: '720p', 1200: '1080p'}
    bitrate_thresholds = sorted(manifest_qualities.keys())
    quality_labels = [manifest_qualities[b] for b in bitrate_thresholds]

    ax1.plot(df['segment'], df['vazão_kbps'], label='Vazão Medida (kbps)', color='tab:blue', marker='o', linestyle='--', alpha=0.4)
    ax1.step(df['segment'], df['bitrate_kbps'], label='Bitrate Selecionado (kbps)', color='tab:red', where='post', linewidth=3)
    
    for seg in failover_segments:
        ax1.axvline(x=seg, color='red', linestyle='--', linewidth=2, label='Failover' if seg == failover_segments[0] else "")
    
    ax1.set_xlabel('Segmento')
    ax1.set_ylabel('Vazão / Bitrate (kbps)')
    ax1.grid(True, which='both', linestyle='--', alpha=0.5)

    # Segundo eixo Y para as resoluções
    ax2 = ax1.twinx()
    ax2.set_ylim(ax1.get_ylim())
    ax2.set_yticks(bitrate_thresholds)
    ax2.set_yticklabels(quality_labels)
    ax2.set_ylabel('Qualidade (Resolução)')
    ax2.tick_params(axis='y', labelcolor='tab:red')

    # Terceiro eixo Y para o Jitter EWMA
    if 'jitter_ewma_ms' in df.columns:
        ax3 = ax1.twinx()
        ax3.spines['right'].set_position(('outward', 60))
        ax3.plot(df['segment'], df['jitter_ewma_ms'], label='Jitter EWMA (ms)', color='purple', linestyle=':', linewidth=2)
        ax3.set_ylabel('Jitter EWMA (ms)', color='purple')
        ax3.tick_params(axis='y', labelcolor='purple')
        
        lines_1, labels_1 = ax1.get_legend_handles_labels()
        lines_3, labels_3 = ax3.get_legend_handles_labels()
        ax1.legend(lines_1 + lines_3, labels_1 + labels_3, loc='upper left')
    else:
        ax1.legend(loc='upper left')

    plt.title(f'Vazão vs Qualidade vs Jitter: {policy_name.upper()}')
    fig.tight_layout()
    plt.savefig(os.path.join(policy_dir, 'vazao_vs_qualidade.png'))
    plt.close()

    # --- 2. Nível de Buffer Individual (com marcas de Failover) ---
    plt.figure(figsize=(10, 6))
    plt.plot(df['segment'], df['buffer_level_s'], label='Buffer (s)', color='green', linewidth=2)
    
    for seg in failover_segments:
        plt.axvline(x=seg, color='red', linestyle='--', linewidth=1.5)
    
    plt.axhline(y=5.0, color='orange', linestyle=':', label='Zona de Pânico')
    plt.xlabel('Segmento')
    plt.ylabel('Segundos')
    plt.title(f'Nível do Buffer: {policy_name.upper()}')
    plt.legend()
    plt.grid(True, alpha=0.2)
    plt.savefig(os.path.join(policy_dir, 'nivel_buffer.png'))
    plt.close()

def generate_iqs_comparison(df_base, df_buff, df_heur, output_dir):
    """Gera gráfico do Índice de Qualidade Segura (IQS) com SATURAÇÃO."""
    max_bitrate = max(df_base['bitrate_kbps'].max(), df_buff['bitrate_kbps'].max())
    if df_heur is not None: max_bitrate = max(max_bitrate, df_heur['bitrate_kbps'].max())
    SATURATION_LIMIT = 20.0 # Segundos
    
    df_base['iqs'] = df_base['buffer_level_s'].clip(upper=SATURATION_LIMIT) * (df_base['bitrate_kbps'] / max_bitrate)
    df_buff['iqs'] = df_buff['buffer_level_s'].clip(upper=SATURATION_LIMIT) * (df_buff['bitrate_kbps'] / max_bitrate)
    if df_heur is not None:
        df_heur['iqs'] = df_heur['buffer_level_s'].clip(upper=SATURATION_LIMIT) * (df_heur['bitrate_kbps'] / max_bitrate)
    
    plt.figure(figsize=(12, 6))
    plt.fill_between(df_base['segment'], df_base['iqs'], color='orange', alpha=0.2, label='Baseline (Eficiência)')
    plt.plot(df_base['segment'], df_base['iqs'], color='orange', linestyle='--', alpha=0.5)
    
    plt.fill_between(df_buff['segment'], df_buff['iqs'], color='green', alpha=0.3, label='Política 2 (Eficiência)')
    plt.plot(df_buff['segment'], df_buff['iqs'], color='green', linewidth=2)
    
    if df_heur is not None:
        plt.fill_between(df_heur['segment'], df_heur['iqs'], color='purple', alpha=0.3, label='Heurística (Eficiência)')
        plt.plot(df_heur['segment'], df_heur['iqs'], color='purple', linewidth=2, linestyle='-.')
        
    plt.xlabel('Segmento')
    plt.ylabel('Índice IQS (Buffer Saturado em 20s)')
    plt.title('Comparativo de Eficiência: IQS (Safe Quality Index)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(output_dir, 'comparativo_eficiencia_iqs.png'))
    plt.close()

def generate_cumulative_bitrate_comparison(df_base, df_buff, df_heur, output_dir):
    """Gera gráfico de Bitrate Acumulado (Zera se can_play == 0)."""
    def get_cumulative(df):
        cum_sum, result = 0, []
        for _, row in df.iterrows():
            if row['buffer_can_play'] == 1: cum_sum += row['bitrate_kbps']
            else: cum_sum = 0
            result.append(cum_sum)
        return result

    plt.figure(figsize=(12, 6))
    plt.plot(df_base['segment'], get_cumulative(df_base), label='Baseline (Acumulado)', color='orange', linestyle='--')
    plt.plot(df_buff['segment'], get_cumulative(df_buff), label='Política 2 (Acumulado)', color='green', linewidth=2)
    if df_heur is not None:
        plt.plot(df_heur['segment'], get_cumulative(df_heur), label='Heurística (Acumulado)', color='purple', linewidth=2, linestyle='-.')
        
    plt.xlabel('Segmento')
    plt.ylabel('Bitrate Total Acumulado (kbps)')
    plt.title('Continuidade de Qualidade: Bitrate Acumulado')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(output_dir, 'comparativo_bitrate_acumulado.png'))
    plt.close()

def generate_correlation_grid(df_base, df_buff, df_heur, output_dir):
    has_heur = df_heur is not None
    n_plots = 3 if has_heur else 2
    fig, axes = plt.subplots(n_plots, 1, figsize=(14, 5 * n_plots), sharex=True)
    if not has_heur: axes = [axes[0], axes[1]]
    
    dfs = [df_base, df_buff]
    titles = ['BASELINE (Rate-Based)', 'POLÍTICA 2 (Buffer-Based)']
    if has_heur:
        dfs.append(df_heur)
        titles.append('POLÍTICA 3 (Heurística)')
        
    for ax, df, title in zip(axes, dfs, titles):
        ax.plot(df['segment'], df['buffer_level_s'], color='green', label='Buffer (s)')
        ax.set_ylabel('Buffer (s)', color='green')
        ax2 = ax.twinx()
        ax2.step(df['segment'], df['bitrate_kbps'], color='red', alpha=0.5, label='Bitrate (kbps)', where='post')
        ax2.set_ylabel('Bitrate (kbps)', color='red')
        ax.set_title(f'Correlação: {title}')
        ax.grid(True, alpha=0.2)
    plt.xlabel('Segmento')
    fig.tight_layout()
    plt.savefig(os.path.join(output_dir, 'comparativo_correlacao_grid.png'))
    plt.close()

def generate_jitter_comparison(df_base, df_buff, df_heur, output_dir):
    """Gera gráfico de Jitter EWMA (Exigência do Roteiro Fase 3)."""
    plt.figure(figsize=(12, 6))
    
    # Adicionamos a linha de failover baseando-se no df_base
    failover_segments = []
    if 'server_id' in df_base.columns:
        df_base['server_changed'] = df_base['server_id'] != df_base['server_id'].shift(1)
        failover_segments = df_base[df_base['server_changed'] & (df_base.index > 0)]['segment'].tolist()
        
    for seg in failover_segments:
        plt.axvline(x=seg, color='red', linestyle='--', linewidth=2, label='Failover' if seg == failover_segments[0] else "")
    
    plt.plot(df_base['segment'], df_base['jitter_ewma_ms'], label='Baseline', color='orange', linestyle='--', alpha=0.5)
    plt.plot(df_buff['segment'], df_buff['jitter_ewma_ms'], label='Política 2', color='green', linewidth=2, alpha=0.7)
    
    if df_heur is not None:
        plt.plot(df_heur['segment'], df_heur['jitter_ewma_ms'], label='Heurística', color='purple', linewidth=3)
        
    plt.xlabel('Segmento')
    plt.ylabel('Jitter EWMA (ms)')
    plt.title('Variação de Atraso Suavizada (Jitter EWMA) ao longo do Tempo')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(output_dir, 'comparativo_jitter_ewma.png'))
    plt.close()

def generate_comparison_graphs(csv_baseline, csv_buffer, csv_heuristic, output_base_dir):
    if not os.path.exists(csv_baseline) or not os.path.exists(csv_buffer): return
    df_base, df_buff = pd.read_csv(csv_baseline), pd.read_csv(csv_buffer)
    df_heur = pd.read_csv(csv_heuristic) if os.path.exists(csv_heuristic) else None
    
    comp_dir = os.path.join(output_base_dir, 'comparison')
    os.makedirs(comp_dir, exist_ok=True)
    generate_correlation_grid(df_base, df_buff, df_heur, comp_dir)
    generate_iqs_comparison(df_base, df_buff, df_heur, comp_dir)
    generate_cumulative_bitrate_comparison(df_base, df_buff, df_heur, comp_dir)
    generate_jitter_comparison(df_base, df_buff, df_heur, comp_dir)

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    metrics_dir = os.path.join(current_dir, '../metrics')
    for p in ['baseline', 'buffer', 'heuristic']:
        csv = os.path.join(metrics_dir, f'streaming_metrics_{p}.csv')
        generate_individual_graphs(csv, current_dir, p)
    csv_base = os.path.join(metrics_dir, 'streaming_metrics_baseline.csv')
    csv_buff = os.path.join(metrics_dir, 'streaming_metrics_buffer.csv')
    csv_heur = os.path.join(metrics_dir, 'streaming_metrics_heuristic.csv')
    generate_comparison_graphs(csv_base, csv_buff, csv_heur, current_dir)
