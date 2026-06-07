import time
import sys
import os
import argparse

# Add the current directory to sys.path to allow relative imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from network import NetworkManager
from buffer import BufferManager
from abr import BaselinePolicy, BufferBasedPolicy
from metrics_collector import MetricsCollector

def run_client(num_segments, policy_name):
    manifest_url = "http://137.131.178.229:8080/manifest"
    output_csv = f"../metrics/streaming_metrics_{policy_name}.csv"
    
    # Initialize components
    network = NetworkManager(manifest_url)
    manifest = network.fetch_manifest()
    
    if not manifest:
        print("Failed to fetch manifest. Exiting.")
        return

    buffer = BufferManager(manifest['segment_duration_s'])
    
    # Policy selection logic
    if policy_name == "buffer":
        policy = BufferBasedPolicy()
    else:
        policy = BaselinePolicy(safety_factor=0.8)
        
    metrics = MetricsCollector(os.path.join(os.path.dirname(__file__), output_csv))
    
    # State variables
    # failover_total will be managed by NetworkManager in Maria's task
    last_throughput = 500.0 # Initial guess
    
    print(f"Starting streaming with policy '{policy_name}' from {network.current_server['url']}...")
    print(f"Targeting {num_segments} segments.")

    for i in range(1, num_segments + 1):
        # 1. Decide quality
        current_buffer = buffer.get_level()
        selected_repr = policy.select_quality(last_throughput, current_buffer, manifest['representations'])
        
        # 2. Download segment
        content, download_time, throughput, jitter = network.download_segment(selected_repr['url_path'])
        
        if content is None:
            print(f"\n[{i:02d}] Failed to download segment. Skipping.")
            continue
            
        # 3. Update buffer
        buffer_can_play_before = 1 if buffer.can_play() else 0
        buffer.add_segment()
        
        # 4. Handle metrics
        last_throughput = throughput
        
        # Update terminal status (one line)
        status = f"Seg {i:03d}/{num_segments:03d} | Qualidade: {selected_repr['quality']:5} | Vazão: {throughput:7.2f} kbps | Buffer: {buffer.get_level():5.2f}s "
        print(f"\r{status}", end="", flush=True)

        metric_data = {
            'segment': i,
            'server_id': network.current_server['id'],
            'quality': selected_repr['quality'],
            'bitrate_kbps': selected_repr['bitrate_kbps'],
            'vazão_kbps': throughput,
            'download_time_s': download_time,
            'jitter_network_ms': jitter,
            'jitter_ewma_ms': 0, 
            'buffer_level_s': buffer.get_level(),
            'buffer_can_play': buffer_can_play_before,
            'rebuffer_event': 1 if buffer_can_play_before == 0 and i > 1 else 0,
            'stall_duration_s': 0,
            'failover_total': getattr(network, 'failover_count', 0)
        }
        metrics.log_metric(metric_data)
        
        time.sleep(0.1)

    print(f"\nStreaming finished. Metrics saved to {output_csv}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DASH Adaptive Streaming Client")
    parser.add_argument("-n", "--segments", type=int, default=20, help="Number of segments to download")
    parser.add_argument("-p", "--policy", type=str, choices=["baseline", "buffer"], default="baseline", help="ABR Policy to use")
    
    args = parser.parse_args()
    run_client(args.segments, args.policy)
