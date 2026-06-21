# TR2 - Projeto Final: Streaming Adaptativo com ABR

Este repositório contém a implementação de um cliente de streaming de vídeo adaptativo (Adaptive Bitrate - ABR) em Python, desenvolvido para a disciplina de Teleinformática e Redes 2 (UnB).

## 🚀 Visão Geral
O sistema simula o comportamento de um player de vídeo moderno (estilo DASH/HLS). O cliente baixa segmentos de vídeo via HTTP, mede o desempenho da rede em tempo real e decide a qualidade do próximo segmento para garantir a continuidade da reprodução e maximizar a qualidade da imagem.

## ✨ Novidades da Fase 2
- **Política Buffer-Based (BBA):** Algoritmo inteligente com lógica de Histerese para evitar oscilações desnecessárias de qualidade.
- **Failover Automático:** Detecção de falha no servidor principal com migração transparente para servidores de backup e auto-recovery.
- **Métricas Avançadas:** Monitoramento de Jitter (EWMA), Duração de Stall (rebuffering real) e Índice de Qualidade Segura (IQS).
- **Análise Comparativa:** Geração automática de gráficos comparando o desempenho das diferentes políticas.

## 📁 Estrutura do Código (`client/`)
- **`main.py`**: Orquestrador principal. Suporta execução individual ou em lote (modo `all`).
- **`network.py`**: Gerenciador de rede com suporte a Failover, cálculo de latência e Jitter.
- **`abr.py`**: Implementação das políticas:
  - `BaselinePolicy`: Baseada puramente na vazão instantânea.
  - `BufferBasedPolicy`: Baseada no nível de ocupação do buffer (Histerese).
- **`buffer.py`**: Modelo de buffer multi-threaded que simula o consumo de vídeo em tempo real.
- **`metrics_collector.py`**: Coletor de dados estatísticos exportados para CSV.

## 🛠️ Como Executar

1. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Inicie o streaming:**
   ```bash
   # Rodar uma política específica
   python3 client/main.py -n 30 -p buffer

   # Rodar TODAS as políticas e gerar gráficos comparativos automaticamente
   python3 client/main.py -n 30 -p all -g
   ```

3. **Gerar gráficos manualmente:**
   ```bash
   python3 graphs/generate_graphs.py
   ```

## 📊 Gráficos e Analytics
Os resultados são organizados na pasta `graphs/`:
- **`individual/`**: Desempenho detalhado (Vazão vs Bitrate) por política.
- **`comparison/`**: Comparações diretas de eficiência:
  - `comparativo_correlacao_grid.png`: Causa e efeito (Buffer vs Bitrate).
  - `comparativo_eficiencia_iqs.png`: Índice de Qualidade Segura (com saturação de 20s).
  - `comparativo_bitrate_acumulado.png`: Continuidade da experiência de visualização.

## 📊 Métricas Coletadas (CSV)
Os logs em `metrics/` incluem:
- `vazão_kbps` e `bitrate_kbps`.
- `jitter_ewma_ms`: Oscilação da rede suavizada.
- `buffer_level_s`: Estado real do reservatório de vídeo.
- `stall_duration_s`: Tempo exato de travamento do vídeo.
- `failover_total`: Quantidade de trocas de servidor realizadas.

## 🗺️ Roadmap de Desenvolvimento
- [x] **Fase 1**: Baseline Rate-Based e estrutura fundamental.
- [x] **Fase 2**: Política Buffer-Based, Failover Automático e Análise de Eficiência (IQS).
- [ ] **Fase 3**: Política Estatística avançada e correlação Wireshark.

## 📝 Requisitos
- Python 3.12+ (recomendado)
- Bibliotecas: `requests`, `pandas`, `matplotlib`, `numpy`.
