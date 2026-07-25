"""
Módulo de Testes Unitários para as Políticas de ABR.

Este arquivo contém a suíte de testes unitários para validar a lógica de adaptação de bitrate:
  - BaselinePolicy: Escolha adequada com base na margem de segurança e vazão instantânea.
  - BufferBasedPolicy: Validação das zonas de Pânico, Conforto e regras de Histerese.
  - HeuristicPolicy: Suavização estatística EWMA, resposta a instabilidade de jitter e conservadorismo.
"""

import sys
import os
import unittest

# Adiciona o diretório client ao sys.path para importação das políticas
sys.path.append(os.path.join(os.path.dirname(__file__), '../client'))
from abr import BaselinePolicy, BufferBasedPolicy, HeuristicPolicy


# Representações fictícias de vídeo para os testes unitários
REPRESENTATIONS = [
    {"quality": "240p",  "bitrate_kbps": 200,  "url_path": "/240p/seg.mp4"},
    {"quality": "360p",  "bitrate_kbps": 400,  "url_path": "/360p/seg.mp4"},
    {"quality": "480p",  "bitrate_kbps": 600,  "url_path": "/480p/seg.mp4"},
    {"quality": "720p",  "bitrate_kbps": 900,  "url_path": "/720p/seg.mp4"},
    {"quality": "1080p", "bitrate_kbps": 1200, "url_path": "/1080p/seg.mp4"},
]


class TestBaselinePolicy(unittest.TestCase):
    """Suíte de testes para a política Baseline (Rate-Based)."""

    def setUp(self):
        self.p = BaselinePolicy(safety_factor=0.92)

    def test_selects_best_fitting_quality(self):
        """Testa se a política seleciona a maior qualidade suportada dentro da vazão disponível."""
        # 1000 kbps * 0.92 = 920 → suporta 720p (900 kbps), não 1080p (1200 kbps)
        rep = self.p.select_quality(1000, 10, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "720p")

    def test_falls_back_to_minimum_when_low_bandwidth(self):
        """Testa o fallback para qualidade mínima em redes de baixa velocidade."""
        rep = self.p.select_quality(100, 10, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "240p")

    def test_selects_max_when_high_bandwidth(self):
        """Testa a escolha de qualidade máxima quando há alta vazão disponível."""
        rep = self.p.select_quality(10000, 10, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "1080p")

    def test_safety_factor_applied(self):
        """Testa a correta aplicação da margem de segurança de vazão."""
        # 1300 * 0.92 = 1196 → suporta 720p (900), mas não 1080p (1200)
        rep = self.p.select_quality(1300, 10, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "720p")


class TestBufferBasedPolicy(unittest.TestCase):
    """Suíte de testes para a política Buffer-Based com Histerese."""

    def setUp(self):
        self.p = BufferBasedPolicy()

    def test_panic_zone_returns_minimum(self):
        """Testa se o buffer abaixo do limiar de pânico força a qualidade mínima."""
        rep = self.p.select_quality(5000, 2, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "240p")

    def test_comfort_zone_returns_maximum(self):
        """Testa se a ocupação do buffer na zona de conforto garante a qualidade máxima."""
        self.p.current_index = 4
        rep = self.p.select_quality(5000, 20, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "1080p")

    def test_hysteresis_prevents_immediate_upgrade(self):
        """Testa se a regra de histerese impede upgrades prematuros sem buffer suficiente."""
        self.p.current_index = 0
        rep = self.p.select_quality(5000, 10, REPRESENTATIONS)
        quality_index = next(i for i, r in enumerate(
            sorted(REPRESENTATIONS, key=lambda x: x["bitrate_kbps"])
        ) if r["quality"] == rep["quality"])
        self.assertLessEqual(quality_index, 2)

    def test_no_downgrade_with_hysteresis_buffer(self):
        """Testa se a histerese evita downgrades desnecessários sob pequenas flutuações de buffer."""
        self.p.current_index = 4
        rep = self.p.select_quality(5000, 14, REPRESENTATIONS)
        q = rep["quality"]
        self.assertIn(q, ["720p", "1080p"])

    def test_panic_ignores_hysteresis(self):
        """Testa se a zona de pânico ignora a histerese e reduz a qualidade imediatamente."""
        self.p.current_index = 4
        rep = self.p.select_quality(5000, 3, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "240p")


class TestHeuristicPolicy(unittest.TestCase):
    """Suíte de testes para a política Heurística (EWMA + Jitter Penalty)."""

    def setUp(self):
        self.p = HeuristicPolicy(alpha=0.3, beta=0.3, gamma=1.5, safety_factor=0.92)

    def test_initial_segment_conservative_fallback(self):
        """Testa o comportamento conservador no primeiro segmento sem histórico de rede."""
        rep = self.p.select_quality(1000, 10, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "480p")

    def test_ewma_updates_on_network_sample(self):
        """Testa a atualização correta da média móvel (EWMA) da vazão."""
        self.p.update_network_sample(2000, 0.5)
        self.p.update_network_sample(2000, 0.5)
        self.assertGreater(self.p.ewma_throughput, 1000)

    def test_high_jitter_forces_lower_quality(self):
        """Testa se um alto nível de jitter reduz conservadoramente a qualidade selecionada."""
        self.p.update_network_sample(3000, 0.5)
        self.p.update_network_sample(3000, 2.5)   # Jitter elevado
        self.p.update_network_sample(3000, 0.5)   # Jitter elevado

        rep_high_jitter = self.p.select_quality(3000, 10, REPRESENTATIONS)

        p_clean = HeuristicPolicy(alpha=0.3, beta=0.3, gamma=1.5, safety_factor=0.92)
        p_clean.update_network_sample(3000, 0.5)
        p_clean.update_network_sample(3000, 0.5)
        p_clean.update_network_sample(3000, 0.5)
        rep_no_jitter = p_clean.select_quality(3000, 10, REPRESENTATIONS)

        self.assertLessEqual(
            rep_high_jitter["bitrate_kbps"],
            rep_no_jitter["bitrate_kbps"],
        )

    def test_zero_jitter_matches_baseline_behavior(self):
        """Testa o comportamento sob jitter nulo/estável."""
        for _ in range(5):
            self.p.update_network_sample(3000, 1.0)
        rep = self.p.select_quality(3000, 10, REPRESENTATIONS)
        self.assertGreaterEqual(rep["bitrate_kbps"], 600)

    def test_ewma_jitter_ms_property(self):
        """Testa a propriedade que retorna o jitter EWMA em milissegundos."""
        self.p.update_network_sample(1000, 1.0)
        self.p.update_network_sample(1000, 1.5)
        jitter_ms = self.p.ewma_jitter_ms
        self.assertGreater(jitter_ms, 0)

    def test_very_high_bandwidth_selects_1080p(self):
        """Testa se uma rede estável de altíssima velocidade seleciona 1080p."""
        for _ in range(10):
            self.p.update_network_sample(10000, 0.5)
        rep = self.p.select_quality(10000, 10, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "1080p")


if __name__ == "__main__":
    unittest.main(verbosity=2)

