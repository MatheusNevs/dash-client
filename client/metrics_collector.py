import csv
import os
from datetime import datetime

class MetricsCollector:
    """Collects and saves streaming metrics to a CSV file."""
    
    def __init__(self, output_path):
        self.output_path = output_path
        self.fields = [
            'segment', 'timestamp', 'server_id', 'quality', 'bitrate_kbps',
            'vazão_kbps', 'download_time_s', 'jitter_network_ms', 'jitter_ewma_ms',
            'buffer_level_s', 'buffer_can_play', 'rebuffer_event', 'stall_duration_s',
            'failover_total'
        ]
        self._initialize_csv()

    def _initialize_csv(self):
        """Creates the CSV file and writes the header."""
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        with open(self.output_path, mode='w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fields)
            writer.writeheader()

    def log_metric(self, data):
        """Appends a row of data to the CSV."""
        # Ensure all fields are present
        log_entry = {field: data.get(field, 0) for field in self.fields}
        log_entry['timestamp'] = datetime.now().isoformat()
        
        with open(self.output_path, mode='a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.fields)
            writer.writerow(log_entry)
