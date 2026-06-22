# TR2 - Projeto Final: Streaming Adaptativo com ABR

Este repositório contém a implementação de um cliente de streaming de vídeo adaptativo (Adaptive Bitrate - ABR) em Python, desenvolvido para a disciplina de Teleinformática e Redes 2 (UnB).

## 🚀 Visão Geral
O sistema simula o comportamento de um player de vídeo moderno (estilo DASH/HLS). O cliente baixa segmentos de vídeo via HTTP, mede o desempenho da rede em tempo real e decide a qualidade do próximo segmento para garantir a continuidade da reprodução e maximizar a qualidade da imagem.

## ✨ Novidades da Fase 3
- **Política Heurística:** Uma nova política híbrida que utiliza média móvel exponencialmente ponderada (EWMA) para Vazão e Jitter, penalizando escolhas arriscadas baseadas na instabilidade da rede.
- **Simulador de Rastreamento Matemático (Trace-Driven):** O backend agora atua como uma "caixa preta" capaz de injetar a exata mesma vazão capturada em múltiplas políticas simultaneamente para uma comparação 100% justa e livre de concorrência real.
- **Dashboard GUI Interativo:** Nova interface gráfica Desktop (CustomTkinter) com plotagem de gráficos em tempo real, suporte a múltiplas linhas comparativas no mesmo gráfico, marcadores de eventos de rede (Failover), e configuração de parâmetros das heurísticas.
- **Limitação Dinâmica de Buffer:** O buffer agora é estritamente limitado a um máximo de 30 segundos de retenção, simulando com precisão o comportamento real de limite de memória (*memory limit*).

## 📁 Estrutura do Código (`client/`)
- **`main.py`**: Ponto de entrada e roteador do cliente (CLI/GUI).
- **`gui.py`**: Interface gráfica Desktop com dashboard interativo e gráficos em tempo real usando Matplotlib.
- **`simulator.py`**: Motor "Caixa Preta" que orquestra a lógica de streaming. Executa simulações matemáticas puras para execuções simultâneas ou em tempo real.
- **`network.py`**: Gerenciador de rede com suporte a Failover Automático, cálculo de latência e Jitter.
- **`abr.py`**: Implementação das políticas:
  - `BaselinePolicy`: Baseada puramente na vazão instantânea.
  - `BufferBasedPolicy`: Baseada no nível de ocupação do buffer (Histerese).
  - `HeuristicPolicy`: Algoritmo estatístico que considera Jitter EWMA e fator de punição/segurança.
- **`buffer.py`**: Modelo de buffer de consumo de vídeo que lida de forma assíncrona com reprodução, limitação (30s) e re-buffering.
- **`metrics_collector.py`**: Coletor de dados estatísticos exportados para CSV.

## 🛠️ Como Executar

### Interface Gráfica (Recomendado)
1. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Inicie o Dashboard:**
   ```bash
   python client/main.py --gui
   ```

### Linha de Comando (CLI)
   ```bash
   # Rodar uma política específica
   python client/main.py -n 30 -p heuristic

   # Rodar TODAS as políticas simultaneamente submetidas à mesma variação de rede
   python client/main.py -n 30 -p all_simultaneous
   ```

## 📊 Gráficos e Analytics
Os logs em `metrics/` são gerados para cada simulação e contêm todos os dados como `vazão_kbps`, `jitter_ewma_ms`, `buffer_level_s`, e **`failover_total`**. 
- No modo **Interface Gráfica**, as ocorrências de failover são detectadas dinamicamente e desenhadas diretamente como **linhas verticais vermelhas tracejadas** cruzando ambos os eixos dos gráficos de forma perfeitamente sincronizada com o instante em que a rede apresentou timeout!

## 🗺️ Roadmap de Desenvolvimento
- [x] **Fase 1**: Baseline Rate-Based e estrutura fundamental.
- [x] **Fase 2**: Política Buffer-Based, Failover Automático e Análise de Eficiência (IQS).
- [x] **Fase 3**: Política Heurística (Estatística avançada), Dashboard GUI, Trace-Driven Simulator e Correlação.

## 📝 Requisitos
- Python 3.12+ (recomendado)
- Bibliotecas: `requests`, `pandas`, `matplotlib`, `numpy`, `customtkinter`.
