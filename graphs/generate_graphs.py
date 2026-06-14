import pandas as pd
import matplotlib.pyplot as plt
import os
import sys

def generate_individual_graphs(csv_path, output_base_dir, policy_name):
    """Gera gráficos individuais básicos para uma política."""
    if not os.path.exists(csv_path): return
    df = pd.read_csv(csv_path)
    policy_dir = os.path.join(output_base_dir, 'individual', policy_name)
    os.makedirs(policy_dir, exist_ok=True)

    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.plot(df['segment'], df['vazão_kbps'], label='Vazão (kbps)', color='tab:blue', alpha=0.3)
    ax1.step(df['segment'], df['bitrate_kbps'], label='Bitrate (kbps)', color='tab:red', where='post', linewidth=2)
    ax1.set_ylabel('kbps')
    ax1.legend(loc='upper left')
    plt.title(f'Performance Individual: {policy_name.upper()}')
    plt.savefig(os.path.join(policy_dir, 'vazao_vs_bitrate.png'))
    plt.close()

def generate_iqs_comparison(df_base, df_buff, output_dir):
    """Gera gráfico do Índice de Qualidade Segura (IQS) com SATURAÇÃO."""
    max_bitrate = max(df_base['bitrate_kbps'].max(), df_buff['bitrate_kbps'].max())
    SATURATION_LIMIT = 20.0 # Segundos
    
    # Cálculo com saturação: o buffer acima de 20s não gera pontos extras de "inteligência"
    df_base['iqs'] = df_base['buffer_level_s'].clip(upper=SATURATION_LIMIT) * (df_base['bitrate_kbps'] / max_bitrate)
    df_buff['iqs'] = df_buff['buffer_level_s'].clip(upper=SATURATION_LIMIT) * (df_buff['bitrate_kbps'] / max_bitrate)
    
    plt.figure(figsize=(12, 6))
    plt.fill_between(df_base['segment'], df_base['iqs'], color='orange', alpha=0.3, label='Baseline (Eficiência)')
    plt.plot(df_base['segment'], df_base['iqs'], color='orange', linestyle='--', alpha=0.6)
    
    plt.fill_between(df_buff['segment'], df_buff['iqs'], color='green', alpha=0.4, label='Política 2 (Eficiência)')
    plt.plot(df_buff['segment'], df_buff['iqs'], color='green', linewidth=2)
    
    plt.xlabel('Segmento')
    plt.ylabel('Índice IQS (Buffer Saturado em 20s)')
    plt.title('Índice de Qualidade Segura (IQS): Eficiência Real com Teto de Segurança')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(output_dir, 'comparativo_eficiencia_iqs.png'))
    plt.close()

def generate_cumulative_bitrate_comparison(df_base, df_buff, output_dir):
    """Gera gráfico de Bitrate Acumulado (Zera se can_play == 0)."""
    
    def get_cumulative(df):
        cum_sum = 0
        result = []
        for _, row in df.iterrows():
            if row['buffer_can_play'] == 1:
                cum_sum += row['bitrate_kbps']
            else:
                cum_sum = 0 # Stall detectado: reseta o progresso de "qualidade entregue"
            result.append(cum_sum)
        return result

    plt.figure(figsize=(12, 6))
    plt.plot(df_base['segment'], get_cumulative(df_base), label='Baseline (Acumulado)', color='orange', linestyle='--')
    plt.plot(df_buff['segment'], get_cumulative(df_buff), label='Política 2 (Acumulado)', color='green', linewidth=2)
    
    plt.xlabel('Segmento')
    plt.ylabel('Bitrate Total Acumulado (kbps)')
    plt.title('Continuidade de Qualidade: Bitrate Acumulado (Reseta em caso de Stall)')
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
    if not os.path.exists(csv_baseline) or not os.path.exists(csv_buffer):
        return
    df_base = pd.read_csv(csv_baseline)
    df_buff = pd.read_csv(csv_buffer)
    comp_dir = os.path.join(output_base_dir, 'comparison')
    os.makedirs(comp_dir, exist_ok=True)

    generate_correlation_grid(df_base, df_buff, comp_dir)
    generate_iqs_comparison(df_base, df_buff, comp_dir)
    generate_cumulative_bitrate_comparison(df_base, df_buff, comp_dir)
    print(f"Gráficos comparativos (IQS Saturado e Acumulado) gerados em: {comp_dir}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    metrics_dir = os.path.join(current_dir, '../metrics')
    for p in ['baseline', 'buffer']:
        csv = os.path.join(metrics_dir, f'streaming_metrics_{p}.csv')
        generate_individual_graphs(csv, current_dir, p)
    csv_base = os.path.join(metrics_dir, 'streaming_metrics_baseline.csv')
    csv_buff = os.path.join(metrics_dir, 'streaming_metrics_buffer.csv')
    generate_comparison_graphs(csv_base, csv_buff, current_dir)
