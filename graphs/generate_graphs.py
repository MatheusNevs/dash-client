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
    fig, ax1 = plt.subplots(figsize=(12, 7))

    # Define the quality bitrates from the manifest for alignment
    manifest_qualities = {
        200: '240p',
        400: '360p',
        700: '480p',
        1500: '720p',
        3000: '1080p'
    }
    bitrate_thresholds = sorted(manifest_qualities.keys())
    quality_labels = [manifest_qualities[b] for b in bitrate_thresholds]

    # Primary axis: Throughput and Bitrate Line
    ax1.plot(df['segment'], df['vazão_kbps'], label='Vazão Medida (kbps)', color='tab:blue', marker='o', linestyle='--', alpha=0.4)
    ax1.step(df['segment'], df['bitrate_kbps'], label='Bitrate Selecionado (kbps)', color='tab:red', where='post', linewidth=3)
    
    ax1.set_xlabel('Segmento')
    ax1.set_ylabel('Vazão / Bitrate (kbps)')
    ax1.grid(True, which='both', linestyle='--', alpha=0.5)

    # Secondary axis: Quality Labels aligned with bitrates
    ax2 = ax1.twinx()
    ax2.set_ylim(ax1.get_ylim()) # Keep the same scale as ax1
    
    ax2.set_yticks(bitrate_thresholds)
    ax2.set_yticklabels(quality_labels)
    ax2.set_ylabel('Qualidade (Resolução)')
    ax2.tick_params(axis='y', labelcolor='tab:red')

    # Highlight thresholds with horizontal lines
    for threshold in bitrate_thresholds:
        ax1.axhline(y=threshold, color='gray', linestyle=':', alpha=0.3)

    plt.title('Vazão vs Qualidade (Alinhada por Bitrate)')
    ax1.legend(loc='upper left')
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
