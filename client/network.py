import requests
import time
import json

class NetworkManager:
    """Handles HTTP requests and network metrics."""
    
    def __init__(self, manifest_url):
        self.manifest_url = manifest_url
        self.session = requests.Session()
        self.current_server = None
        self.manifest = None

    def fetch_manifest(self):
        """Downloads and parses the manifest JSON."""
        try:
            response = self.session.get(self.manifest_url, timeout=5)
            response.raise_for_status()
            self.manifest = response.json()
            # Set primary server based on priority
            servers = sorted(self.manifest['servers'], key=lambda x: x['priority'])
            self.current_server = servers[0]
            return self.manifest
        except Exception as e:
            print(f"Error fetching manifest: {e}")
            return None

    def download_segment(self, quality_path):
        """
        Downloads a video segment and measures throughput and jitter.
        Returns (content, download_time, throughput_kbps, jitter_ms)
        """
        if not self.current_server:
            return None, 0, 0, 0

        url = f"{self.current_server['url']}{quality_path}"
        
        try:
            start_time = time.perf_counter()
            response = self.session.get(url, timeout=10)
            end_time = time.perf_counter()
            
            response.raise_for_status()
            content = response.content
            download_time = end_time - start_time
            
            # Throughput calculation: (bytes * 8) / (1000 * time) -> kbps
            bytes_received = len(content)
            throughput_kbps = (bytes_received * 8) / (1000 * download_time) if download_time > 0 else 0
            
            # For now, jitter is 0 as we are downloading the whole segment at once.
            # Real jitter would require chunked download or server-side timing.
            jitter_ms = 0 
            
            return content, download_time, throughput_kbps, jitter_ms
        except Exception as e:
            print(f"Error downloading segment: {e}")
            return None, 0, 0, 0

    def check_health(self, server_url):
        """Checks if a server is healthy via GET /health."""
        try:
            response = self.session.get(f"{server_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False
