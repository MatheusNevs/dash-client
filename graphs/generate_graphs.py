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
    manifest_qualities = {200: '240p', 400: '360p', 700: '480p', 1500: '720p', 3000: '1080p'}
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

    plt.title(f'Vazão vs Qualidade: {policy_name.upper()} (com Failover)')
    ax1.legend(loc='upper left')
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

def generate_iqs_comparison(df_base, df_buff, output_dir):
    """Gera gráfico do Índice de Qualidade Segura (IQS) com SATURAÇÃO."""
    max_bitrate = max(df_base['bitrate_kbps'].max(), df_buff['bitrate_kbps'].max())
    SATURATION_LIMIT = 20.0 # Segundos
    
    df_base['iqs'] = df_base['buffer_level_s'].clip(upper=SATURATION_LIMIT) * (df_base['bitrate_kbps'] / max_bitrate)
    df_buff['iqs'] = df_buff['buffer_level_s'].clip(upper=SATURATION_LIMIT) * (df_buff['bitrate_kbps'] / max_bitrate)
    
    plt.figure(figsize=(12, 6))
    plt.fill_between(df_base['segment'], df_base['iqs'], color='orange', alpha=0.2, label='Baseline (Eficiência)')
    plt.plot(df_base['segment'], df_base['iqs'], color='orange', linestyle='--', alpha=0.5)
    
    plt.fill_between(df_buff['segment'], df_buff['iqs'], color='green', alpha=0.3, label='Política 2 (Eficiência)')
    plt.plot(df_buff['segment'], df_buff['iqs'], color='green', linewidth=2)
    
    plt.xlabel('Segmento')
    plt.ylabel('Índice IQS (Buffer Saturado em 20s)')
    plt.title('Comparativo de Eficiência: IQS (Safe Quality Index)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(output_dir, 'comparativo_eficiencia_iqs.png'))
    plt.close()

def generate_cumulative_bitrate_comparison(df_base, df_buff, output_dir):
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
    plt.xlabel('Segmento')
    plt.ylabel('Bitrate Total Acumulado (kbps)')
    plt.title('Continuidade de Qualidade: Bitrate Acumulado')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(output_dir, 'comparativo_bitrate_acumulado.png'))
    plt.close()

def generate_correlation_grid(df_base, df_buff, output_dir):
    fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    for ax, df, title in zip([ax_top, ax_bot], [df_base, df_buff], ['BASELINE (Rate-Based)', 'POLÍTICA 2 (Buffer-Based)']):
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

def generate_comparison_graphs(csv_baseline, csv_buffer, output_base_dir):
    if not os.path.exists(csv_baseline) or not os.path.exists(csv_buffer): return
    df_base, df_buff = pd.read_csv(csv_baseline), pd.read_csv(csv_buffer)
    comp_dir = os.path.join(output_base_dir, 'comparison')
    os.makedirs(comp_dir, exist_ok=True)
    generate_correlation_grid(df_base, df_buff, comp_dir)
    generate_iqs_comparison(df_base, df_buff, comp_dir)
    generate_cumulative_bitrate_comparison(df_base, df_buff, comp_dir)

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    metrics_dir = os.path.join(current_dir, '../metrics')
    for p in ['baseline', 'buffer']:
        csv = os.path.join(metrics_dir, f'streaming_metrics_{p}.csv')
        generate_individual_graphs(csv, current_dir, p)
    csv_base = os.path.join(metrics_dir, 'streaming_metrics_baseline.csv')
    csv_buff = os.path.join(metrics_dir, 'streaming_metrics_buffer.csv')
    generate_comparison_graphs(csv_base, csv_buff, current_dir)
