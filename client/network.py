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
            
            # Sanitize server IDs (e.g. 'srv-B' to 'B') to match the expected CSV format
            for server in self.manifest['servers']:
                if server['id'].startswith('srv-'):
                    server['id'] = server['id'].replace('srv-', '')

            # Sort servers by priority
            self.all_servers = sorted(self.manifest['servers'], key=lambda x: x['priority'])
            self.current_server = self.all_servers[0]
            
            return self.manifest
        except Exception:
            return None

    def try_failover(self):
        """
        Attempts to switch to a fallback server.
        """
        # Increment failover counter
        self.failover_count += 1

        # Store current index of server to help switch servers ( A -> B or B -> A)
        current_index = self.all_servers.index(self.current_server)
        total_servers = len(self.all_servers)

        # Loop through the list looking for the next server available
        for i in range (1, total_servers):
            next_index = (current_index + i) % total_servers
            candidato = self.all_servers[next_index]
            
            # Health Check
            if self.check_health(candidato['url']):
                self.current_server = candidato
                return True
                
        return False

    def download_segment(self, quality_path):
        """
        Downloads a video segment and measures throughput.
        If it fails, calls try_failover().
        """
        if not self.current_server:
            return None, 0, 0, 0

        # Verifica se estamos em um servidor de fallback e se o principal (A) voltou
        if self.current_server != self.all_servers[0]:
            try:
                # Usa um timeout muito baixo (0.5s) para não travar o vídeo se ainda estiver offline
                response = self.session.get(f"{self.all_servers[0]['url']}/health", timeout=0.5)
                if response.status_code == 200:
                    self.current_server = self.all_servers[0]
                    self.failover_count += 1
            except:
                pass # Continua no fallback se o principal ainda estiver fora

        url = f"{self.current_server['url']}{quality_path}"
        
        try:
            start_time = time.perf_counter()
            # Timeout reduzido para 1s para detectar falhas mais rápido (Failover ágil)
            response = self.session.get(url, timeout=1) 
            end_time = time.perf_counter()
            
            response.raise_for_status()
            content = response.content
            download_time = end_time - start_time
            
            throughput_kbps = (len(content) * 8) / (1000 * download_time) if download_time > 0 else 0
            
            return content, download_time, throughput_kbps, 0
        except Exception:
            if self.try_failover():
                # Try to download again, using new server available
                return self.download_segment(quality_path)
            return None, 0, 0, 0

    def check_health(self, server_url):
        """Checks if a server is healthy via GET /health."""
        try:
            response = self.session.get(f"{server_url}/health", timeout=2)
            if response.status_code == 200:
                return True
            return False
        except:
            return False
