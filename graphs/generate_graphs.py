import pandas as pd
import matplotlib.pyplot as plt
import os
import sys

def generate_graphs(csv_path, output_dir):
    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
        return

    df = pd.read_csv(csv_path)
    os.makedirs(output_dir, exist_ok=True)

    # 1. Throughput vs Quality Bitrate
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Primary axis: Throughput
    ax1.plot(df['segment'], df['vazão_kbps'], label='Vazão Medida (kbps)', color='tab:blue', marker='o', linestyle='--', alpha=0.6)
    ax1.set_xlabel('Segmento')
    ax1.set_ylabel('Vazão (kbps)', color='tab:blue')
    ax1.tick_params(axis='y', labelcolor='tab:blue')
    ax1.grid(True, which='both', linestyle='--', alpha=0.5)

    # Secondary axis: Quality Labels
    ax2 = ax1.twinx()
    
    # Define quality order for visualization
    quality_order = ['240p', '360p', '480p', '720p', '1080p']
    # Map the quality column to its index in the order
    df['quality_idx'] = df['quality'].apply(lambda x: quality_order.index(x) if x in quality_order else -1)
    
    ax2.step(df['segment'], df['quality_idx'], label='Qualidade Selecionada', color='tab:red', where='post', linewidth=3)
    ax2.set_ylabel('Qualidade (Resolução)', color='tab:red')
    ax2.set_yticks(range(len(quality_order)))
    ax2.set_yticklabels(quality_order)
    ax2.tick_params(axis='y', labelcolor='tab:red')
    ax2.set_ylim(-0.5, len(quality_order) - 0.5)

    plt.title('Vazão vs Qualidade Selecionada')
    fig.tight_layout()
    plt.savefig(os.path.join(output_dir, 'vazao_vs_qualidade.png'))
    plt.close()

    # 2. Buffer Level
    plt.figure(figsize=(10, 6))
    plt.plot(df['segment'], df['buffer_level_s'], label='Nível do Buffer (s)', color='green')
    plt.axhline(y=2.0, color='r', linestyle='--', label='Limite Mínimo (1 segmento)')
    plt.xlabel('Segmento')
    plt.ylabel('Segundos')
    plt.title('Nível do Buffer ao Longo dos Segmentos')
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'nivel_buffer.png'))
    plt.close()

    print(f"Graphs generated in {output_dir}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file = os.path.join(current_dir, '../metrics/streaming_metrics.csv')
    output_folder = os.path.join(current_dir, './')
    
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    
    generate_graphs(csv_file, output_folder)
