"""
Algoritmos de Adaptação de Taxa de Transmissão (Adaptive Bitrate - ABR).

Este módulo contém as implementações das políticas de ABR para seleção da qualidade do próximo
segmento de vídeo em um player DASH/HLS:
  1. BaselinePolicy: Baseada puramente na vazão instantânea da rede (Rate-Based).
  2. BufferBasedPolicy: Baseada no nível de ocupação do buffer de reprodução com histerese.
  3. HeuristicPolicy: Política híbrida estatística com suavização EWMA para vazão e jitter.
"""


class ABRPolicy:
    """Classe base abstrata para políticas de adaptação de bitrate (ABR)."""

    def select_quality(self, throughput_kbps, buffer_level, representations, **kwargs):
        """
        Seleciona a qualidade do próximo segmento a ser baixado.

        Args:
            throughput_kbps (float): Vazão medida no último segmento em kbps.
            buffer_level (float): Nível atual do buffer de reprodução em segundos.
            representations (list[dict]): Lista de dicionários das qualidades disponíveis no manifesto.

        Returns:
            dict: Dicionário contendo a representação selecionada (ex: 'quality', 'bitrate_kbps').
        """
        raise NotImplementedError


class BaselinePolicy(ABRPolicy):
    """
    Política ABR Baseada em Vazão (Rate-Based Baseline).

    Seleciona a maior qualidade de vídeo cuja taxa de transmissão (bitrate) seja menor ou igual
    à vazão disponível multiplicada por um fator de segurança (safety factor).
    """

    def __init__(self, safety_factor=0.92):
        """
        Inicializa a política Baseline.

        Args:
            safety_factor (float): Margem de segurança aplicada sobre a vazão medida (padrão: 0.92 ou 92%).
        """
        self.safety_factor = safety_factor

    def select_quality(self, throughput_kbps, buffer_level, representations, **kwargs):
        """
        Seleciona a qualidade com base na vazão instantânea.

        Args:
            throughput_kbps (float): Vazão estimada em kbps.
            buffer_level (float): Nível de buffer em segundos.
            representations (list[dict]): Qualidades de vídeo disponíveis.

        Returns:
            dict: Representação de vídeo selecionada.
        """
        sorted_reprs = sorted(representations, key=lambda x: x['bitrate_kbps'])
        selected = sorted_reprs[0]
        available_bandwidth = throughput_kbps * self.safety_factor
        for rep in sorted_reprs:
            if rep['bitrate_kbps'] <= available_bandwidth:
                selected = rep
            else:
                break
        return selected


class BufferBasedPolicy(ABRPolicy):
    """
    Política ABR Baseada em Buffer com Histerese (Buffer-Based Policy).

    Mapeia a ocupação do buffer de reprodução diretamente para os níveis de qualidade disponíveis.
    Utiliza zonas de decisão e margem de histerese para evitar oscilações de qualidade entre segmentos vizinhos.

    Zonas de decisão (buffer em segundos):
      - Panic Zone    (< PANIC_LEVEL)              : Queda imediata para a qualidade mínima.
      - Safe Zone     (PANIC_LEVEL..COMFORT_LEVEL) : Mapeamento linear buffer → qualidade.
      - Comfort Zone  (>= COMFORT_LEVEL)            : Qualidade máxima garantida.

    Histerese (evita oscilações rápidas):
      - Upgrade:   Só ocorre se buffer >= limiar_alvo + HYSTERESIS.
      - Downgrade: Só ocorre se buffer <= limiar_atual - HYSTERESIS.
      - Exceção:   Panic Zone ignora a histerese (queda é sempre instantânea para evitar stall).
    """

    PANIC_LEVEL   = 5.0   # Segundos — abaixo disto, ativa a zona de pânico
    COMFORT_LEVEL = 15.0  # Segundos — acima disto, seleciona a máxima qualidade
    HYSTERESIS    = 2.0   # Segundos — margem anti-oscilação

    def __init__(self):
        """Inicializa o estado da política baseada em buffer."""
        self.current_index = 0  # Índice da qualidade em uso (preserva estado para a histerese)

    def _threshold(self, index: int, n: int) -> float:
        """
        Calcula o nível de buffer (s) correspondente ao índice da qualidade através
        de mapeamento linear entre PANIC_LEVEL e COMFORT_LEVEL.

        Args:
            index (int): Índice da qualidade desejada (0 até n-1).
            n (int): Número total de qualidades disponíveis.

        Returns:
            float: Limiar de buffer em segundos.
        """
        if n <= 1:
            return self.PANIC_LEVEL
        return self.PANIC_LEVEL + (index / (n - 1)) * (self.COMFORT_LEVEL - self.PANIC_LEVEL)

    def _raw_target(self, buffer_level: float, n: int) -> int:
        """
        Calcula o índice de qualidade ideal com base exclusivamente no nível do buffer,
        sem aplicar a margem de histerese.

        Args:
            buffer_level (float): Nível de buffer atual em segundos.
            n (int): Número total de qualidades disponíveis.

        Returns:
            int: Índice da qualidade alvo preliminar.
        """
        if buffer_level < self.PANIC_LEVEL:
            return 0
        if buffer_level >= self.COMFORT_LEVEL:
            return n - 1
        ratio = (buffer_level - self.PANIC_LEVEL) / (self.COMFORT_LEVEL - self.PANIC_LEVEL)
        return int(ratio * (n - 1))

    def select_quality(self, throughput_kbps, buffer_level, representations, **kwargs):
        """
        Seleciona a qualidade com base no nível do buffer e nas regras de histerese.

        Args:
            throughput_kbps (float): Vazão medida (ignorada por esta política).
            buffer_level (float): Segundos de conteúdo disponíveis no buffer.
            representations (list[dict]): Qualidades de vídeo disponíveis.

        Returns:
            dict: Representação de vídeo selecionada.
        """
        sorted_reprs = sorted(representations, key=lambda x: x['bitrate_kbps'])
        n = len(sorted_reprs)

        # Garante índice válido caso o número de representações mude
        self.current_index = min(self.current_index, n - 1)

        # ── Zona de Pânico: Queda imediata para a qualidade mínima ──────────────────
        if buffer_level < self.PANIC_LEVEL:
            if self.current_index != 0:
                print(f"\n[ABR-Buffer] ⚠ PÂNICO! Buffer={buffer_level:.1f}s → qualidade mínima.")
            self.current_index = 0
            return sorted_reprs[0]

        # ── Calcula o índice alvo baseado puramente no buffer ─────────────────────
        raw = self._raw_target(buffer_level, n)

        if raw > self.current_index:
            # Solicitação de Upgrade: exige que o buffer esteja HYSTERESIS acima do limiar do alvo
            needed = self._threshold(raw, n) + self.HYSTERESIS
            if buffer_level >= needed:
                self.current_index = raw

        elif raw < self.current_index:
            # Solicitação de Downgrade: exige que o buffer esteja HYSTERESIS abaixo do limiar atual
            needed = self._threshold(self.current_index, n) - self.HYSTERESIS
            if buffer_level <= needed:
                self.current_index = raw

        return sorted_reprs[self.current_index]


class HeuristicPolicy(ABRPolicy):
    """
    Política ABR Heurística (EWMA + Penalização por Jitter + Saúde de Buffer).

    Combina estimativas estatísticas suavizadas via Média Móvel Exponencialmente Ponderada (EWMA)
    para a vazão de rede e o jitter, aplicando penalidades proporcionais à instabilidade da rede
    e atenuando penalidades quando o buffer se encontra saudável.
    """

    def __init__(
        self,
        alpha: float = 0.3,
        beta: float  = 0.3,
        gamma: float = 1.5,
        safety_factor: float = 0.92,
    ) -> None:
        """
        Inicializa a política Heurística.

        Args:
            alpha (float): Fator de suavização EWMA para a vazão de rede (0 a 1).
            beta (float): Fator de suavização EWMA para o jitter de rede (0 a 1).
            gamma (float): Fator de ponderação/sensibilidade à variação de jitter.
            safety_factor (float): Fator de segurança base sobre a vazão estimada.
        """
        self.alpha = alpha
        self.beta  = beta
        self.gamma = gamma
        self.safety_factor = safety_factor

        self._ewma_throughput = None
        self._ewma_jitter = 0.0
        self._last_download_time = None

        self.COMFORT_BUFFER = 15.0 

    def update_network_sample(self, throughput_kbps: float, download_time_s: float) -> None:
        """
        Atualiza as estimativas estatísticas de EWMA da vazão e do jitter com uma nova amostra.

        Args:
            throughput_kbps (float): Vazão medida no download do segmento atual em kbps.
            download_time_s (float): Tempo de download do segmento atual em segundos.
        """
        # Atualização da EWMA da vazão
        if self._ewma_throughput is None:
            self._ewma_throughput = throughput_kbps
        else:
            self._ewma_throughput = self.alpha * throughput_kbps + (1.0 - self.alpha) * self._ewma_throughput

        # Atualização do jitter bruto e da EWMA do jitter
        if self._last_download_time is not None:
            raw_jitter = abs(download_time_s - self._last_download_time)
        else:
            raw_jitter = 0.0
        self._last_download_time = download_time_s

        self._ewma_jitter = self.beta * raw_jitter + (1.0 - self.beta) * self._ewma_jitter

    def select_quality(self, throughput_kbps, buffer_level, representations, **kwargs):
        """
        Seleciona a qualidade otimizada combinando vazão EWMA, penalidade por jitter e nível de buffer.

        Args:
            throughput_kbps (float): Vazão instantânea em kbps.
            buffer_level (float): Nível de buffer atual em segundos.
            representations (list[dict]): Qualidades de vídeo disponíveis.

        Returns:
            dict: Representação de vídeo selecionada.
        """
        sorted_reprs = sorted(representations, key=lambda x: x["bitrate_kbps"])
        if self._ewma_throughput is None or self._ewma_throughput <= 0:
            available = throughput_kbps * (self.safety_factor * 0.7)
        else:
            s_hat = self._ewma_throughput
            j_hat = self._ewma_jitter
            jitter_kbps_equiv = j_hat * s_hat
            raw_penalty = max(0.0, 1.0 - self.gamma * jitter_kbps_equiv / (s_hat + 1e-9))

            # Calcula a saúde relativa do buffer comparada com a meta COMFORT_BUFFER (15s)
            buffer_health = min(1.0, max(0.0, buffer_level / self.COMFORT_BUFFER))
            buffer_confiability = 0.95

            # Buffer saudável compensa parcialmente a penalidade imposta por jitter instável
            penalty = raw_penalty + (1.0 - raw_penalty) * buffer_health * buffer_confiability

            s_eff = s_hat * penalty           
            available = s_eff * self.safety_factor

        # Prevenção total de travamento (stall): se o buffer for crítico (<2s), força qualidade mínima
        if buffer_level < 2.0:
            return sorted_reprs[0]

        selected = sorted_reprs[0]
        for rep in sorted_reprs:
            if rep["bitrate_kbps"] <= available:
                selected = rep
            else:
                break
        return selected

    @property
    def ewma_throughput(self) -> float:
        """Retorna a vazão suavizada EWMA atual em kbps."""
        return self._ewma_throughput if self._ewma_throughput is not None else 0.0

    @property
    def ewma_jitter_ms(self) -> float:
        """Retorna a estimativa de jitter EWMA suavizado em milissegundos."""
        return self._ewma_jitter * 1000.0