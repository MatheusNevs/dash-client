class ABRPolicy:
    """Base class for ABR policies."""
    def select_quality(self, throughput_kbps, buffer_level, representations):
        raise NotImplementedError

class BaselinePolicy(ABRPolicy):
    """Rate-Based ABR policy (Policy 1)."""
    
    def __init__(self, safety_factor=0.8):
        self.safety_factor = safety_factor

    def select_quality(self, throughput_kbps, buffer_level, representations):
        """
        Selects the highest quality with bitrate < throughput * safety_factor.
        'representations' is a list of dicts with 'quality' and 'bitrate_kbps'.
        """
        # Sort representations by bitrate ascending
        sorted_reprs = sorted(representations, key=lambda x: x['bitrate_kbps'])
        
        selected = sorted_reprs[0] # Default to lowest
        
        available_bandwidth = throughput_kbps * self.safety_factor
        
        for rep in sorted_reprs:
            if rep['bitrate_kbps'] <= available_bandwidth:
                selected = rep
            else:
                break
                
        return selected

class BufferBasedPolicy(ABRPolicy):
    """Buffer-Based ABR policy (Policy 2). To be implemented by Bernardo."""
    
    def select_quality(self, throughput_kbps, buffer_level, representations):
        # Sort representations by bitrate ascending
        sorted_reprs = sorted(representations, key=lambda x: x['bitrate_kbps'])
        
        # TODO: Implement logic based on buffer_level zones
        # Placeholder: Return lowest quality
        return sorted_reprs[0]
