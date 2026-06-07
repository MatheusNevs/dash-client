import requests
import time
import json

class NetworkManager:
    """Handles HTTP requests, network metrics, and automatic failover."""
    
    def __init__(self, manifest_url):
        self.manifest_url = manifest_url
        self.session = requests.Session()
        self.all_servers = []
        self.current_server = None
        self.manifest = None
        self.failover_count = 0

    def fetch_manifest(self):
        """Downloads and parses the manifest JSON."""
        try:
            response = self.session.get(self.manifest_url, timeout=5)
            response.raise_for_status()
            self.manifest = response.json()
            
            # Sort servers by priority
            self.all_servers = sorted(self.manifest['servers'], key=lambda x: x['priority'])
            self.current_server = self.all_servers[0]
            
            return self.manifest
        except Exception as e:
            print(f"\n[Network] Error fetching manifest: {e}")
            return None

    def try_failover(self):
        """
        Attempts to switch to a fallback server.
        TODO (Maria): 
        1. Percorrer self.all_servers procurando o próximo servidor.
        2. Realizar Health Check (self.check_health).
        3. Se OK, medir latência e atualizar self.current_server.
        4. Incrementar self.failover_count.
        """
        print(f"\n[Network] Failover triggered! Switching from {self.current_server['id']}...")
        
        # Increment failover counter
        self.failover_count += 1

        # Store current index of server to help switch servers ( A -> B or B -> A)
        current_index = self.all_servers.index(self.current_server)
        total_servers = len(self.all_servers)

        # Loop through the list looking for the next server available
        for i in range (1, total_servers):
            next_index = (current_index + i) % total_servers
            candidato = self.all_servers[next_index]
            
            print(f"    [Failover] Checking integrity of backup server ({candidato['id']})...")
            
            # Health Check
            if self.check_health(candidato['url']):
                self.current_server = candidato
                print(f"    [Failover] Sucess! Route redirected to server {candidato['id']}.")
                return True
                
        print("    [Critical Error] No backup server is responding to the network!")
        return False

    def download_segment(self, quality_path):
        """
        Downloads a video segment and measures throughput.
        If it fails, calls try_failover().
        """
        if not self.current_server:
            return None, 0, 0, 0

        url = f"{self.current_server['url']}{quality_path}"
        
        try:
            start_time = time.perf_counter()
            # Timeout can be reduced to detect failure faster
            response = self.session.get(url, timeout=5) 
            end_time = time.perf_counter()
            
            response.raise_for_status()
            content = response.content
            download_time = end_time - start_time
            
            throughput_kbps = (len(content) * 8) / (1000 * download_time) if download_time > 0 else 0
            
            return content, download_time, throughput_kbps, 0
        except Exception as e:
            print(f"\n[Network] Download failed: {e}")
            
            if self.try_failover():
                # Try to download again, using new server available
                return self.download_segment(quality_path)
            return None, 0, 0, 0

    def check_health(self, server_url):
        """Checks if a server is healthy via GET /health."""
        try:
            start_time = time.perf_counter()
            response = self.session.get(f"{server_url}/health", timeout=2)
            end_time = time.perf_counter()
            
            if response.status_code == 200:
                latency_ms = (end_time - start_time) * 1000
                
                # Alert in case route is low or has noise (latency > 500 ms)
                if latency_ms > 500:
                    print(f"    [Attention] Healthy server, but latency is high: {latency_ms:.2f} ms")
                    
                return True
            return False
        except:
            return False
