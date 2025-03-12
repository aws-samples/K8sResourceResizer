import numpy as np
import pandas as pd
from typing import List, Optional, Dict, Any
from .base_strategy import BaseStrategy

class TrendAwareStrategy(BaseStrategy):
    """
    Trend-aware resource recommendation strategy that detects and accounts for usage trends.
    
    Algorithm:
    - Uses linear regression to detect usage trends
    - CPU: Adjusts 95th percentile based on growth rate if trend is increasing
    - Memory: Increases buffer if upward trend detected
    - Calculates growth rate using slope of regression line
    - Classifies trends as increasing/decreasing/stable based on threshold
    """
    def calculate_cpu_request(self, cpu_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not cpu_samples or not timestamps:
            return self.config.min_cpu_cores
            
        trend_analysis = self._analyze_trends(cpu_samples, timestamps)
        base_value = np.percentile(cpu_samples, self.config.cpu_percentile)
        
        if trend_analysis['trend'] == 'increasing':
            # Add extra buffer for increasing trends
            growth_factor = 1 + (trend_analysis['growth_rate'] * 1.2)  # 20% extra buffer for growth
            return max(base_value * growth_factor, self.config.min_cpu_cores)
        elif trend_analysis['trend'] == 'volatile':
            # Add larger buffer for volatile workloads
            return max(base_value * 1.2, self.config.min_cpu_cores)
        return max(base_value * 1.1, self.config.min_cpu_cores)

    def calculate_memory_request(self, memory_samples: List[float], timestamps: Optional[List[float]] = None) -> float:
        if not memory_samples or not timestamps:
            return self.config.min_memory_bytes
            
        trend_analysis = self._analyze_trends(memory_samples, timestamps)
        base_value = max(memory_samples)
        
        if trend_analysis['trend'] == 'increasing':
            # Add extra buffer for increasing trends
            growth_factor = 1 + (trend_analysis['growth_rate'] * 1.5)  # 50% extra buffer for growth
            return max(base_value * growth_factor * self.config.memory_buffer, self.config.min_memory_bytes)
        elif trend_analysis['trend'] == 'volatile':
            # Add larger buffer for volatile workloads
            return max(base_value * 1.3 * self.config.memory_buffer, self.config.min_memory_bytes)
        return max(base_value * self.config.memory_buffer, self.config.min_memory_bytes)

    def _analyze_trends(self, samples: List[float], timestamps: Optional[List[float]] = None) -> Dict[str, Any]:
        if len(samples) < 2 or not timestamps:
            return {'trend': 'stable', 'growth_rate': 0, 'volatility': 0}
            
        # Create time series
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(timestamps, unit='s'),
            'value': samples
        })
        
        # Calculate trend using more sophisticated method
        # Use rolling average to smooth out noise
        df['rolling_avg'] = df['value'].rolling(window=6, min_periods=1).mean()
        
        # Calculate overall trend
        x = np.arange(len(df))
        y = df['rolling_avg'].values
        slope, intercept = np.polyfit(x, y, 1)
        
        # Calculate growth rate relative to the mean
        mean_value = df['value'].mean()
        growth_rate = (slope * len(df)) / mean_value if mean_value != 0 else 0
        
        # Calculate volatility
        volatility = df['value'].std() / mean_value if mean_value != 0 else 0
        
        # Determine trend type
        if volatility > self.config.high_variance_threshold:
            trend = 'volatile'
        elif growth_rate > self.config.trend_threshold:
            trend = 'increasing'
        elif growth_rate < -self.config.trend_threshold:
            trend = 'decreasing'
        else:
            trend = 'stable'
            
        return {
            'trend': trend,
            'growth_rate': growth_rate,
            'volatility': volatility,
            'slope': slope,
            'mean': mean_value
        } 