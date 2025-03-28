import numpy as np
from typing import List, Optional
from .base_strategy import BaseStrategy

class BasicStrategy(BaseStrategy):
    """
    Basic resource recommendation strategy that uses simple statistical methods.
    
    Algorithm:
    - CPU: Uses 95th percentile of CPU usage as the request value
    - Memory: Uses peak memory usage + 15% buffer as both request and limit
    - Enforces minimum values for both CPU and memory
    - No time-based analysis or trend detection
    """
    
    def calculate_cpu_request(self, cpu_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        """
        Calculate CPU request using 95th percentile with a 10% safety buffer.
        
        Args:
            cpu_samples: List of CPU usage samples in cores
            timestamps: Optional list of timestamps (not used in basic strategy)
            
        Returns:
            float: Recommended CPU request in cores
        """
        if not cpu_samples:
            return self.config.min_cpu_cores
            
        p95 = np.percentile(cpu_samples, 95)
        safety_buffer = 1.1  # 10% safety buffer
        
        return max(p95 * safety_buffer, self.config.min_cpu_cores)

    def calculate_memory_request(self, memory_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        """
        Calculate memory request using peak usage with configurable buffer.
        
        Args:
            memory_samples: List of memory usage samples in bytes
            timestamps: Optional list of timestamps (not used in basic strategy)
            
        Returns:
            float: Recommended memory request in bytes
        """
        if not memory_samples:
            return self.config.min_memory_bytes
            
        peak = max(memory_samples)
        
        return max(peak * self.config.memory_buffer, self.config.min_memory_bytes) 