import time

class BufferManager:
    """Manages the playback buffer level in seconds."""
    
    def __init__(self, segment_duration):
        self.segment_duration = segment_duration
        self.buffer_level = 0.0
        self.last_update_time = time.perf_counter()
        self.is_playing = False

    def update(self):
        """Updates the buffer level based on elapsed time."""
        now = time.perf_counter()
        elapsed = now - self.last_update_time
        
        if self.is_playing:
            self.buffer_level = max(0.0, self.buffer_level - elapsed)
        
        self.last_update_time = now
        return self.buffer_level

    def add_segment(self):
        """Adds a segment to the buffer."""
        self.update() # First decay based on time since last check
        self.buffer_level += self.segment_duration
        
        # Start playing if we have enough buffer (e.g., at least one segment)
        if not self.is_playing and self.buffer_level >= self.segment_duration:
            self.is_playing = True
            
        return self.buffer_level

    def can_play(self):
        """Returns True if there is content in the buffer to play."""
        self.update()
        return self.buffer_level > 0

    def get_level(self):
        """Returns the current buffer level in seconds."""
        return self.update()
