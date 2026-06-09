#!/usr/bin/env python3
"""
test_abr.py — Testes unitários e simulação comparativa para BufferBasedPolicy.

Execute com:  python3 test_abr.py
Coloque este arquivo na mesma pasta que abr.py (dentro de client/).
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from abr import BaselinePolicy, BufferBasedPolicy

# ─────────────────────────── Dados de teste ─────────────────────────────────

# As mesmas qualidades do servidor real (tiradas do generate_graphs.py)
REPRS = [
    {'quality': '240p',  'bitrate_kbps': 200,  'url_path': '/seg/240p'},
    {'quality': '360p',  'bitrate_kbps': 400,  'url_path': '/seg/360p'},
    {'quality': '480p',  'bitrate_kbps': 700,  'url_path': '/seg/480p'},
    {'quality': '720p',  'bitrate_kbps': 1500, 'url_path': '/seg/720p'},
    {'quality': '1080p', 'bitrate_kbps': 3000, 'url_path': '/seg/1080p'},
]

# Com n=5, PANIC=5, COMFORT=15, HYSTERESIS=2, os limiares são:
#   threshold: [5.0,  7.5, 10.0, 12.5, 15.0]
#   upgrade:   [  -, 9.5, 12.0, 14.5, 17.0]  (threshold + 2)
#   downgrade: [  -, 5.5,  8.0, 10.5, 13.0]  (threshold - 2)

PASSED = 0
FAILED = 0

def check(name, got, expected):
    global PASSED, FAILED
    if got == expected:
        PASSED += 1
        print(f"  ✅ PASS | {name}")
    else:
        FAILED += 1
        print(f"  ❌ FAIL | {name}")
        print(f"           Esperado: '{expected}'  |  Obtido: '{got}'")


# ─────────────────────────── Testes: Zona de Pânico ─────────────────────────

def test_panic_zone():
    print("\n── [1] Zona de Pânico ──────────────────────────────────────────────")

    # Buffer bem abaixo do pânico → mínima qualidade
    p = BufferBasedPolicy()
    r = p.select_quality(9999, 3.0, REPRS)
    check("Buffer=3.0s → 240p (mínima)", r['quality'], '240p')

    # Buffer exatamente no limite inferior do pânico (< 5.0 ainda é pânico)
    p2 = BufferBasedPolicy()
    r = p2.select_quality(9999, 4.99, REPRS)
    check("Buffer=4.99s → ainda 240p (< 5.0)", r['quality'], '240p')

    # Estava em 1080p, cai no pânico → deve voltar ao mínimo imediatamente (sem histerese)
    p3 = BufferBasedPolicy()
    p3.current_index = 4   # simula que o player já está em 1080p
    r = p3.select_quality(9999, 2.0, REPRS)
    check("Em 1080p, buffer=2.0s → queda imediata para 240p (pânico ignora histerese)", r['quality'], '240p')


# ─────────────────────────── Testes: Zona de Conforto ───────────────────────

def test_comfort_zone():
    print("\n── [2] Zona de Conforto ────────────────────────────────────────────")

    # Partindo de 240p (índice 0), buffer=16s está na comfort zone mas histerese
    # exige buffer >= threshold(4)+2 = 15+2 = 17s para realmente subir.
    p = BufferBasedPolicy()
    r = p.select_quality(100, 16.0, REPRS)
    check("De 240p, buffer=16.0s → ainda 240p (histerese exige 17.0s)", r['quality'], '240p')

    # Com buffer=17.0s a histerese é satisfeita e sobe direto para 1080p
    r = p.select_quality(100, 17.0, REPRS)
    check("De 240p, buffer=17.0s → sobe para 1080p", r['quality'], '1080p')

    # Já em 1080p, buffer ainda no conforto (15.5s) → mantém 1080p
    p2 = BufferBasedPolicy()
    p2.current_index = 4
    r = p2.select_quality(100, 15.5, REPRS)
    check("Em 1080p, buffer=15.5s → mantém 1080p (conforto)", r['quality'], '1080p')

    # Em 1080p, buffer cai para safe zone mas não o suficiente para downgrade.
    # Downgrade de index=4 exige buffer <= threshold(4)-2 = 15-2 = 13.0s.
    p3 = BufferBasedPolicy()
    p3.current_index = 4
    r = p3.select_quality(100, 14.0, REPRS)
    check("Em 1080p, buffer=14.0s → mantém 1080p (14.0 > 13.0 necessário)", r['quality'], '1080p')

    # Com buffer=13.0s a histerese cede e faz o downgrade (raw_target=3 → 720p)
    r2 = p3.select_quality(100, 13.0, REPRS)
    check("Em 1080p, buffer=13.0s → downgrade para 720p", r2['quality'], '720p')


# ─────────────────────────── Testes: Safe Zone ──────────────────────────────

def test_safe_zone():
    print("\n── [3] Safe Zone (mapeamento linear + histerese) ───────────────────")

    # Para subir de 240p para 360p (index 0→1):
    #   threshold(1) = 7.5s, upgrade_needed = 7.5+2 = 9.5s
    p = BufferBasedPolicy()
    r = p.select_quality(100, 9.4, REPRS)
    check("De 240p, buffer=9.4s → ainda 240p (9.4 < 9.5 necessário)", r['quality'], '240p')

    p2 = BufferBasedPolicy()
    r = p2.select_quality(100, 9.5, REPRS)
    check("De 240p, buffer=9.5s → sobe para 360p (histerese exata)", r['quality'], '360p')

    # Para subir de 360p para 480p (index 1→2):
    #   threshold(2) = 10.0s, upgrade_needed = 10.0+2 = 12.0s
    p3 = BufferBasedPolicy()
    p3.current_index = 1  # já em 360p
    r = p3.select_quality(100, 11.9, REPRS)
    check("De 360p, buffer=11.9s → ainda 360p (11.9 < 12.0 necessário)", r['quality'], '360p')

    r2 = p3.select_quality(100, 12.0, REPRS)
    check("De 360p, buffer=12.0s → sobe para 480p", r2['quality'], '480p')

    # Para subir de 480p para 720p (index 2→3):
    #   threshold(3) = 12.5s, upgrade_needed = 12.5+2 = 14.5s
    p4 = BufferBasedPolicy()
    p4.current_index = 2  # já em 480p
    r = p4.select_quality(100, 14.4, REPRS)
    check("De 480p, buffer=14.4s → ainda 480p (14.4 < 14.5 necessário)", r['quality'], '480p')

    r2 = p4.select_quality(100, 14.5, REPRS)
    check("De 480p, buffer=14.5s → sobe para 720p", r2['quality'], '720p')


# ─────────────────────────── Testes: Histerese ──────────────────────────────

def test_hysteresis():
    print("\n── [4] Histerese (evita oscilações) ────────────────────────────────")

    p = BufferBasedPolicy()

    # Simula uma subida gradual até 480p
    p.select_quality(100, 9.5,  REPRS)   # 240p → 360p  (9.5 >= 9.5 ✓)
    p.select_quality(100, 12.0, REPRS)   # 360p → 480p  (12.0 >= 12.0 ✓)
    check("Após subida gradual, chegou em 480p (index=2)", p.current_index, 2)

    # Buffer oscila para 9.5s — raw_target seria 360p, mas downgrade de 480p
    # só acontece se buffer <= threshold(2)-2 = 10.0-2 = 8.0s
    p.select_quality(100, 9.5, REPRS)
    check("Oscilação para 9.5s → mantém 480p (downgrade precisa de <= 8.0s)", p.current_index, 2)

    # Continua caindo para 8.0s → agora downgrade é autorizado
    p.select_quality(100, 8.0, REPRS)
    check("Buffer cai para 8.0s → downgrade para 360p", p.current_index, 1)

    # Buffer se recupera para 11.0s — raw_target seria 480p,
    # mas upgrade de 360p para 480p exige >= 12.0s
    p.select_quality(100, 11.0, REPRS)
    check("Recuperação para 11.0s → ainda 360p (re-upgrade exige >= 12.0s)", p.current_index, 1)

    # Teste de pulo de múltiplos níveis: buffer sobe direto para 17s
    # → deve pular da qualidade atual para 1080p de uma vez
    p.select_quality(100, 17.0, REPRS)
    check("Buffer sobe para 17.0s → pulo para 1080p (índice 4)", p.current_index, 4)


# ─────────────────────────── Simulação comparativa ──────────────────────────

def simulate_trace():
    """
    Simula um trace de buffer com rede instável e compara Policy 1 vs Policy 2.
    O buffer sobe, estabiliza, sofre uma crise e se recupera.
    """
    print("\n── [5] Simulação: trace com rede instável ──────────────────────────")

    # Trace de buffer (s): subida → estável → crise → recuperação
    buffer_trace = [
        2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0,   # subida
        17.5, 16.8, 15.2, 14.0, 13.5, 13.0, 12.8, 12.5,      # estável (leve queda)
        10.0, 8.0, 6.0, 4.5, 3.0,                             # crise
        4.0, 6.0, 8.0, 10.0, 14.0, 16.0, 18.0,               # recuperação
    ]

    # Throughput oscilante (kbps) — vai estressar a Política 1
    throughput_trace = [
        500, 800, 1200, 1800, 2500, 3000, 2800, 3200, 3500,
        2000, 1500, 1000, 1200, 800,  900,  1100, 1300,
        600,  400,  300,  200,  150,
        200,  500,  900,  1400, 2000, 2800, 3500,
    ]

    p1 = BaselinePolicy(safety_factor=0.8)
    p2 = BufferBasedPolicy()

    prev_q1, prev_q2 = None, None
    q1_changes, q2_changes = 0, 0

    print(f"\n  {'Seg':>4}  {'Buffer':>8}  {'Baseline (P1)':>15}  {'Buffer-Based (P2)':>18}")
    print(f"  {'─'*4}  {'─'*8}  {'─'*15}  {'─'*18}")

    for i, (buf, tput) in enumerate(zip(buffer_trace, throughput_trace), 1):
        r1 = p1.select_quality(tput, buf, REPRS)
        r2 = p2.select_quality(tput, buf, REPRS)

        tag1 = " ↕" if prev_q1 and r1['quality'] != prev_q1 else "  "
        tag2 = " ↕" if prev_q2 and r2['quality'] != prev_q2 else "  "

        if prev_q1 and r1['quality'] != prev_q1: q1_changes += 1
        if prev_q2 and r2['quality'] != prev_q2: q2_changes += 1

        print(f"  {i:>4}  {buf:>7.1f}s  {r1['quality']:>13}{tag1}  {r2['quality']:>16}{tag2}")
        prev_q1, prev_q2 = r1['quality'], r2['quality']

    print(f"\n  Trocas de qualidade → Baseline: {q1_changes} | Buffer-Based: {q2_changes}")

    global PASSED, FAILED
    if q2_changes < q1_changes:
        PASSED += 1
        print(f"  ✅ PASS | Buffer-Based foi {q1_changes - q2_changes} troca(s) mais estável que Baseline!")
    else:
        FAILED += 1
        print("  ❌ FAIL | Baseline teve menos (ou igual) trocas neste trace — revise os parâmetros.")


# ─────────────────────────── Execução ───────────────────────────────────────

if __name__ == "__main__":
    print("=" * 62)
    print("  Testes — BufferBasedPolicy | Bernardo Gomes Rodrigues")
    print("=" * 62)

    test_panic_zone()
    test_comfort_zone()
    test_safe_zone()
    test_hysteresis()
    simulate_trace()

    print(f"\n{'=' * 62}")
    print(f"  Resultado final: {PASSED} passaram  |  {FAILED} falharam")
    print(f"{'=' * 62}")

    sys.exit(0 if FAILED == 0 else 1)