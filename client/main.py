import time
import sys
import os

# Add the current directory to sys.path to allow relative imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from network import NetworkManager
from buffer import BufferManager
from abr import BaselinePolicy
from metrics_collector import MetricsCollector

def run_client(num_segments=20):
    manifest_url = "http://137.131.178.229:8080/manifest"
    output_csv = "../metrics/streaming_metrics.csv"
    
    # Initialize components
    network = NetworkManager(manifest_url)
    manifest = network.fetch_manifest()
    
    if not manifest:
        print("Failed to fetch manifest. Exiting.")
        return

    buffer = BufferManager(manifest['segment_duration_s'])
    policy = BaselinePolicy(safety_factor=0.8)
    metrics = MetricsCollector(os.path.join(os.path.dirname(__file__), output_csv))
    
    # State variables
    failover_total = 0
    last_throughput = 500.0 # Initial guess for the first segment
    
    print(f"Starting streaming from {network.current_server['url']}...")
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
            'jitter_ewma_ms': 0, # To be implemented in Phase 3
            'buffer_level_s': buffer.get_level(),
            'buffer_can_play': buffer_can_play_before,
            'rebuffer_event': 1 if buffer_can_play_before == 0 and i > 1 else 0,
            'stall_duration_s': 0, # Simplified for now
            'failover_total': failover_total
        }
        metrics.log_metric(metric_data)
        
        time.sleep(0.1)

    print(f"\nStreaming finished. Metrics saved to {output_csv}")

if __name__ == "__main__":
    segments = 20
    if len(sys.argv) > 1:
        segments = int(sys.argv[1])
    run_client(segments)
