import numpy as np
import pandas as pd
from typing import List, Optional
from .base_strategy import BaseStrategy

class WorkloadAwareStrategy(BaseStrategy):
    """
    Workload-aware resource recommendation strategy that adapts to workload characteristics.
    
    Algorithm:
    - Classifies workloads based on usage variance (stable/moderate/intensive)
    - CPU: Uses 99th percentile for CPU-intensive workloads, 95th for others
    - Memory: Applies 20% buffer for memory-intensive workloads, standard buffer for others
    - Uses coefficient of variation to detect workload intensity
    - Adapts recommendations based on workload classification
    """
    def calculate_cpu_request(self, cpu_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not cpu_samples:
            return self.config.min_cpu_cores
            
        workload_type = self._detect_workload_type(cpu_samples, timestamps)
        
        if workload_type == 'intensive':
            # Use 99th percentile for CPU-intensive workloads
            return max(np.percentile(cpu_samples, 99) * 1.1, self.config.min_cpu_cores)
        elif workload_type == 'moderate':
            # Use 95th percentile for moderate workloads
            return max(np.percentile(cpu_samples, 95) * 1.1, self.config.min_cpu_cores)
        else:
            # Use 90th percentile for stable workloads
            return max(np.percentile(cpu_samples, 90) * 1.1, self.config.min_cpu_cores)

    def calculate_memory_request(self, memory_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not memory_samples:
            return self.config.min_memory_bytes
            
        workload_type = self._detect_workload_type(memory_samples, timestamps)
        peak = max(memory_samples)
        
        if workload_type == 'intensive':
            # Add 30% buffer for memory-intensive workloads
            return max(peak * 1.3, self.config.min_memory_bytes)
        elif workload_type == 'moderate':
            # Add 20% buffer for moderate workloads
            return max(peak * 1.2, self.config.min_memory_bytes)
        else:
            # Use standard buffer for stable workloads
            return max(peak * self.config.memory_buffer, self.config.min_memory_bytes)

    def _detect_workload_type(self, samples: List[float], timestamps: Optional[List[float]] = None) -> str:
        if not samples:
            return 'stable'
            
        # Create time series for better analysis
        if timestamps:
            df = pd.DataFrame({
                'timestamp': pd.to_datetime(timestamps, unit='s'),
                'value': samples
            })
            # Calculate rolling statistics
            df['rolling_mean'] = df['value'].rolling(window=6, min_periods=1).mean()
            df['rolling_std'] = df['value'].rolling(window=6, min_periods=1).std()
            
            # Calculate various metrics
            mean = df['rolling_mean'].mean()
            std = df['rolling_std'].mean()
            peak_to_mean = df['value'].max() / mean if mean != 0 else 0
            cv = std / mean if mean != 0 else 0  # coefficient of variation
            
            # Detect sudden spikes
            spikes = df[df['value'] > (mean + 2 * std)].shape[0] / len(df)
            
            # Classify based on multiple factors
            if cv > self.config.high_variance_threshold or spikes > 0.1:
                return 'intensive'
            elif cv > self.config.high_variance_threshold / 2 or spikes > 0.05:
                return 'moderate'
            else:
                return 'stable'
        else:
            # Fallback to simple analysis if no timestamps
            mean = np.mean(samples)
            std = np.std(samples)
            cv = std / mean if mean != 0 else 0
            
            if cv > self.config.high_variance_threshold:
                return 'intensive'
            elif cv > self.config.high_variance_threshold / 2:
                return 'moderate'
            else:
                return 'stable' 