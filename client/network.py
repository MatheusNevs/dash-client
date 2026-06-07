import requests
import time
import json

class NetworkManager:
    """Handles HTTP requests, network metrics, and automatic failover."""
    
    def __init__(self, manifest_url):
        self.manifest_url = manifest_url
        self.session = requests.Session()
        self.all_servers = [] # TODO (Maria): Armazenar todos os servidores aqui
        self.current_server = None
        self.manifest = None
        self.failover_count = 0 # TODO (Maria): Incrementar este contador a cada troca

    def fetch_manifest(self):
        """Downloads and parses the manifest JSON."""
        try:
            response = self.session.get(self.manifest_url, timeout=5)
            response.raise_for_status()
            self.manifest = response.json()
            
            # TODO (Maria): Ordenar por prioridade e salvar em self.all_servers
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
        # Placeholder: por enquanto não faz nada
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
            # Dica (Maria): O timeout pode ser reduzido para detectar falhas mais rápido
            response = self.session.get(url, timeout=5) 
            end_time = time.perf_counter()
            
            response.raise_for_status()
            content = response.content
            download_time = end_time - start_time
            
            throughput_kbps = (len(content) * 8) / (1000 * download_time) if download_time > 0 else 0
            
            return content, download_time, throughput_kbps, 0
        except Exception as e:
            print(f"\n[Network] Download failed: {e}")
            # TODO (Maria): Tentar failover e, se der certo, repetir o download
            if self.try_failover():
                return self.download_segment(quality_path) # Recursão simples para tentar de novo
            return None, 0, 0, 0

    def check_health(self, server_url):
        """Checks if a server is healthy via GET /health."""
        try:
            # TODO (Maria): Medir a latência desta chamada para o relatório
            response = self.session.get(f"{server_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False
