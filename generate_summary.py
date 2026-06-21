import pandas as pd
import os

def analyze_policy(csv_path, name):
    if not os.path.exists(csv_path):
        return None
    
    df = pd.read_csv(csv_path)
    
    # Cálculos estatísticos
    avg_bitrate = df['bitrate_kbps'].mean()
    avg_vazao = df['vazão_kbps'].mean()
    avg_buffer = df['buffer_level_s'].mean()
    total_stalls = df['rebuffer_event'].sum()
    total_stall_duration = df['stall_duration_s'].sum()
    
    # Estabilidade: Quantidade de vezes que a qualidade mudou
    df['quality_changed'] = df['quality'] != df['quality'].shift(1)
    switches = df['quality_changed'].sum() - 1 # Desconta o primeiro segmento
    
    # Eficiência (IQS Saturado em 20s)
    max_bitrate = 3000 # 1080p
    df['iqs'] = df['buffer_level_s'].clip(upper=20) * (df['bitrate_kbps'] / max_bitrate)
    avg_iqs = df['iqs'].mean()

    return {
        'name': name,
        'avg_bitrate': avg_bitrate,
        'avg_vazao': avg_vazao,
        'avg_buffer': avg_buffer,
        'switches': int(switches),
        'stalls': int(total_stalls),
        'stall_duration': total_stall_duration,
        'avg_iqs': avg_iqs
    }

def main():
    metrics_dir = os.path.join(os.path.dirname(__file__), 'metrics')
    baseline = analyze_policy(os.path.join(metrics_dir, 'streaming_metrics_baseline.csv'), "Baseline (Rate-Based)")
    buffer_based = analyze_policy(os.path.join(metrics_dir, 'streaming_metrics_buffer.csv'), "Política 2 (Buffer-Based)")

    if not baseline or not buffer_based:
        print("Erro: CSVs não encontrados. Execute o cliente primeiro.")
        return

    print("="*60)
    print("RESUMO ESTATÍSTICO PARA O RELATÓRIO - FASE 2")
    print("="*60)
    
    template = "{:<30} | {:<12} | {:<12}"
    print(template.format("Métrica", "Baseline", "Buffer-Based"))
    print("-" * 60)
    
    print(template.format("Bitrate Médio (kbps)", f"{baseline['avg_bitrate']:.2f}", f"{buffer_based['avg_bitrate']:.2f}"))
    print(template.format("Vazão Média (kbps)", f"{baseline['avg_vazao']:.2f}", f"{buffer_based['avg_vazao']:.2f}"))
    print(template.format("Buffer Médio (s)", f"{baseline['avg_buffer']:.2f}", f"{buffer_based['avg_buffer']:.2f}"))
    print(template.format("Trocas de Qualidade", f"{baseline['switches']}", f"{buffer_based['switches']}"))
    print(template.format("Total de Travamentos", f"{baseline['stalls']}", f"{buffer_based['stalls']}"))
    print(template.format("Duração Total Stall (s)", f"{baseline['stall_duration']:.2f}", f"{buffer_based['stall_duration']:.2f}"))
    print(template.format("Eficiência (IQS Médio)", f"{baseline['avg_iqs']:.2f}", f"{buffer_based['avg_iqs']:.2f}"))
    print("="*60)

    # Conclusões Automáticas
    print("\nINSIGHTS PARA A DISCUSSÃO DO RELATÓRIO:")
    if buffer_based['switches'] < baseline['switches']:
        reduction = (1 - (buffer_based['switches'] / baseline['switches'])) * 100
        print(f"- A Política 2 reduziu as oscilações de qualidade em {reduction:.1f}% em comparação à Baseline.")
    
    if buffer_based['avg_iqs'] > baseline['avg_iqs']:
        print(f"- A Política 2 foi {((buffer_based['avg_iqs']/baseline['avg_iqs'])-1)*100:.1f}% mais eficiente no equilíbrio Qualidade vs Segurança.")
    
    if buffer_based['stalls'] == 0 and baseline['stalls'] > 0:
        print("- A Política 2 eliminou completamente os eventos de rebuffering observados na Baseline.")
    
    print("\nOBSERVAÇÃO SOBRE O FAILOVER:")
    print("- Verifique no gráfico 'vazao_vs_bitrate' das pastas individuais se o cliente manteve 'buffer_can_play=1'")
    print("  no momento das linhas tracejadas vermelhas.")
    print("="*60)

if __name__ == "__main__":
    main()
