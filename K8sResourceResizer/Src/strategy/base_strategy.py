from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from . import RecommendationConfig

class BaseStrategy(ABC):
    """
    Abstract base class for all recommendation strategies.
    Each strategy must implement calculate_cpu_request and calculate_memory_request methods.
    """
    def __init__(self, config: RecommendationConfig):
        self.config = config

    @abstractmethod
    def calculate_cpu_request(self, cpu_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        """
        Calculate the recommended CPU request based on usage samples.
        
        Args:
            cpu_samples: List of CPU usage samples
            timestamps: Optional list of timestamps for the samples
            
        Returns:
            float: Recommended CPU request in cores
        """
        pass

    @abstractmethod
    def calculate_memory_request(self, memory_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        """
        Calculate the recommended memory request based on usage samples.
        
        Args:
            memory_samples: List of memory usage samples in bytes
            timestamps: Optional list of timestamps for the samples
            
        Returns:
            float: Recommended memory request in bytes
        """
        pass 