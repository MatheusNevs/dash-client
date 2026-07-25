"""
Gerenciador de Rede e Failover HTTP.

Este módulo é responsável por efetuar requisições HTTP para obtenção do manifesto
e dos segmentos de vídeo, realizar o cálculo de vazão, tempo de download e jitter,
além de implementar o mecanismo automático de failover entre servidores primários e secundários.
"""

import requests
import time
import json

class NetworkManager:
    """
    Gerencia conexões de rede, requisições HTTP, estatísticas de download e failover automático.

    Attributes:
        manifest_url (str): URL de onde o manifesto JSON é baixado.
        session (requests.Session): Sessão HTTP reutilizável.
        all_servers (list[dict]): Lista de servidores ordenados por prioridade.
        current_server (dict | None): Servidor atualmente ativo para requisições.
        manifest (dict | None): Manifesto de vídeo parseado.
        failover_count (int): Contador total de eventos de failover acionados.
        last_download_time (float | None): Tempo de download do segmento anterior (em segundos) para cálculo de jitter.
    """
    
    def __init__(self, manifest_url):
        """
        Inicializa o gerenciador de rede.

        Args:
            manifest_url (str): URL para baixar o manifesto JSON do vídeo.
        """
        self.manifest_url = manifest_url
        self.session = requests.Session()
        self.all_servers = []
        self.current_server = None
        self.manifest = None
        self.failover_count = 0
        self.last_download_time = None

    def fetch_manifest(self):
        """
        Baixa e faz o parse do manifesto JSON do vídeo.
        Normaliza os IDs dos servidores e os ordena por prioridade.

        Returns:
            dict | None: Conteúdo do manifesto parseado ou None em caso de falha.
        """
        try:
            response = self.session.get(self.manifest_url, timeout=5)
            response.raise_for_status()
            self.manifest = response.json()
            
            # Sanitiza os IDs dos servidores (ex: 'srv-B' para 'B') para compatibilidade com CSV/Métricas
            for server in self.manifest['servers']:
                if server['id'].startswith('srv-'):
                    server['id'] = server['id'].replace('srv-', '')

            # Ordena servidores por prioridade crescente (menor número = maior prioridade)
            self.all_servers = sorted(self.manifest['servers'], key=lambda x: x['priority'])
            self.current_server = self.all_servers[0]
            
            return self.manifest
        except Exception:
            return None

    def try_failover(self):
        """
        Tenta alternar a conexão para um servidor secundário disponível (Fallback).

        Returns:
            bool: True se encontrou um servidor saudável e realizou a troca, False se nenhum respondeu.
        """
        # Incrementa o contador global de failovers
        self.failover_count += 1

        current_index = self.all_servers.index(self.current_server)
        total_servers = len(self.all_servers)

        # Percorre a lista de servidores procurando o próximo nó saudável
        for i in range(1, total_servers):
            next_index = (current_index + i) % total_servers
            candidato = self.all_servers[next_index]
            
            # Realiza verificação de integridade (Health Check)
            if self.check_health(candidato['url']):
                self.current_server = candidato
                return True
                
        return False

    def download_segment(self, quality_path):
        """
        Baixa um segmento de vídeo de determinada qualidade e mede a vazão e jitter da rede.
        Caso o download falhe ou sofra timeout, dispara a rotina de failover.

        Args:
            quality_path (str): Caminho relativo do segmento (ex: '/segment_1_1080p.m4s').

        Returns:
            tuple: (content, download_time, throughput_kbps, jitter_ms)
                - content (bytes | None): Conteúdo bruto do segmento baixado.
                - download_time (float): Tempo de download em segundos.
                - throughput_kbps (float): Vazão medida em kilobits por segundo.
                - jitter_ms (float): Jitter bruto em milissegundos.
        """
        if not self.current_server:
            return None, 0, 0, 0

        # Se estiver usando um servidor fallback, verifica se o servidor principal (A) voltou a operar
        if self.current_server != self.all_servers[0]:
            try:
                # Usa um timeout curto (0.5s) no health check para evitar travamentos
                response = self.session.get(f"{self.all_servers[0]['url']}/health", timeout=0.5)
                if response.status_code == 200:
                    self.current_server = self.all_servers[0]
                    self.failover_count += 1
            except:
                pass  # Permanece no servidor fallback se o principal ainda estiver offline

        url = f"{self.current_server['url']}{quality_path}"
        
        try:
            start_time = time.perf_counter()
            # Timeout curto de 1s para rápido diagnóstico de falhas e failover ágil
            response = self.session.get(url, timeout=1) 
            end_time = time.perf_counter()
            
            response.raise_for_status()
            content = response.content
            download_time = end_time - start_time
            
            # Cálculo de Jitter (ms): Variação absoluta nos tempos de download consecutivos
            jitter_ms = 0
            if self.last_download_time is not None:
                jitter_ms = abs(download_time - self.last_download_time) * 1000
            self.last_download_time = download_time

            throughput_kbps = (len(content) * 8) / (1000 * download_time) if download_time > 0 else 0
            
            return content, download_time, throughput_kbps, jitter_ms
        except Exception:
            if self.try_failover():
                # Tenta novamente o download utilizando o novo servidor selecionado no failover
                return self.download_segment(quality_path)
            return None, 0, 0, 0

    def check_health(self, server_url):
        """
        Verifica a integridade de um servidor efetuando uma requisição GET na rota /health.

        Args:
            server_url (str): URL base do servidor a ser testado.

        Returns:
            bool: True se o servidor respondeu com HTTP 200, False caso contrário.
        """
        try:
            response = self.session.get(f"{server_url}/health", timeout=2)
            if response.status_code == 200:
                return True
            return False
        except:
            return False

