import time
import sys
import os
import argparse
import concurrent.futures

# Add the current directory to sys.path to allow relative imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from network import NetworkManager
from buffer import BufferManager
from abr import BaselinePolicy, BufferBasedPolicy
from metrics_collector import MetricsCollector

def print_status(i, num_segments, server_id, quality, throughput, buffer_level):
    """Helper to format and print the dynamic status line."""
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
    print(f"\r{status}", end="", flush=True)

def run_client(num_segments, policy_name):
    manifest_url = "http://137.131.178.229:8080/manifest"
    output_csv = f"../metrics/streaming_metrics_{policy_name}.csv"
    
    network = NetworkManager(manifest_url)
    manifest = network.fetch_manifest()
    
    if not manifest:
        print("Failed to fetch manifest. Exiting.")
        return

    buffer = BufferManager(manifest['segment_duration_s'])
    
    if policy_name == "buffer":
        policy = BufferBasedPolicy()
    else:
        policy = BaselinePolicy(safety_factor=0.8)
        
    metrics = MetricsCollector(os.path.join(os.path.dirname(__file__), output_csv))
    last_throughput = 500.0 
    jitter_ewma = 0.0
    alpha = 0.125 # Standard TCP-like EWMA alpha
    
    print(f"Starting streaming with policy '{policy_name}' from {network.current_server['url']}...")
    print(f"Targeting {num_segments} segments.")

    # Use a thread pool to download asynchronously so we can update the UI
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    for i in range(1, num_segments + 1):
        # 1. Decide quality based on current state
        current_buffer = buffer.get_level()
        selected_repr = policy.select_quality(last_throughput, current_buffer, manifest['representations'])
        
        # 2. Start download in background
        stall_start = None
        future = executor.submit(network.download_segment, selected_repr['url_path'])
        
        # 3. Update terminal EVERY 0.1s while waiting for download
        # Track stall duration if buffer hits zero
        while not future.done():
            level = buffer.get_level()
            if level <= 0 and stall_start is None:
                stall_start = time.perf_counter()
            
            print_status(i, num_segments, network.current_server['id'], selected_repr['quality'], last_throughput, level)
            time.sleep(0.1)

        # 4. Download finished, get results
        content, download_time, throughput, jitter = future.result()
        
        stall_duration = 0
        if stall_start is not None:
            stall_duration = time.perf_counter() - stall_start

        if content is None:
            print(f"\n[{i:02d}] Failed to download segment. Skipping.")
            continue
            
        # 5. Update buffer with new segment
        buffer_can_play_before = 1 if buffer.can_play() else 0
        buffer.add_segment()
        last_throughput = throughput
        
        # Update Jitter EWMA
        if i == 1:
            jitter_ewma = jitter
        else:
            jitter_ewma = (1 - alpha) * jitter_ewma + alpha * jitter
        
        # Final print for this segment with the updated buffer/throughput
        print_status(i, num_segments, network.current_server['id'], selected_repr['quality'], throughput, buffer.get_level())

        # 6. Handle metrics
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

    executor.shutdown()
    buffer.stop()
    print(f"\nStreaming finished. Metrics saved to {output_csv}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DASH Adaptive Streaming Client")
    parser.add_argument("-n", "--segments", type=int, default=20, help="Number of segments to download")
    parser.add_argument("-p", "--policy", type=str, choices=["baseline", "buffer", "all"], default="baseline", help="ABR Policy to use")
    parser.add_argument("-g", "--generate", action="store_true", help="Automatically generate graphs after finishing")
    
    args = parser.parse_args()
    
    if args.policy == "all":
        policies = ["baseline", "buffer"]
        print(f"Executing batch run for all policies: {policies}")
        for p in policies:
            print(f"\n" + "="*50)
            print(f"RUNNING POLICY: {p}")
            print("="*50)
            run_client(args.segments, p)
    else:
        run_client(args.segments, args.policy)

    if args.generate:
        print("\nGenerating comparison graphs...")
        try:
            import subprocess
            graph_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../graphs/generate_graphs.py")
            subprocess.run(["python3", graph_script])
        except Exception as e:
            print(f"Could not auto-generate graphs: {e}")
