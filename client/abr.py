"""
abr.py — Motor de decisão ABR
Contém as três políticas de seleção de qualidade:
  - BaselinePolicy    (Política 1): Rate-Based com safety factor
  - BufferBasedPolicy (Política 2): Buffer-Based com histerese
  - HeuristicPolicy   (Política 3): EWMA de vazão com penalidade de jitter

Justificativa matemática da Política 3
---------------------------------------
Seja T_n a vazão medida no segmento n e J_n = |d_n - d_{n-1}| a variação
de atraso (jitter bruto). Define-se:

  EWMA de vazão:
    Ŝ_n = α · T_n + (1 − α) · Ŝ_{n-1}        (α = 0,3)

  EWMA de jitter:
    Ĵ_n = β · J_n + (1 − β) · Ĵ_{n-1}        (β = 0,3)

  Vazão efetiva penalizada:
    S_eff = Ŝ_n · max(0, 1 − γ · Ĵ_n / Ŝ_n)   (γ = 1,5)

A política seleciona o maior bitrate r tal que:
    r ≤ S_eff · safety_factor                    (safety_factor = 0,85)

Quando Ĵ_n → 0 (sem jitter), S_eff → Ŝ_n e a política se comporta como
a Baseline suavizada. Quando o jitter cresce proporcionalmente a Ŝ_n,
S_eff decresce linearmente, forçando uma escolha mais conservadora antes
que o buffer seja esgotado.
"""

from __future__ import annotations
from typing import List, Dict, Any


class ABRPolicy:
    """Classe base para políticas ABR."""
    def select_quality(
        self,
        throughput_kbps: float,
        buffer_level: float,
        representations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        raise NotImplementedError


# ──────────────────────────────────────────────────────────────
# Política 1 — Baseline Rate-Based
# ──────────────────────────────────────────────────────────────
class BaselinePolicy(ABRPolicy):
    """
    Política 1 (Rate-Based): seleciona a maior qualidade cujo bitrate
    cabe dentro de throughput × safety_factor.
    """
    def __init__(self, safety_factor: float = 0.8) -> None:
        self.safety_factor = safety_factor

    def select_quality(
        self,
        throughput_kbps: float,
        buffer_level: float,
        representations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        sorted_reprs = sorted(representations, key=lambda x: x["bitrate_kbps"])
        available = throughput_kbps * self.safety_factor
        selected = sorted_reprs[0]
        for rep in sorted_reprs:
            if rep["bitrate_kbps"] <= available:
                selected = rep
            else:
                break
        return selected


# ──────────────────────────────────────────────────────────────
# Política 2 — Buffer-Based com Histerese
# ──────────────────────────────────────────────────────────────
class BufferBasedPolicy(ABRPolicy):
    """
    Política 2 (Buffer-Based / Hysteresis).

    Zonas de decisão (buffer em segundos):
      Panic Zone   : buffer < PANIC_LEVEL      → qualidade mínima imediata
      Safe Zone    : PANIC_LEVEL..COMFORT_LEVEL → mapeamento linear buffer→qualidade
      Comfort Zone : buffer > COMFORT_LEVEL    → qualidade máxima

    Histerese anti-oscilação:
      Upgrade  só ocorre se buffer ≥ threshold(alvo) + HYSTERESIS
      Downgrade só ocorre se buffer ≤ threshold(atual) − HYSTERESIS
      Exceção: Panic Zone ignora histerese (queda sempre imediata)

    Com n=5, PANIC=5s, COMFORT=15s, HYSTERESIS=2s, os limiares ficam:
      index 0 → 5.0 s  | index 1 → 7.5 s  | index 2 → 10.0 s
      index 3 → 12.5 s | index 4 → 15.0 s
    """

    PANIC_LEVEL   = 5.0   # s — abaixo disto, pânico total
    COMFORT_LEVEL = 15.0  # s — acima disto, máxima qualidade garantida
    HYSTERESIS    = 2.0   # s — margem anti-oscilação

    def __init__(self) -> None:
        self.current_index: int = 0

    def _threshold(self, index: int, n: int) -> float:
        """Nível de buffer correspondente ao índice via mapeamento linear."""
        if n <= 1:
            return self.PANIC_LEVEL
        return self.PANIC_LEVEL + index / (n - 1) * (self.COMFORT_LEVEL - self.PANIC_LEVEL)

    def _raw_target(self, buffer_level: float, n: int) -> int:
        """Índice-alvo ideal sem histerese."""
        if buffer_level <= self.PANIC_LEVEL:
            return 0
        if buffer_level >= self.COMFORT_LEVEL:
            return n - 1
        ratio = (buffer_level - self.PANIC_LEVEL) / (self.COMFORT_LEVEL - self.PANIC_LEVEL)
        return int(ratio * (n - 1))

    def select_quality(
        self,
        throughput_kbps: float,
        buffer_level: float,
        representations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        sorted_reprs = sorted(representations, key=lambda x: x["bitrate_kbps"])
        n = len(sorted_reprs)
        self.current_index = min(self.current_index, n - 1)

        # Zona de Pânico — queda imediata, sem histerese
        if buffer_level < self.PANIC_LEVEL:
            if self.current_index != 0:
                print(f"ABR-Buffer PÂNICO! Buffer={buffer_level:.1f}s → qualidade mínima.")
            self.current_index = 0
            return sorted_reprs[0]

        raw = self._raw_target(buffer_level, n)

        if raw > self.current_index:
            needed = self._threshold(raw, n) + self.HYSTERESIS
            if buffer_level >= needed:
                self.current_index = raw
        elif raw < self.current_index:
            needed = self._threshold(self.current_index, n) - self.HYSTERESIS
            if buffer_level <= needed:
                self.current_index = raw

        return sorted_reprs[self.current_index]


# ──────────────────────────────────────────────────────────────
# Política 3 — Heurística EWMA com Penalidade de Jitter
# ──────────────────────────────────────────────────────────────
class HeuristicPolicy(ABRPolicy):
    """
    Política 3 (Heurística / EWMA + Jitter Penalty).

    Mantém estimativas suavizadas via EWMA de:
      - vazão observada (Ŝ)
      - jitter de rede (Ĵ), calculado como |delay_n − delay_{n-1}|

    A decisão de qualidade é baseada numa vazão efetiva penalizada:
      S_eff = Ŝ · max(0, 1 − γ · Ĵ / Ŝ)

    Parâmetros ajustáveis no construtor:
      alpha         — peso EWMA da vazão        (padrão 0,3)
      beta          — peso EWMA do jitter       (padrão 0,3)
      gamma         — coeficiente de penalidade (padrão 1,5)
      safety_factor — margem conservadora final (padrão 0,85)
    """

    def __init__(
        self,
        alpha: float = 0.3,
        beta: float  = 0.3,
        gamma: float = 1.5,
        safety_factor: float = 0.85,
    ) -> None:
        self.alpha = alpha
        self.beta  = beta
        self.gamma = gamma
        self.safety_factor = safety_factor

        # Estado interno
        self._ewma_throughput: float | None = None   # Ŝ_n
        self._ewma_jitter: float = 0.0               # Ĵ_n
        self._last_download_time: float | None = None  # d_{n-1}

        # Expõe as estimativas atuais para o MetricsCollector
        self.current_ewma_throughput: float = 0.0
        self.current_ewma_jitter: float     = 0.0

    # ── API principal ──────────────────────────────────────────

    def update_network_sample(
        self,
        throughput_kbps: float,
        download_time_s: float,
    ) -> None:
        """
        Atualiza as EWMAs de vazão e jitter com a amostra mais recente.
        Deve ser chamado após cada segmento baixado, ANTES de select_quality.

        Parâmetros:
          throughput_kbps  — vazão medida no segmento (kbps)
          download_time_s  — tempo de download do segmento (s)
        """
        # ── Atualiza EWMA de vazão ─────────────────────────────
        if self._ewma_throughput is None:
            self._ewma_throughput = throughput_kbps
        else:
            self._ewma_throughput = (
                self.alpha * throughput_kbps
                + (1.0 - self.alpha) * self._ewma_throughput
            )

        # ── Calcula jitter bruto = |d_n − d_{n-1}| ────────────
        if self._last_download_time is not None:
            raw_jitter = abs(download_time_s - self._last_download_time)
        else:
            raw_jitter = 0.0
        self._last_download_time = download_time_s

        # ── Atualiza EWMA de jitter ────────────────────────────
        self._ewma_jitter = (
            self.beta * raw_jitter
            + (1.0 - self.beta) * self._ewma_jitter
        )

        # Expõe para logging
        self.current_ewma_throughput = self._ewma_throughput
        self.current_ewma_jitter     = self._ewma_jitter * 1000.0  # → ms

    def select_quality(
        self,
        throughput_kbps: float,
        buffer_level: float,
        representations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Seleciona qualidade com base na vazão EWMA penalizada pelo jitter.

        Fallback: se ainda não houver estimativa (primeiros segmentos),
        usa a vazão instantânea com safety_factor conservador.
        """
        sorted_reprs = sorted(representations, key=lambda x: x["bitrate_kbps"])

        # Sem histórico ainda → usa throughput instantâneo conservador
        if self._ewma_throughput is None or self._ewma_throughput <= 0:
            available = throughput_kbps * (self.safety_factor * 0.7)
        else:
            s_hat = self._ewma_throughput
            j_hat = self._ewma_jitter  # em segundos (compatível com Ŝ em kbps·s)

            # Penalidade relativa: γ · Ĵ / Ŝ  (adimensional)
            # Ĵ está em segundos; normalizamos para kbps dividindo pelo
            # tempo de segmento típico (2 s) para converter para kbps equivalente.
            jitter_kbps_equiv = j_hat * s_hat  # variação de "kbps" induzida pelo jitter
            penalty = max(0.0, 1.0 - self.gamma * jitter_kbps_equiv / (s_hat + 1e-9))
            s_eff   = s_hat * penalty
            available = s_eff * self.safety_factor

        selected = sorted_reprs[0]
        for rep in sorted_reprs:
            if rep["bitrate_kbps"] <= available:
                selected = rep
            else:
                break
        return selected

    # ── Propriedades utilitárias ──────────────────────────────

    @property
    def ewma_throughput(self) -> float:
        return self._ewma_throughput if self._ewma_throughput is not None else 0.0

    @property
    def ewma_jitter_ms(self) -> float:
        """Jitter EWMA em milissegundos (para o CSV)."""
        return self._ewma_jitter * 1000.0
