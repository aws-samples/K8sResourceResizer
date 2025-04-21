import numpy as np
from typing import List, Optional, Dict, Tuple
from .base_strategy import BaseStrategy
from collections import deque
import math
from dataclasses import dataclass
from statistics import stdev, mean

@dataclass
class Sample:
    value: float
    timestamp: float
    weight: float = 1.0
    importance: float = 1.0

class DecayingHistogram:
    """
    Streaming decaying histogram with adaptive weights and smart pruning.
    
    Features:
    - Adaptive decay rates based on data volatility
    - Smart sample pruning based on importance
    - Weighted quantile computation
    - Memory-efficient storage
    """
    
    def __init__(self, max_samples: int = 1000, initial_decay_rate: float = 0.1):
        self.max_samples = max_samples
        self.decay_rate = initial_decay_rate
        self.samples = deque(maxlen=max_samples)
        self._volatility_window = 100  # Window for volatility calculation
        self._min_importance = 0.1  # Minimum importance to keep a sample
        
    def _calculate_volatility(self) -> float:
        """Calculate volatility of recent samples."""
        if len(self.samples) < 2:
            return 0.0
            
        recent_samples = [s.value for s in list(self.samples)[-self._volatility_window:]]
        if len(recent_samples) < 2:
            return 0.0
            
        return stdev(recent_samples) / mean(recent_samples) if mean(recent_samples) > 0 else 0.0
        
    def _update_decay_rate(self):
        """Update decay rate based on volatility."""
        volatility = self._calculate_volatility()
        # Higher volatility = faster decay
        self.decay_rate = min(0.5, max(0.01, volatility * 2))
        
    def _calculate_importance(self, value: float, timestamp: float) -> float:
        """Calculate importance of a new sample."""
        if not self.samples:
            return 1.0
            
        # Calculate deviation from recent trend
        recent_values = [s.value for s in list(self.samples)[-10:]]
        if recent_values:
            recent_mean = mean(recent_values)
            deviation = abs(value - recent_mean) / recent_mean if recent_mean > 0 else 0.0
            # Higher deviation = higher importance
            return min(1.0, max(0.1, deviation * 2))
        return 1.0
        
    def add_sample(self, value: float, timestamp: float):
        """Add a new sample with adaptive importance."""
        self._update_decay_rate()
        importance = self._calculate_importance(value, timestamp)
        
        # Calculate age-based weight
        if self.samples:
            current_time = self.samples[-1].timestamp
            age = current_time - timestamp
            weight = math.exp(-self.decay_rate * age)
        else:
            weight = 1.0
            
        sample = Sample(value=value, timestamp=timestamp, weight=weight, importance=importance)
        self.samples.append(sample)
        
        # Prune samples with low importance
        if len(self.samples) > self.max_samples:
            # Keep samples with high importance
            sorted_samples = sorted(self.samples, key=lambda x: x.importance, reverse=True)
            self.samples = deque(sorted_samples[:self.max_samples], maxlen=self.max_samples)
        
    def _get_weights(self) -> np.ndarray:
        """Calculate normalized weights considering both age and importance."""
        if not self.samples:
            return np.array([])
            
        weights = np.array([s.weight * s.importance for s in self.samples])
        return weights / np.sum(weights) if np.sum(weights) > 0 else weights
        
    def get_quantile(self, q: float) -> float:
        """Compute weighted quantile from the histogram."""
        if not self.samples:
            return 0.0
            
        weights = self._get_weights()
        sorted_indices = np.argsort([s.value for s in self.samples])
        sorted_samples = np.array([self.samples[i].value for i in sorted_indices])
        sorted_weights = weights[sorted_indices]
        
        # Compute cumulative weights
        cum_weights = np.cumsum(sorted_weights)
        # Find the index where cumulative weight exceeds quantile
        idx = np.searchsorted(cum_weights, q)
        
        if idx == 0:
            return sorted_samples[0]
        if idx == len(sorted_samples):
            return sorted_samples[-1]
            
        # Linear interpolation between adjacent samples
        weight_below = cum_weights[idx-1]
        weight_above = cum_weights[idx]
        sample_below = sorted_samples[idx-1]
        sample_above = sorted_samples[idx]
        
        # Interpolate based on weights
        if weight_above == weight_below:
            return sample_below
        fraction = (q - weight_below) / (weight_above - weight_below)
        return sample_below + fraction * (sample_above - sample_below)

class BasicStrategy(BaseStrategy):
    """
    Improved basic resource recommendation strategy with adaptive features.
    
    Algorithm:
    - Adaptive decay rates based on data volatility
    - Smart sample pruning based on importance
    - Dynamic confidence factors based on data quality
    - Memory-efficient storage
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.cpu_histogram = DecayingHistogram(max_samples=1000, initial_decay_rate=0.1)
        self.memory_histogram = DecayingHistogram(max_samples=1000, initial_decay_rate=0.05)
        
    def _calculate_data_quality(self, samples: List[Sample]) -> float:
        """Calculate data quality score based on various metrics."""
        if not samples:
            return 0.0
            
        values = [s.value for s in samples]
        
        # Calculate metrics
        volatility = stdev(values) / mean(values) if mean(values) > 0 else 0.0
        coverage = len(samples) / self.cpu_histogram.max_samples
        importance = mean([s.importance for s in samples])
        
        # Combine metrics into quality score (0-1)
        quality = (1 - min(1, volatility)) * 0.4 + coverage * 0.3 + importance * 0.3
        return max(0.1, min(1.0, quality))
        
    def _get_confidence_factor(self, samples: List[Sample]) -> float:
        """Compute dynamic confidence factor based on data quality."""
        if not samples:
            return 1.15  # Default margin
            
        quality = self._calculate_data_quality(samples)
        # Higher quality = lower margin
        base_margin = 1.15
        min_margin = 1.05
        return max(min_margin, base_margin * (1 - quality * 0.5))
    
    def calculate_cpu_request(self, cpu_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        """Calculate CPU request using improved weighted quantiles."""
        if not cpu_samples or not timestamps:
            return self.config.min_cpu_cores
            
        # Add samples to histogram
        for value, timestamp in zip(cpu_samples, timestamps):
            self.cpu_histogram.add_sample(value, timestamp)
            
        # Get weighted quantiles
        p50 = self.cpu_histogram.get_quantile(0.50)
        p90 = self.cpu_histogram.get_quantile(0.90)
        p95 = self.cpu_histogram.get_quantile(0.95)
        
        # Compute confidence factor based on data quality
        confidence = self._get_confidence_factor(list(self.cpu_histogram.samples))
        
        # Smart base value selection
        if p95 / p90 > 1.5:  # If p95 is 50% higher than p90
            base_value = p90
        else:
            base_value = p95
            
        return max(base_value * confidence, self.config.min_cpu_cores)

    def calculate_memory_request(self, memory_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        """Calculate memory request using improved weighted quantiles."""
        if not memory_samples or not timestamps:
            return self.config.min_memory_bytes
            
        # Add samples to histogram
        for value, timestamp in zip(memory_samples, timestamps):
            self.memory_histogram.add_sample(value, timestamp)
            
        # Get weighted quantiles
        p50 = self.memory_histogram.get_quantile(0.50)
        p90 = self.memory_histogram.get_quantile(0.90)
        p95 = self.memory_histogram.get_quantile(0.95)
        
        # Compute confidence factor based on data quality
        confidence = self._get_confidence_factor(list(self.memory_histogram.samples))
        
        # Smart base value selection
        if p95 / p90 > 1.5:  # If p95 is 50% higher than p90
            base_value = p90
        else:
            base_value = p95
            
        return max(base_value * confidence * self.config.memory_buffer, self.config.min_memory_bytes) 