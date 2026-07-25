"""
Gerenciador de Buffer de Reprodução de Vídeo.

Este módulo é responsável por simular o comportamento de um buffer de player de vídeo
em tempo real. Ele gerencia o acúmulo de segmentos baixados, o limite máximo de armazenamento
e o consumo contínuo por parte do player através de uma thread em segundo plano.
"""

import time
import threading

class BufferManager:
    """
    Gerencia o nível do buffer de reprodução (em segundos) utilizando uma thread assíncrona.
    
    Attributes:
        segment_duration (float): Duração de cada segmento de vídeo em segundos.
        buffer_level (float): Nível atual do buffer em segundos.
        is_playing (bool): Indica se o player está reproduzindo conteúdo ou em travamento (stall).
    """
    
    def __init__(self, segment_duration):
        """
        Inicializa o gerenciador de buffer.

        Args:
            segment_duration (float): Duração de cada segmento de vídeo em segundos.
        """
        self.segment_duration = segment_duration
        self.buffer_level = 0.0
        self.is_playing = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # Inicia a thread de consumo contínuo
        self._drain_thread = threading.Thread(target=self._drain_loop, daemon=True)
        self._drain_thread.start()

    def _drain_loop(self):
        """
        Simula o consumo contínuo do player de vídeo.
        1 segundo de tempo real decorrido reduz 1 segundo do nível de buffer.
        """
        last_time = time.perf_counter()
        while not self._stop_event.is_set():
            time.sleep(0.1)  # Atualiza a cada 100 milissegundos
            now = time.perf_counter()
            elapsed = now - last_time
            last_time = now
            
            with self._lock:
                if self.is_playing:
                    self.buffer_level -= elapsed
                    if self.buffer_level <= 0:
                        self.buffer_level = 0.0
                        self.is_playing = False  # Ocorre evento de re-buffering (Stall)

    def add_segment(self):
        """
        Adiciona a duração de um segmento inteiro ao buffer instantaneamente.
        Respeita o limite máximo de retenção de 30 segundos (simulando limite de memória do player).

        Returns:
            float: Nível atualizado do buffer em segundos.
        """
        with self._lock:
            self.buffer_level += self.segment_duration
            if self.buffer_level > 30.0:
                self.buffer_level = 30.0
            
            # Se o player estava pausado/travado e acumulou buffer suficiente, retoma a reprodução
            if not self.is_playing and self.buffer_level >= self.segment_duration:
                self.is_playing = True
                
        return self.get_level()

    def can_play(self):
        """
        Verifica se há conteúdo disponível no buffer para reprodução.

        Returns:
            bool: True se o nível do buffer for maior que zero, False caso contrário.
        """
        with self._lock:
            return self.buffer_level > 0

    def get_level(self):
        """
        Retorna o nível atual do buffer em segundos de forma segura (thread-safe).

        Returns:
            float: Nível atual do buffer em segundos.
        """
        with self._lock:
            return self.buffer_level
            
    def stop(self):
        """Sinaliza e encerra a thread de consumo contínuo do buffer."""
        self._stop_event.set()

