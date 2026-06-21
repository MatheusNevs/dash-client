"""
test_abr.py — Testes unitários para as políticas ABR.

Cobre:
  - Seleção de qualidade em condições normais / escassez / fartura de banda
  - Zonas de Pânico, Conforto e Histerese da Política 2
  - Comportamento EWMA e penalidade de jitter da Política 3
  - Fallback conservador nos primeiros segmentos da Política 3
"""

import sys
import os
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), '../client'))
from abr import BaselinePolicy, BufferBasedPolicy, HeuristicPolicy


# Representações fictícias para os testes
REPRESENTATIONS = [
    {"quality": "240p",  "bitrate_kbps": 200,  "url_path": "/240p/seg.mp4"},
    {"quality": "360p",  "bitrate_kbps": 400,  "url_path": "/360p/seg.mp4"},
    {"quality": "480p",  "bitrate_kbps": 600,  "url_path": "/480p/seg.mp4"},
    {"quality": "720p",  "bitrate_kbps": 900, "url_path": "/720p/seg.mp4"},
    {"quality": "1080p", "bitrate_kbps": 1200, "url_path": "/1080p/seg.mp4"},
]


class TestBaselinePolicy(unittest.TestCase):
    def setUp(self):
        self.p = BaselinePolicy(safety_factor=0.92)

    def test_selects_best_fitting_quality(self):
        # 1000 kbps * 0.92 = 920 → cabe 720p (900), não 1080p (1200)
        rep = self.p.select_quality(1000, 10, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "720p")

    def test_falls_back_to_minimum_when_low_bandwidth(self):
        rep = self.p.select_quality(100, 10, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "240p")

    def test_selects_max_when_high_bandwidth(self):
        rep = self.p.select_quality(10000, 10, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "1080p")

    def test_safety_factor_applied(self):
        # 1300 * 0.92 = 1196 → cabe 720p (900), não 1080p (1200)
        rep = self.p.select_quality(1300, 10, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "720p")


class TestBufferBasedPolicy(unittest.TestCase):
    def setUp(self):
        self.p = BufferBasedPolicy()

    def test_panic_zone_returns_minimum(self):
        rep = self.p.select_quality(5000, 2, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "240p")

    def test_comfort_zone_returns_maximum(self):
        self.p.current_index = 4
        rep = self.p.select_quality(5000, 20, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "1080p")

    def test_hysteresis_prevents_immediate_upgrade(self):
        self.p.current_index = 0
        # buffer=10s → raw_target ~2, mas sem HYSTERESIS suficiente → sem upgrade
        rep = self.p.select_quality(5000, 10, REPRESENTATIONS)
        quality_index = next(i for i, r in enumerate(
            sorted(REPRESENTATIONS, key=lambda x: x["bitrate_kbps"])
        ) if r["quality"] == rep["quality"])
        self.assertLessEqual(quality_index, 2)

    def test_no_downgrade_with_hysteresis_buffer(self):
        self.p.current_index = 4
        # buffer=14s → abaixo do COMFORT, mas histerese impede downgrade imediato
        rep = self.p.select_quality(5000, 14, REPRESENTATIONS)
        q = rep["quality"]
        self.assertIn(q, ["720p", "1080p"])

    def test_panic_ignores_hysteresis(self):
        self.p.current_index = 4  # estava na melhor qualidade
        rep = self.p.select_quality(5000, 3, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "240p")


class TestHeuristicPolicy(unittest.TestCase):
    def setUp(self):
        self.p = HeuristicPolicy(alpha=0.3, beta=0.3, gamma=1.5, safety_factor=0.92)

    def test_initial_segment_conservative_fallback(self):
        # Sem histórico → fallback ultra-conservador (safety * 0.7)
        rep = self.p.select_quality(1000, 10, REPRESENTATIONS)
        # 1000 * 0.92 * 0.7 = 644 → cabe 480p (600)? Sim: 644 < 900 → 480p
        self.assertEqual(rep["quality"], "480p")

    def test_ewma_updates_on_network_sample(self):
        self.p.update_network_sample(2000, 0.5)
        self.p.update_network_sample(2000, 0.5)
        # após 2 amostras com throughput=2000, EWMA deve estar próximo de 2000
        self.assertGreater(self.p.ewma_throughput, 1000)

    def test_high_jitter_forces_lower_quality(self):
        # Alimenta EWMA com throughput alto mas jitter variável
        self.p.update_network_sample(3000, 0.5)
        self.p.update_network_sample(3000, 2.5)   # jitter = 2s
        self.p.update_network_sample(3000, 0.5)   # jitter = 2s

        rep_high_jitter = self.p.select_quality(3000, 10, REPRESENTATIONS)

        # Cria política sem jitter para comparação
        p_clean = HeuristicPolicy(alpha=0.3, beta=0.3, gamma=1.5, safety_factor=0.92)
        p_clean.update_network_sample(3000, 0.5)
        p_clean.update_network_sample(3000, 0.5)
        p_clean.update_network_sample(3000, 0.5)
        rep_no_jitter = p_clean.select_quality(3000, 10, REPRESENTATIONS)

        # Com jitter, a qualidade deve ser menor ou igual à sem jitter
        self.assertLessEqual(
            rep_high_jitter["bitrate_kbps"],
            rep_no_jitter["bitrate_kbps"],
        )

    def test_zero_jitter_matches_baseline_behavior(self):
        # Sem jitter, política heurística deve ser conservadora mas funcional
        for _ in range(5):
            self.p.update_network_sample(3000, 1.0)  # delay constante → jitter=0
        rep = self.p.select_quality(3000, 10, REPRESENTATIONS)
        self.assertGreaterEqual(rep["bitrate_kbps"], 600)   # pelo menos 480p

    def test_ewma_jitter_ms_property(self):
        self.p.update_network_sample(1000, 1.0)
        self.p.update_network_sample(1000, 1.5)
        jitter_ms = self.p.ewma_jitter_ms
        self.assertGreater(jitter_ms, 0)

    def test_very_high_bandwidth_selects_1080p(self):
        for _ in range(10):
            self.p.update_network_sample(10000, 0.5)  # alto e estável
        rep = self.p.select_quality(10000, 10, REPRESENTATIONS)
        self.assertEqual(rep["quality"], "1080p")


if __name__ == "__main__":
    unittest.main(verbosity=2)
