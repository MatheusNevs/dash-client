import time
import threading

class BufferManager:
    """Manages the playback buffer level in seconds using a background thread."""
    
    def __init__(self, segment_duration):
        self.segment_duration = segment_duration
        self.buffer_level = 0.0
        self.is_playing = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # Inicia a thread de consumo contínuo
        self._drain_thread = threading.Thread(target=self._drain_loop, daemon=True)
        self._drain_thread.start()

    def _drain_loop(self):
        """Simula o consumo contínuo do player de vídeo (1 segundo real = 1 segundo de buffer)."""
        last_time = time.perf_counter()
        while not self._stop_event.is_set():
            time.sleep(0.1) # Atualiza a cada 100ms
            now = time.perf_counter()
            elapsed = now - last_time
            last_time = now
            
            with self._lock:
                if self.is_playing:
                    self.buffer_level -= elapsed
                    if self.buffer_level <= 0:
                        self.buffer_level = 0.0
                        self.is_playing = False # Rebuffering event (Stall)

    def add_segment(self):
        """Adiciona um segmento inteiro (+2.0s) ao buffer instantaneamente."""
        with self._lock:
            self.buffer_level += self.segment_duration
            
            # Se estava travado e agora tem dados suficientes, volta a tocar
            if not self.is_playing and self.buffer_level >= self.segment_duration:
                self.is_playing = True
                
        return self.get_level()

    def can_play(self):
        """Returns True if there is content in the buffer to play."""
        with self._lock:
            return self.buffer_level > 0

    def get_level(self):
        """Returns the current buffer level in seconds safely."""
        with self._lock:
            return self.buffer_level
            
    def stop(self):
        """Encerra a thread de consumo no fim do programa."""
        self._stop_event.set()
