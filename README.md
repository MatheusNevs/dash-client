# ABR Video Streaming Client & Simulator

Um cliente e simulador de streaming de vídeo adaptativo (Adaptive Bitrate - ABR) em Python, desenvolvido para análise, comparação e otimização de algoritmos de adaptação de taxa de transmissão (estilo DASH/HLS) em diferentes cenários de rede.

## 🚀 Visão Geral

O sistema simula o comportamento de um player de vídeo moderno que baixa segmentos de vídeo via HTTP, monitora as condições de rede em tempo real (vazão, latência e jitter) e seleciona dinamicamente a qualidade do próximo segmento para otimizar a experiência do usuário (QoE), minimizando travamentos (*rebuffering*) e variações bruscas de qualidade.

Conta com uma interface gráfica interativa (GUI Desktop), um motor de simulação matemática orientado a traces (*Trace-Driven Black-Box Simulator*), suporte a *failover* de rede e múltiplos algoritmos de ABR.

---

## ✨ Principais Funcionalidades

- **Algoritmos ABR Implementados:**
  - `Baseline Policy (Rate-Based)`: Seleção baseada puramente na vazão instantânea da rede.
  - `Buffer-Based Policy`: Seleção baseada no nível de ocupação do buffer de reprodução via histerese.
  - `Heuristic Policy (Estatística Avançada)`: Política híbrida que utiliza média móvel exponencialmente ponderada (EWMA) para vazão e jitter, aplicando fatores de punição para evitar oscilações em redes instáveis.

- **Simulador de Rastreamento (Trace-Driven Simulator):**
  - Motor "caixa preta" capaz de aplicar identicamente os mesmos perfis de variação de rede a múltiplas políticas simultaneamente, garantindo comparações reproduzíveis e isentas de ruído de concorrência real.

- **Interface Gráfica Interativa (GUI Desktop):**
  - Desenvolvida com `CustomTkinter` em estilo *Neon Dark*.
  - Exibição de gráficos em tempo real e sobreposição comparativa de curvas de desempenho no mesmo eixo.
  - Painel para testes de **Failover de Rede** com injeção de quedas via regras de `iptables` (autenticação segura `sudo`).

- **Gerenciamento Dinâmico de Buffer:**
  - Modelo assíncrono de consumo e reprodução de vídeo.
  - Retenção máxima limitada (ex: 30 segundos) para simular restrições de memória de players reais.

- **Failover Automático & Resiliência:**
  - Redirecionamento automático de requisições para servidores de backup em caso de indisponibilidade ou timeout.
  - Sincronização visual de eventos de failover nos gráficos através de marcadores verticais tracejados.

- **Coleta de Métricas & Analytics:**
  - Exportação de dados detalhados em formato CSV (vazão, jitter, nível de buffer, qualidade selecionada, trocas de qualidade, eventos de rebuffering e contagem de failovers).

---

## 📁 Estrutura do Projeto (`client/`)

```text
client/
├── main.py                 # Ponto de entrada do cliente (CLI e GUI)
├── gui.py                  # Interface gráfica Desktop com gráficos em tempo real
├── simulator.py            # Motor de simulação (tempo real e trace-driven)
├── network.py              # Gerenciador de rede, timeouts, latência, jitter e failover
├── abr.py                  # Implementação das políticas de ABR (Baseline, Buffer, Heuristic)
├── buffer.py               # Modelo de buffer assíncrono de reprodução e limitação
└── metrics_collector.py    # Coletor e exportador de estatísticas em CSV
```

---

## 🛠️ Instalação e Execução

### Pré-requisitos
- Python 3.12 ou superior

### Instalação das Dependências

```bash
pip install -r requirements.txt
```

### 1. Interface Gráfica (GUI)

Inicie o dashboard interativo:

```bash
python client/main.py --gui
```

### 2. Linha de Comando (CLI)

Executar uma política específica:

```bash
python client/main.py -n 30 -p heuristic
```

Executar **todas as políticas simultaneamente** sob a mesma variação de rede:

```bash
python client/main.py -n 30 -p all_simultaneous
```

---

## 📊 Analytics e Coleta de Dados

Os resultados das simulações são exportados para a pasta `metrics/` em formato CSV. Os logs capturam métricas cruciais de Qualidade de Experiência (QoE):

- **Bitrate selecionado (`bitrate_kbps`)**
- **Vazão medida (`vazão_kbps`)**
- **Jitter estimado (`jitter_ewma_ms`)**
- **Nível de ocupação do buffer (`buffer_level_s`)**
- **Eventos de travamento (`rebuffer_event`, `stall_duration_s`)**
- **Ocorrências de failover (`failover_total`)**

Na interface gráfica ou através dos scripts de visualização, as ocorrências de failover são destacadas como **linhas verticais tracejadas em vermelho**, perfeitamente sincronizadas com o momento de oscilação ou timeout na rede.

---

## 📄 Licença

Este projeto é disponibilizado sob a licença [MIT](LICENSE).
