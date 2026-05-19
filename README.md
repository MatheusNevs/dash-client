# TR2 - Projeto Final: Streaming Adaptativo com ABR

Este repositório contém a implementação de um cliente de streaming de vídeo adaptativo (Adaptive Bitrate - ABR) em Python, desenvolvido para a disciplina de Teleinformática e Redes 2 (UnB).

## 🚀 Visão Geral
O sistema simula o comportamento de um player de vídeo moderno (estilo DASH/HLS). O cliente baixa segmentos de vídeo via HTTP, mede o desempenho da rede em tempo real e decide a qualidade do próximo segmento para evitar travamentos (rebuffering) e maximizar a experiência do usuário.

## 📁 Estrutura do Código (`client/`)
- **`main.py`**: Orquestrador principal. Gerencia o loop de download e a integração dos componentes.
- **`network.py`**: Camada de rede. Responsável por requisições HTTP, medição de vazão (kbps) e verificação de saúde dos servidores.
- **`abr.py`**: Motor de decisão. Contém as políticas ABR (atualmente implementada: *Rate-Based Baseline*).
- **`buffer.py`**: Modelo de buffer. Simula o consumo de vídeo e estima quantos segundos de reprodução restam.
- **`metrics_collector.py`**: Abstração para log. Garante que todas as métricas sejam salvas no formato CSV exigido.

## 🛠️ Como Executar

1. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Inicie o streaming:**
   ```bash
   # Executa o cliente baixando 20 segmentos (padrão)
   python3 client/main.py [numero_de_segmentos]
   ```

3. **Gere os gráficos de desempenho:**
   ```bash
   python3 graphs/generate_graphs.py
   ```
   Os gráficos serão salvos na pasta `graphs/` como `vazao_vs_qualidade.png` e `nivel_buffer.png`.

## 📊 Métricas Coletadas
O sistema gera um arquivo `metrics/streaming_metrics.csv` contendo:
- Vazão medida por segmento.
- Qualidade selecionada e seu bitrate.
- Nível do buffer no momento da decisão.
- Eventos de rebuffering e stalls.
- Estatísticas de failover.

## 🗺️ Roadmap de Desenvolvimento
- [x] **Fase 1**: Baseline Rate-Based e estrutura fundamental.
- [ ] **Fase 2**: Implementação de Política 2 (Buffer-Based/Hysteresis) e Failover Automático.
- [ ] **Fase 3**: Política 3 (Estatística/EWMA) e correlação com tráfego Wireshark.

## 📝 Requisitos
- Python 3.6+
- Bibliotecas: `requests`, `pandas`, `matplotlib`.
