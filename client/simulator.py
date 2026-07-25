"""
Motor de Simulação de Streaming ABR (Real-Time e Trace-Driven).

Este módulo gerencia a execução das simulações de streaming de vídeo. Ele suporta:
  - Simulação individual de políticas em tempo real (_run_single).
  - Simulação simultânea (Trace-Driven / Batch) de múltiplas políticas sob a mesma variação
    de rede (_run_simultaneous_batch).
"""

import time
import sys
import os
import argparse
import concurrent.futures

# Adiciona o diretório atual ao sys.path para garantir a resolução correta de importações relativas
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from network import NetworkManager
from buffer import BufferManager
from abr import BaselinePolicy, BufferBasedPolicy, HeuristicPolicy
from metrics_collector import MetricsCollector


def print_status(i, num_segments, server_id, quality, throughput, buffer_level):
    """
    Formata e exibe a linha de status dinâmica no terminal para execuções de uma única política.

    Args:
        i (int): Número do segmento atual.
        num_segments (int): Total de segmentos da simulação.
        server_id (str): ID do servidor ativo (ex: 'A', 'B').
        quality (str): Qualidade selecionada para o segmento (ex: '1080p').
        throughput (float): Vazão medida em kbps.
        buffer_level (float): Nível atual do buffer em segundos.
    """
    if server_id == 'A':
        server_str = f"\033[92m{server_id}\033[0m"
    elif server_id == 'B':
        server_str = f"\033[93m{server_id}\033[0m"
    else:
        server_str = server_id
        
    if quality == '1080p': q_str = f"\033[92m{quality:5}\033[0m"
    elif quality == '720p': q_str = f"\033[96m{quality:5}\033[0m"
    elif quality == '480p': q_str = f"\033[93m{quality:5}\033[0m"
    else: q_str = f"\033[91m{quality:5}\033[0m"

    if throughput >= 1100: t_str = f"\033[92m{throughput:7.2f}\033[0m"
    elif throughput >= 600: t_str = f"\033[93m{throughput:7.2f}\033[0m"
    else: t_str = f"\033[91m{throughput:7.2f}\033[0m"

    if buffer_level >= 10: b_str = f"\033[92m{buffer_level:5.2f}\033[0m"
    elif buffer_level >= 4: b_str = f"\033[93m{buffer_level:5.2f}\033[0m"
    else: b_str = f"\033[91m{buffer_level:5.2f}\033[0m"

    status = f"Seg {i:03d}/{num_segments:03d} | Servidor: {server_str} | Qualidade: {q_str} | Vazão: {t_str} kbps | Buffer: {b_str}s "
    print(f"\r{status:<100}", end="", flush=True)


def print_batch_status(i, num_segments, server_id, throughput, reprs, buffers):
    """
    Formata e exibe a linha de status dinâmica no terminal para simulações simultâneas.

    Args:
        i (int): Número do segmento atual.
        num_segments (int): Total de segmentos da simulação.
        server_id (str): ID do servidor ativo.
        throughput (float): Vazão da rede em kbps.
        reprs (dict): Dicionário mapeando nome da política para a qualidade escolhida.
        buffers (dict): Dicionário mapeando nome da política para o nível do buffer.
    """
    if server_id == 'A':
        server_str = f"\033[92m{server_id}\033[0m"
    elif server_id == 'B':
        server_str = f"\033[93m{server_id}\033[0m"
    else:
        server_str = server_id

    if throughput >= 1100: t_str = f"\033[92m{throughput:7.2f}\033[0m"
    elif throughput >= 600: t_str = f"\033[93m{throughput:7.2f}\033[0m"
    else: t_str = f"\033[91m{throughput:7.2f}\033[0m"

    pol_strs = []
    for p_name in ["baseline", "buffer", "heuristic"]:
        if p_name in reprs and p_name in buffers:
            q = reprs[p_name]
            b = buffers[p_name]
            if q == '1080p': q_str = f"\033[92m{q:5}\033[0m"
            elif q == '720p': q_str = f"\033[96m{q:5}\033[0m"
            elif q == '480p': q_str = f"\033[93m{q:5}\033[0m"
            else: q_str = f"\033[91m{q:5}\033[0m"
            
            if b >= 10: b_str = f"\033[92m{b:5.2f}\033[0m"
            elif b >= 4: b_str = f"\033[93m{b:5.2f}\033[0m"
            else: b_str = f"\033[91m{b:5.2f}\033[0m"
            
            pol_strs.append(f"{p_name[:2].upper()}[{q_str} {b_str}s]")
            
    policies_str = " | ".join(pol_strs)
    status = f"Seg {i:03d}/{num_segments:03d} | Serv: {server_str} | Vazão: {t_str} kbps | {policies_str} "
    print(f"\r{status:<120}", end="", flush=True)


def run_simulation(num_segments, policy_mode, gui_params=None, update_callback=None):
    """
    Ponto de entrada do motor de simulação. Roteia para simulação individual ou lote simultâneo.

    Args:
        num_segments (int): Número total de segmentos a baixar.
        policy_mode (str): Nome da política ('baseline', 'buffer', 'heuristic', 'all_simultaneous').
        gui_params (dict | None): Parâmetros customizados vindos da GUI.
        update_callback (callable | None): Callback para atualização da interface em tempo real.
    """
    if policy_mode == "all_simultaneous":
        _run_simultaneous_batch(num_segments, gui_params, update_callback)
    else:
        _run_single(num_segments, policy_mode, gui_params, update_callback)


def _run_single(num_segments, policy_name, gui_params=None, update_callback=None):
    """
    Executa a simulação de streaming para uma única política de ABR em tempo real.

    Args:
        num_segments (int): Número total de segmentos.
        policy_name (str): Nome da política a ser executada.
        gui_params (dict | None): Parâmetros configurados via GUI.
        update_callback (callable | None): Callback de atualização visual.
    """
    manifest_url = "http://137.131.178.229:8080/manifest"
    output_csv = f"../metrics/streaming_metrics_{policy_name}.csv"
    
    network = NetworkManager(manifest_url)
    manifest = network.fetch_manifest()
    
    if not manifest:
        print(f"[{policy_name}] Falha ao baixar o manifesto.")
        return

    buffer = BufferManager(manifest['segment_duration_s'])
    
    # Instancia a política selecionada
    if policy_name == "buffer":
        policy = BufferBasedPolicy()
    elif policy_name == "heuristic":
        if gui_params:
            policy = HeuristicPolicy(
                alpha=gui_params.get("alpha", 0.3),
                beta=gui_params.get("beta", 0.3),
                gamma=gui_params.get("gamma", 1.5),
                safety_factor=gui_params.get("safety_factor", 0.92)
            )
        else:
            policy = HeuristicPolicy()
    else:
        sf = gui_params.get("safety_factor", 0.92) if gui_params else 0.92
        policy = BaselinePolicy(safety_factor=sf)
        
    metrics = MetricsCollector(os.path.join(os.path.dirname(__file__), output_csv))
    
    # Inicia com a menor vazão (Cold Start conservador)
    min_bitrate = manifest['representations'][0]['bitrate_kbps']
    last_throughput = min_bitrate 
    jitter_ewma = 0.0
    alpha = 0.125  # Fator EWMA estilo TCP
    
    print(f"Iniciando streaming com a política '{policy_name}' no servidor {network.current_server['url']}...")
    print(f"Meta: {num_segments} segmentos.")

    # Executor em thread para download assíncrono mantendo a GUI/Terminal responsivos
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    for i in range(1, num_segments + 1):
        # 1. Decide a qualidade com base no estado atual
        current_buffer = buffer.get_level()
        selected_repr = policy.select_quality(last_throughput, current_buffer, manifest['representations'], jitter_ewma=jitter_ewma)
        
        # 2. Inicia o download em segundo plano
        stall_start = None
        future = executor.submit(network.download_segment, selected_repr['url_path'])
        
        # 3. Atualiza o status a cada 100ms durante o download
        while not future.done():
            level = buffer.get_level()
            if level <= 0 and stall_start is None:
                stall_start = time.perf_counter()
            
            print_status(i, num_segments, network.current_server['id'], selected_repr['quality'], last_throughput, level)
            time.sleep(0.1)

        # 4. Download concluído: extrai métricas
        content, download_time, throughput, jitter = future.result()
        
        if isinstance(policy, HeuristicPolicy):
            policy.update_network_sample(throughput, download_time)
        
        stall_duration = 0
        if stall_start is not None:
            stall_duration = time.perf_counter() - stall_start

        if content is None:
            print(f"\n[{i:02d}] Falha ao baixar o segmento. Pando para o próximo.")
            continue
            
        # 5. Adiciona o segmento baixado ao buffer
        buffer_can_play_before = 1 if buffer.can_play() else 0
        buffer.add_segment()
        last_throughput = throughput
        
        # Atualiza o Jitter EWMA
        if i == 1:
            jitter_ewma = jitter
        else:
            jitter_ewma = (1 - alpha) * jitter_ewma + alpha * jitter
        
        print_status(i, num_segments, network.current_server['id'], selected_repr['quality'], throughput, buffer.get_level())

        # 6. Registra as métricas no CSV
        metric_data = {
            'segment': i,
            'server_id': network.current_server['id'],
            'quality': selected_repr['quality'],
            'bitrate_kbps': selected_repr['bitrate_kbps'],
            'vazão_kbps': throughput,
            'download_time_s': download_time,
            'jitter_network_ms': jitter,
            'jitter_ewma_ms': jitter_ewma, 
            'buffer_level_s': buffer.get_level(),
            'buffer_can_play': buffer_can_play_before,
            'rebuffer_event': 1 if stall_duration > 0 else 0,
            'stall_duration_s': stall_duration,
            'failover_total': getattr(network, 'failover_count', 0)
        }
        metrics.log_metric(metric_data)
        
        if update_callback:
            update_callback(policy_name, metric_data)

    executor.shutdown()
    buffer.stop()
    print(f"\nStreaming finalizado. Métricas salvas em {output_csv}")


def _run_simultaneous_batch(num_segments, gui_params, update_callback):
    """
    Executa a simulação simultânea (Trace-Driven) para todas as políticas.
    Baixa um segmento real de alta qualidade para medir a vazão da rede e aplica
    matematicamente esse mesmo perfil a cada uma das políticas para comparação 100% isenta de viés.

    Args:
        num_segments (int): Número total de segmentos.
        gui_params (dict | None): Parâmetros customizados da GUI.
        update_callback (callable | None): Callback para atualização dos gráficos da GUI.
    """
    manifest_url = "http://137.131.178.229:8080/manifest"
    network = NetworkManager(manifest_url)
    manifest = network.fetch_manifest()
    if not manifest: return
        
    segment_duration = manifest['segment_duration_s']
    sf = gui_params.get("safety_factor", 0.92) if gui_params else 0.92
    policies = {
        "baseline": BaselinePolicy(safety_factor=sf),
        "buffer": BufferBasedPolicy(),
        "heuristic": HeuristicPolicy(
            alpha=gui_params.get("alpha", 0.3) if gui_params else 0.3,
            beta=gui_params.get("beta", 0.3) if gui_params else 0.3,
            gamma=gui_params.get("gamma", 1.5) if gui_params else 1.5,
            safety_factor=sf
        )
    }
    
    class SimulatedBufferManager:
        """
        Gerenciador sintético de buffer para a simulação matemática simultânea.

        Simula de forma discreta (calculada por equações) o consumo e o acúmulo de buffer 
        de reprodução sem a necessidade de threads em segundo plano.
        """

        def __init__(self, segment_duration: float) -> None:
            """
            Inicializa o buffer sintético.

            Args:
                segment_duration (float): Duração individual de cada segmento em segundos.
            """
            self.segment_duration = segment_duration
            self.buffer_level = 0.0
            self.is_playing = False

        def simulate_download(self, download_time_s: float) -> float:
            """
            Simula o consumo de buffer durante o tempo decorrido no download de um segmento.

            Args:
                download_time_s (float): Tempo necessário para baixar o segmento (em segundos).

            Returns:
                float: Duração do evento de congelamento/stall (em segundos), se houver.
            """
            stall_duration = 0.0
            if self.is_playing:
                self.buffer_level -= download_time_s
                if self.buffer_level < 0:
                    stall_duration = abs(self.buffer_level)
                    self.buffer_level = 0.0
                    self.is_playing = False  # Ocorre re-buffering (Stall)
            else:
                stall_duration = download_time_s
            return stall_duration

        def add_segment(self) -> float:
            """
            Adiciona a duração de um segmento baixado ao buffer sintético.

            Returns:
                float: Novo nível de buffer em segundos.
            """
            self.buffer_level += self.segment_duration
            if self.buffer_level > 30.0:
                self.buffer_level = 30.0  # Limite máximo de retenção (30s)
            if not self.is_playing and self.buffer_level >= self.segment_duration:
                self.is_playing = True   # Retoma a reprodução ao atingir o limiar mínimo
            return self.buffer_level

        def get_level(self) -> float:
            """Retorna o nível atual do buffer sintético em segundos."""
            return self.buffer_level

        def can_play(self) -> bool:
            """Verifica se há conteúdo disponível no buffer para reprodução."""
            return self.buffer_level > 0

    states = {}
    min_bitrate = manifest['representations'][0]['bitrate_kbps']
    
    for p_name in policies:
        output_csv = f"../metrics/streaming_metrics_{p_name}.csv"
        states[p_name] = {
            "buffer": SimulatedBufferManager(segment_duration),
            "last_throughput": min_bitrate,
            "jitter_ewma": 0.0,
            "last_sim_download_time": None,
            "metrics": MetricsCollector(os.path.join(os.path.dirname(__file__), output_csv))
        }
    
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    
    print(f"Iniciando simulação lote simultânea no servidor {network.current_server['url']}...")
    print(f"Meta: {num_segments} segmentos.")
    
    for i in range(1, num_segments + 1):
        decisions = {}
        for p_name, policy in policies.items():
            state = states[p_name]
            p_buffer = state["buffer"]
            selected_repr = policy.select_quality(state["last_throughput"], p_buffer.get_level(), manifest['representations'], jitter_ewma=state["jitter_ewma"])
            decisions[p_name] = selected_repr

        # Utiliza a maior representação para garantir um download representativo e aferir a vazão real da rede
        max_repr = manifest['representations'][-1]
        future = executor.submit(network.download_segment, max_repr['url_path'])
        
        while not future.done():
            reprs_for_print = {p: decisions[p]['quality'] for p in policies}
            buffers_for_print = {p: states[p]["buffer"].get_level() for p in policies}
            current_server_id = network.current_server['id'] if network.current_server else '?'
            print_batch_status(i, num_segments, current_server_id, states['baseline']['last_throughput'], reprs_for_print, buffers_for_print)
            time.sleep(0.1)
            
        content, real_download_time, real_throughput, real_jitter = future.result()
        if content is None: 
            print(f"\n[{i:02d}] Falha ao baixar o segmento. Pulando.")
            continue
            
        for p_name, policy in policies.items():
            state = states[p_name]
            p_buffer = state["buffer"]
            selected_repr = decisions[p_name]
            
            sim_size_kb = selected_repr['bitrate_kbps'] * segment_duration
            sim_download_time = sim_size_kb / real_throughput if real_throughput > 0 else 0
            
            stall_duration = p_buffer.simulate_download(sim_download_time)
            buffer_can_play_before = 1 if p_buffer.can_play() else 0
            p_buffer.add_segment()
            state["last_throughput"] = real_throughput
            
            sim_jitter = 0.0
            if state["last_sim_download_time"] is not None:
                sim_jitter = abs(sim_download_time - state["last_sim_download_time"]) * 1000.0
            state["last_sim_download_time"] = sim_download_time
            
            alpha_jitter = 0.125
            if i == 1: state["jitter_ewma"] = sim_jitter
            else: state["jitter_ewma"] = (1 - alpha_jitter) * state["jitter_ewma"] + alpha_jitter * sim_jitter
                
            if isinstance(policy, HeuristicPolicy):
                policy.update_network_sample(real_throughput, sim_download_time)
                
            metric_data = {
                'segment': i, 'server_id': network.current_server['id'],
                'quality': selected_repr['quality'], 'bitrate_kbps': selected_repr['bitrate_kbps'],
                'vazão_kbps': real_throughput, 'download_time_s': sim_download_time,
                'jitter_network_ms': sim_jitter, 'jitter_ewma_ms': state["jitter_ewma"], 
                'buffer_level_s': p_buffer.get_level(), 'buffer_can_play': buffer_can_play_before,
                'rebuffer_event': 1 if stall_duration > 0 else 0, 'stall_duration_s': stall_duration,
                'failover_total': getattr(network, 'failover_count', 0)
            }
            if update_callback: update_callback(p_name, metric_data)
            state["metrics"].log_metric(metric_data)
            
        reprs_for_print = {p: decisions[p]['quality'] for p in policies}
        buffers_for_print = {p: states[p]["buffer"].get_level() for p in policies}
        print_batch_status(i, num_segments, network.current_server['id'], real_throughput, reprs_for_print, buffers_for_print)

    executor.shutdown()
    print(f"\n\nSimulação simultânea finalizada. Métricas salvas na pasta metrics/.")

