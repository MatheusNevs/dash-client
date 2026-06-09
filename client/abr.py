class ABRPolicy:
    """Base class for ABR policies."""
    def select_quality(self, throughput_kbps, buffer_level, representations):
        raise NotImplementedError


class BaselinePolicy(ABRPolicy):
    """Rate-Based ABR policy (Policy 1)."""

    def __init__(self, safety_factor=0.8):
        self.safety_factor = safety_factor

    def select_quality(self, throughput_kbps, buffer_level, representations):
        """
        Selects the highest quality with bitrate < throughput * safety_factor.
        'representations' is a list of dicts with 'quality' and 'bitrate_kbps'.
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
    Buffer-Based ABR policy with hysteresis (Policy 2).
    Implementado por Bernardo Gomes Rodrigues.

    Zonas de decisão (buffer em segundos):
      - Panic Zone    (< PANIC_LEVEL)             : queda imediata para qualidade mínima.
      - Safe Zone     (PANIC_LEVEL..COMFORT_LEVEL) : mapeamento linear buffer → qualidade.
      - Comfort Zone  (>= COMFORT_LEVEL)           : qualidade máxima, ignora oscilações.

    Histerese (evita oscilações rápidas entre qualidades vizinhas):
      - Upgrade:   só ocorre se buffer >= threshold_do_alvo    + HYSTERESIS
      - Downgrade: só ocorre se buffer <= threshold_do_atual   - HYSTERESIS
      - Exceção:   Panic Zone ignora histerese — queda é sempre imediata.

    Com 5 qualidades, PANIC=5s, COMFORT=15s, HYSTERESIS=2s, os limiares ficam:
      index 0 = 5.0s | index 1 = 7.5s | index 2 = 10.0s | index 3 = 12.5s | index 4 = 15.0s
    O que gera as seguintes faixas de estabilidade:
      Para entrar em 360p: precisa de 9.5s. Para sair de 360p: cai abaixo de 5.5s.
      Para entrar em 480p: precisa de 12.0s. Para sair de 480p: cai abaixo de 8.0s.
      Para entrar em 720p: precisa de 14.5s. Para sair de 720p: cai abaixo de 10.5s.
      Para entrar em 1080p: precisa de 17.0s. Para sair de 1080p: cai abaixo de 13.0s.
    """

    PANIC_LEVEL   = 5.0   # s — abaixo disto, pânico total
    COMFORT_LEVEL = 15.0  # s — acima disto, máxima qualidade garantida
    HYSTERESIS    = 2.0   # s — margem anti-oscilação

    def __init__(self):
        self.current_index = 0  # índice da qualidade em uso (estado da histerese)

    # ─────────────────────────── helpers ────────────────────────────────────

    def _threshold(self, index: int, n: int) -> float:
        """
        Retorna o nível de buffer (s) que corresponde ao índice `index`
        via mapeamento linear entre PANIC_LEVEL e COMFORT_LEVEL.

        Exemplo com n=5:
          index 0 → 5.0s  |  index 1 → 7.5s  |  index 2 → 10.0s
          index 3 → 12.5s |  index 4 → 15.0s
        """
        if n <= 1:
            return self.PANIC_LEVEL
        return self.PANIC_LEVEL + (index / (n - 1)) * (self.COMFORT_LEVEL - self.PANIC_LEVEL)

    def _raw_target(self, buffer_level: float, n: int) -> int:
        """
        Índice-alvo 'ideal' calculado apenas pelo nível de buffer, sem histerese.
        É o ponto de partida antes de aplicar a lógica de estabilização.
        """
        if buffer_level < self.PANIC_LEVEL:
            return 0
        if buffer_level >= self.COMFORT_LEVEL:
            return n - 1
        ratio = (buffer_level - self.PANIC_LEVEL) / (self.COMFORT_LEVEL - self.PANIC_LEVEL)
        return int(ratio * (n - 1))

    # ─────────────────────────── decisão principal ──────────────────────────

    def select_quality(self, throughput_kbps, buffer_level, representations):
        """
        Seleciona a qualidade com base no nível de buffer com histerese.

        Args:
            throughput_kbps : Vazão medida — ignorada nesta política.
            buffer_level    : Segundos de conteúdo disponível no buffer.
            representations : Lista de dicts com 'bitrate_kbps', 'quality' e 'url_path'.

        Returns:
            Dict da representação selecionada.
        """
        sorted_reprs = sorted(representations, key=lambda x: x['bitrate_kbps'])
        n = len(sorted_reprs)

        # Proteção: garante índice válido caso o manifesto mude entre segmentos
        self.current_index = min(self.current_index, n - 1)

        # ── Zona de Pânico: queda imediata, sem histerese ──────────────────
        if buffer_level < self.PANIC_LEVEL:
            if self.current_index != 0:
                print(f"\n[ABR-Buffer] ⚠ PÂNICO! Buffer={buffer_level:.1f}s → qualidade mínima.")
            self.current_index = 0
            return sorted_reprs[0]

        # ── Calcula o alvo "puro" baseado só no buffer ─────────────────────
        raw = self._raw_target(buffer_level, n)

        if raw > self.current_index:
            # Quer subir: confirma se buffer está HYSTERESIS acima do limiar do alvo
            needed = self._threshold(raw, n) + self.HYSTERESIS
            if buffer_level >= needed:
                self.current_index = raw
            # caso contrário: aguarda mais buffer antes de autorizar o upgrade

        elif raw < self.current_index:
            # Quer descer: confirma se buffer caiu HYSTERESIS abaixo do limiar atual
            needed = self._threshold(self.current_index, n) - self.HYSTERESIS
            if buffer_level <= needed:
                self.current_index = raw
            # caso contrário: mantém qualidade atual — a histerese está segurando

        return sorted_reprs[self.current_index]